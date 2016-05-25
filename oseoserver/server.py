# Copyright 2015 Ricardo Garcia Silva
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""This module defines the OseoServer class, which implements general request
processing operations and then delegates to specialized operation classes
that preform each OSEO operation.

.. code:: python

   s = oseoserver.OseoServer()
   result, status_code, response_headers = s.process_request(request)
"""

# Creating the ParameterData element:
#
# * create an appropriate XML Schema Definition file (xsd)
# * generate pyxb bindings for the XML schema with:
#
#  pyxbgen --schema-location=pyoseo.xsd --module=pyoseo_schema
#
# * in ipython
#
#  import pyxb.binding.datatypes as xsd
#  import pyxb.bundles.opengis.oseo as oseo
#  import pyoseo_schema
#
#  pd = oseo.ParameterData()
#  pd.encoding = 'XMLEncoding'
#  pd.values = xsd.anyType()
#  pd.values.append(pyoseo_schema.fileFormat('o valor'))
#  pd.values.append(pyoseo_schema.projection('a projeccao'))
#  pd.toxml()

from __future__ import absolute_import
from datetime import datetime
import logging

from django.db.models import Q
from lxml import etree
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.ows as ows_bindings
import pyxb

from . import tasks
from . import models
from . import errors
from . import utilities
#from .auth.usernametoken import UsernameTokenAuthentication
from .signals import signals

logger = logging.getLogger(__name__)


class OseoServer(object):
    """Handle requests that come from Django and process them.

    This class performs some pre-processing of requests, such as schema
    validation and user authentication. It then offloads the actual processing
    of requests to specialized OSEO operation classes. After the request has
    been processed, there is also some post-processing stuff, such as wrapping
    the result with the correct SOAP headers.

    Clients of this class should use only the process_request method.

    """

    DEFAULT_USER_NAME = 'oseoserver_user'
    """Used for anonymous servers"""

    OSEO_VERSION = "1.0.0"

    ENCODING = "utf-8"

    _namespaces = {
        "soap": "http://www.w3.org/2003/05/soap-envelope",
        "soap1.1": "http://schemas.xmlsoap.org/soap/envelope/",
        "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-"
                "wssecurity-secext-1.0.xsd",
        "ows": "http://www.opengis.net/ows/2.0",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }

    _exception_codes = {
        "AuthorizationFailed": "Sender",
        "AuthenticationFailed": "Sender",
        "InvalidOrderIdentifier": "Sender",
        "NoApplicableCode": "Sender",
        "UnsupportedCollection": "Sender",
        "InvalidParameterValue": "Sender",
        "SubscriptionNotSupported": "Sender",
        "ProductOrderingNotSupported": "Sender",
        "FutureProductNotSupported": "Sender",
    }

    OPERATION_CLASSES = {
        "GetCapabilities": "oseoserver.operations.getcapabilities."
                           "GetCapabilities",
        "Submit": "oseoserver.operations.submit.Submit",
        "DescribeResultAccess": "oseoserver.operations.describeresultaccess."
                                "DescribeResultAccess",
        "GetOptions": "oseoserver.operations.getoptions.GetOptions",
        "GetStatus": "oseoserver.operations.getstatus.GetStatus",
        "Cancel": "oseoserver.operations.cancel.Cancel",
    }

    def process_request(self, request_data, user):
        """Entry point for the ordering service.

        This method receives the raw request data as a string and then parses
        it into a valid pyxb OSEO object. It will then send the request to the
        appropriate operation processing class.

        Parameters
        ----------
        request_data: str
            The raw request data
        user: django.contrib.auth.models.User
            The django user that is responsible for the request

        Returns
        -------
        response, status_code, headers: (str, int, dict)
            The response XML document, as a string, the HTTP status code
            and a dictionary with HTTP headers to be set by the wsgi server

        """

        element = etree.fromstring(request_data)
        response_headers = dict()
        soap_version = self._is_soap(element)
        if soap_version is not None:
            data = self._get_soap_data(element, soap_version)
            if soap_version == '1.2':
                logger.debug('SOAP 1.2 request')
                response_headers['Content-Type'] = 'application/soap+xml'
            else:
                logger.debug('SOAP 1.1 request')
                response_headers['Content-Type'] = 'text/xml'
        else:
            logger.debug('Non SOAP request')
            data = element
            response_headers['Content-Type'] = 'application/xml'
        try:
            #user = self.authenticate_request(element, soap_version)
            schema_instance = self.parse_xml(data)
            operation, op_name = self._get_operation(schema_instance)
            response, status_code, order = operation(schema_instance, user)
            if op_name == "Submit":
                if order.status == models.CustomizableItem.SUBMITTED:
                    utilities.send_moderation_email(order)
                else:
                    order_type = order.order_type.name
                    if order_type == models.Order.PRODUCT_ORDER:
                        self.dispatch_product_order(order)
            if soap_version is not None:
                result = self._wrap_soap(response, soap_version)
            else:
                result = response.toxml(encoding=self.ENCODING)
        except errors.OseoError as err:
            if err.code == 'AuthorizationFailed':
                status_code = 401
                # we should probably also adjust the response's headers to 
                # include a WWW-authenticate HTTP header as well
            else:
                status_code = 400
            result = self.create_exception_report(err.code, err.text,
                                                  soap_version,
                                                  locator=err.locator)
            signals.invalid_request.send_robust(sender=self,
                                                request_data=request_data,
                                                exception_report=result)
        except errors.NonSoapRequestError as e:
            status_code = 400
            result = e
        except errors.ServerError as e:
            status_code = 500
            result = e
        return result, status_code, response_headers

    #def authenticate_request(self, request_element, soap_version):
    #    """Authenticate an OSEO request.

    #    Verify that the incoming request is made by a valid user.
    #    PyOSEO uses SOAP-WSS UsernameToken Profile v1.0 authentication. The
    #    specification is available at:

    #    https://www.oasis-open.org/committees/download.php/16782/
    #        wss-v1.1-spec-os-UsernameTokenProfile.pdf

    #    Request authentication can be customized according to the
    #    needs of each ordering server. This method plugs into that by
    #    trying to load an external authentication class.

    #    There are two auth scenarios:

    #    * A returning user
    #    * A new user

    #    The actual authentication is done by a custom class. This class
    #    is specified for each OseoGroup instance in its `authentication_class`
    #    attribute.

    #    The custom authentication class must provide the following API:

    #    .. py:function:: authenticate_request(user_name, password, **kwargs)

    #    .. py:function:: is_user(user_name, password, **kwargs)
    #    """

    #    auth = UsernameTokenAuthentication()
    #    user_name, password, extra = auth.get_details(request_element,
    #                                                  soap_version)
    #    logger.debug("user_name: {}".format(user_name))
    #    logger.debug("password: {}".format(password))
    #    logger.debug("extra: {}".format(extra))
    #    try:
    #        user = models.OseoUser.objects.get(user__username=user_name)
    #        auth_class = user.oseo_group.authentication_class
    #    except models.OseoUser.DoesNotExist:
    #        user = self.add_user(user_name, password, **extra)
    #        auth_class = user.oseo_group.authentication_class
    #    try:
    #        instance = utilities.import_class(auth_class)
    #        authenticated = instance.authenticate_request(user_name, password,
    #                                                      **extra)
    #        if not authenticated:
    #            raise errors.AuthenticationFailedError()
    #    except errors.OseoError:
    #        raise  # this error is handled by the calling method
    #    except Exception as e:
    #        # other errors are re-raised as InvalidSettings
    #        logger.error('exception class: {}'.format(
    #                     e.__class__.__name__))
    #        logger.error('exception args: {}'.format(e.args))
    #        raise errors.ServerError('Invalid authentication class')
    #    logger.info('User {} authenticated successfully'.format(user_name))
    #    return user
    #
    #def add_user(self, user_name, password, **kwargs):
    #    oseo_user = None
    #    groups = models.OseoGroup.objects.all()
    #    found_group = False
    #    current = 0
    #    while not found_group and current < len(groups):
    #        current_group = groups[current]
    #        custom_auth = utilities.import_class(
    #            current_group.authentication_class)
    #        if custom_auth.is_user(user_name, password, **kwargs):
    #            found_group = True
    #            user = models.User.objects.create_user(user_name,
    #                                                   password=None)
    #            oseo_user = models.OseoUser()
    #            oseo_user.user = user
    #            oseo_user.oseo_group = current_group
    #            oseo_user.save()
    #        current += 1
    #    return oseo_user

    def create_exception_report(self, code, text, soap_version, locator=None):
        """
        :arg code: OSEO exception code. Can be any of the defined
                   exceptionCode values in the OSEO and OWS Common 
                   specifications.
        :type code: str
        :arg text: Text to display in the exception report
        :type text: str
        :arg soap_version: Version of the SOAP protocol to use, if any
        :type soap_version: str or None
        :arg locator: value to display in the 'locator' field
        :type locator: str
        :return: A string with the XML exception report
        """

        exception = ows_bindings.Exception(exceptionCode=code)
        if locator is not None:
            exception.locator = locator
        exception.append(text)
        exception_report = ows_bindings.ExceptionReport(
            version=self.OSEO_VERSION)
        exception_report.append(exception)
        if soap_version is not None:
            soap_code = self._exception_codes[code]
            result = self._wrap_soap_fault(exception_report, soap_code,
                                           soap_version)
        else:
            result = exception_report.toxml(encoding=self.ENCODING)
        return result

    def parse_xml(self, xml):
        """Parse the input XML request and return a valid PyXB object.

        :arg xml: the XML element with the request
        :xml type: lxml.etree.Element
        :return: The instance generated by pyxb
        """

        try:
            document = etree.tostring(xml, encoding=self.ENCODING,
                                      pretty_print=True)
            oseo_request = oseo.CreateFromDocument(document)
        except (pyxb.UnrecognizedDOMRootNodeError,
                pyxb.UnrecognizedContentError,
                pyxb.SimpleFacetValueError) as e:
            raise errors.NoApplicableCodeError()
        return oseo_request

    def dispatch_product_order(self, order, force=False):
        """Dispatch a product order for processing in the async queue.

        :arg order: the order to be dispatched
        :type order: models.Order
        :arg force: Should the order be dispatched even if it has not been
        moderated?
        :type force: bool
        """

        if force:
            order.status = models.CustomizableItem.ACCEPTED
        if order.status == models.CustomizableItem.ACCEPTED:
            logger.debug("Sending order {} to processing queue...".format(
                order.id))
            tasks.process_product_order.apply_async((order.id,))

    # the code that checks the value of the email notification extension
    # does not belong in oseoserver. This could be simplified by
    # sending custom notification e-mails as a response to a signal
    #sent whenever there is a status change
    def dispatch_subscription_order(self, order, timeslot, collection):
        """Create a new subscription batch and send it to the processing queue.

        :param timeslot:
        :param collection:
        :type collection: list(models.Collection)
        :return:
        """

        batch, created = models.SubscriptionBatch.objects.get_or_create(
            order=order, collection=collection, timeslot=timeslot)
        if created:
            batch.order = order
            batch.save()
            processor, params = utilities.get_processor(
                order.order_type,
                models.ItemProcessor.PROCESSING_PROCESS_ITEM,
                logger_type="pyoseo"
            )
            spec = order.batches.first()
            spec_item = spec.order_items.get(collection=collection)
            requested_options = spec_item.export_options()
            identifiers = processor.get_subscription_batch_identifiers(
                timeslot, collection.name, requested_options, **params)
            self._clone_subscription_batch(identifiers, spec, timeslot,
                                           collection, batch)
            order.save()
        else:
            for order_item in batch.order_items.all():
                order_item.files.all().delete()
            batch.updated_on = datetime.utcnow()
            batch.save()

        notify_user = False
        try:
            extension = order.extension_set.get(
                text__icontains="emailnotification")
            processor, params = utilities.get_processor(
                order.order_type, models.ItemProcessor.PROCESSING_PARSE_OPTION)
            nam, value = processor.parse_extension(extension.text)
            if value.upper() == "EACH":
                notify_user = True
        except models.Extension.DoesNotExist:
            pass
        tasks.process_subscription_order_batch.apply_async(
            (batch.id,), {"notify_user": notify_user})

    def process_subscription_orders(self, timeslot, collections=None,
                                    order_id=None):
        """Process subscriptions for the input timeslot

        :param timeslot:
        :type timeslot: datetime.datetime
        :param collections: A list with the names of the collections to
            process. The default value of None causes all available collections
            to be processed.
        :type collections: [models.Collection] or None
        :param order_id: The id of an existing subscription order to process.
            The default value of None causes the processing of all
            subscriptions that have been accepted.
        :type order_id: int or None
        :return:
        """

        if order_id is None:
            qs = models.SubscriptionOrder.objects.all()
        else:
            qs = models.SubscriptionOrder.objects.filter(id=order_id)
        for order in qs.filter(status=models.CustomizableItem.ACCEPTED):
            if collections is None:
                batch = order.batches.first()
                cols = [oi.collection for oi in batch.order_items.all()]
            else:
                cols = []
                for c in collections:
                    cols.append(models.Collection.objects.get(name=c))
            for c in cols:
                self.dispatch_subscription_order(order, timeslot, c)

    def process_product_orders(self):
        for order in models.ProductOrder.objects.filter(
                status=models.CustomizableItem.ACCEPTED):
            self.dispatch_product_order(order)

    def reprocess_order(self, order_id, **kwargs):
        order = models.Order.objects.get(id=order_id)
        if order.order_type.name == models.Order.PRODUCT_ORDER:
            self.dispatch_product_order(order, force=True)
        elif order.order_type.name == models.Order.SUBSCRIPTION_ORDER:
            self.dispatch_subscription_order(order, kwargs["timeslot"],
                                             kwargs["collection"])
        else:
            raise ValueError("Invalid order type: {}".format(
                order.order_type.name))

    def moderate_order(self, order, approved, rejection_details=None):
        """
        Decide on approval of an order.

        The OSEO standard does not really define any moderation workflow
        for orders. As such, none of the defined statuses fits exactly with
        this process. We are abusing the CANCELLED status for this.

        :param order:
        :param approved:
        :return:
        """

        rejection_details = rejection_details or ("Order request has been "
                                                  "rejected by the "
                                                  "administrators")
        if order.order_type.name == models.Order.PRODUCT_ORDER:
            self._moderate_request(
                order,
                approved,
                acceptance_details="Order has been approved and is waiting "
                                   "in the processing queue",
                rejection_details=rejection_details
            )
            self.dispatch_product_order(order)
        elif order.order_type.name == models.Order.SUBSCRIPTION_ORDER:
            self._moderate_request(
                order,
                approved,
                acceptance_details="Subscription has been approved and will "
                                   "be processed when new products become "
                                   "available",
                rejection_details=rejection_details
            )

    def _clone_subscription_batch(self, order_item_identifiers,
                                  subscription_spec_batch, timeslot,
                                  collection, new_batch):
        try:
            col_item = subscription_spec_batch.order_items.get(
                collection=collection)
            try:
                col_item_payment_option = col_item.selected_payment_option
            except models.SelectedPaymentOption.DoesNotExist:
                col_item_payment_option = None
            try:
                col_item_delivery_option = col_item.selected_delivery_option
            except models.SelectedDeliveryOption.DoesNotExist:
                col_item_delivery_option = None
        except models.Collection.DoesNotExist:
            raise errors.ServerError("Invalid collection: "
                                     "{}".format(collection))
        selected_options = col_item.selected_options.all()
        selected_scene_options = \
            col_item.selected_scene_selection_options.all()
        # django way of cloning model instances is to set the pk and id to None
        for ident in order_item_identifiers:
            new_item = col_item
            new_item.pk = None
            new_item.id = None
            new_item.identifier = ident
            new_item.batch = new_batch
            new_item.save()
            new_item.item_id = "{}_{}_{}".format(
                subscription_spec_batch.order.reference,
                new_batch.id,
                new_item.identifier
            )
            self._clone_item_options(selected_options[:], new_item)
            self._clone_item_scene_selection_options(
                selected_scene_options[:], new_item)
            if col_item_payment_option is not None:
                new_item.selected_payment_option = col_item_payment_option
            if col_item_delivery_option is not None:
                new_item.selected_delivery_option = col_item_delivery_option
            new_item.status = models.CustomizableItem.ACCEPTED
            new_item.additional_status_info = ""
            new_item.save()
        new_batch.save()

    def _clone_item_options(self, existing_options, new_item):
        for op in existing_options:
            op.pk = None
            op.id = None
            op.save()
            new_item.selected_options.add(op)

    def _clone_item_scene_selection_options(self,
                                            existing_scene_selection_options,
                                            new_item):
        for op in existing_scene_selection_options:
            op.pk = None
            op.id = None
            op.save()
            new_item.selected_scene_selection_options.add(op)

    def _get_operation(self, pyxb_request):
        oseo_op = pyxb_request.toDOM().firstChild.tagName.partition(":")[-1]
        op = self.OPERATION_CLASSES[oseo_op]
        return utilities.import_class(op), oseo_op

    def _get_soap_data(self, element, soap_version):
        """
        :arg element: The full request object
        :type element: lxml.etree.Element
        :arg soap_version: The SOAP version in use
        :type soap_version: str
        :return: The contents of the soap:Body element.
        :rtype: lxml.etree.Element
        """

        if soap_version == '1.2':
            path = '/soap:Envelope/soap:Body/*[1]'
        else:
            path = '/soap1.1:Envelope/soap1.1:Body/*[1]'
        xml_element = element.xpath(path, namespaces=self._namespaces)
        return xml_element[0]

    def _is_soap(self, request_element):
        """
        Look for SOAP requests.

        Although the OSEO spec states that SOAP v1.2 is to be used, pyoseo
        accepts both SOAP v1.1 and SOAP v1.2

        :arg request_element: the raw input request
        :type request_element: lxml.etree.Element instance
        """

        ns, tag = request_element.tag.split('}')
        ns = ns[1:]
        result = None
        if tag == 'Envelope':
            if ns == self._namespaces['soap']:
                result = '1.2'
            elif ns == self._namespaces['soap1.1']:
                result = '1.1'
        return result

    def _moderate_request(self, order, approved, acceptance_details="",
                          rejection_details=""):
        if approved:
            order.status = models.CustomizableItem.ACCEPTED
            order.additional_status_info = acceptance_details
        else:
            order.status = models.CustomizableItem.CANCELLED
            order.additional_status_info = rejection_details

        mail_recipients = models.OseoUser.objects.filter(
            Q(orders__id=order.id) | Q(user__is_staff=True)
        ).exclude(user__email="")

        if order.order_type.name == models.Order.SUBSCRIPTION_ORDER:
            utilities.send_subscription_moderated_email(
                order, approved, mail_recipients,
                acceptance_details, rejection_details
            )
        else:
            pass
        order.save()

    def _wrap_soap(self, response, soap_version):
        """
        :arg response: the pyxb instance with the previously generated response
        :type response: pyxb.bundles.opengis.oseo
        :arg soap_version: The SOAP version in use
        :type soap_version: str
        :return: A string with the XML response
        """

        soap_env_ns = {
            'ows': self._namespaces['ows'],
        }
        if soap_version == '1.2':
            soap_env_ns['soap'] = self._namespaces['soap']
        else:
            soap_env_ns['soap'] = self._namespaces['soap1.1']
        soap_env = etree.Element('{%s}Envelope' % soap_env_ns['soap'],
                                 nsmap=soap_env_ns)
        soap_body = etree.SubElement(soap_env, '{%s}Body' %
                                     soap_env_ns['soap'])

        response_string = response.toxml(encoding=self.ENCODING)
        response_string = response_string.encode(self.ENCODING)
        response_element = etree.fromstring(response_string)
        soap_body.append(response_element)
        return etree.tostring(soap_env, encoding=self.ENCODING,
                              pretty_print=True)

    def _wrap_soap_fault(self, exception_report, soap_code, soap_version):
        """
        :arg exception_report: The pyxb instance with the previously generated
                               exception report
        :type exception_report: pyxb.bundles.opengis.ows.ExceptionReport
        :arg soap_code: Can be either 'server' or 'client'
        :type soap_code: str
        :arg soap_version: The SOAP version in use
        :type soap_version: str
        """

        code_msg = 'soap:{}'.format(soap_code.capitalize())
        reason_msg = '{} exception was encountered'.format(
            soap_code.capitalize())
        exception_string = exception_report.toxml(encoding=self.ENCODING)
        exception_string = exception_string.encode(self.ENCODING)
        exception_element = etree.fromstring(exception_string)
        soap_env_ns = {
            'ows': self._namespaces['ows'],
            'xml': self._namespaces['xml'],
        }
        if soap_version == '1.2':
            soap_env_ns['soap'] = self._namespaces['soap']
        else:
            soap_env_ns['soap'] = self._namespaces['soap1.1']
        soap_env = etree.Element('{{{}}}Envelope'.format(soap_env_ns['soap']),
                                 nsmap=soap_env_ns)
        soap_body = etree.SubElement(soap_env, '{{{}}}Body'.format(
                                     soap_env_ns['soap']))
        soap_fault = etree.SubElement(soap_body, '{{{}}}Fault'.format(
                                      soap_env_ns['soap']))
        if soap_version == '1.2':
            fault_code = etree.SubElement(soap_fault, '{{{}}}Code'.format(
                                          soap_env_ns['soap']))
            code_value = etree.SubElement(fault_code, '{{{}}}Value'.format(
                                          soap_env_ns['soap']))
            code_value.text = code_msg
            fault_reason = etree.SubElement(soap_fault, '{{{}}}Reason'.format(
                                            soap_env_ns['soap']))
            reason_text = etree.SubElement(fault_reason, '{{{}}}Text'.format(
                                           soap_env_ns['soap']))
            reason_text.set("{{{}}}lang".format(soap_env_ns["xml"]), "en")
            reason_text.text = reason_msg
            fault_detail = etree.SubElement(soap_fault, '{{{}}}Detail'.format(
                                            soap_env_ns['soap']))
            fault_detail.append(exception_element)
        else:
            fault_code = etree.SubElement(soap_fault, 'faultcode')
            fault_code.text = code_msg
            fault_string = etree.SubElement(soap_fault, 'faultstring')
            fault_string.text = reason_msg
            fault_actor = etree.SubElement(soap_fault, 'faultactor')
            fault_actor.text = ''
            detail = etree.SubElement(soap_fault, 'detail')
            detail.append(exception_element)
        return etree.tostring(soap_env, encoding=self.ENCODING,
                              pretty_print=True)
