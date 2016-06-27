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
from django.contrib.auth import get_user_model
from lxml import etree
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.ows as ows_bindings
import pyxb

from . import tasks
from . import models
from . import errors
from . import utilities
from . import constants
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

    OSEO_VERSION = "1.0.0"

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
        request_data: etree.Element
            The request data
        user: django.contrib.auth.models.User
            The django user that is responsible for the request

        Returns
        -------
        response: etree.Element
            The response's XML content

        """

        schema_instance = self.parse_xml(request_data)
        operation, op_name = self._get_operation(schema_instance)
        result = operation(schema_instance, user)
        if op_name == "Submit":
            response, order = result
            if order.status == constants.OrderStatus.SUBMITTED:
                utilities.send_moderation_email(order)
            else:
                order_type = constants.OrderType(order.order_type)
                if order_type == constants.OrderType.PRODUCT_ORDER:
                    self.dispatch_product_order(order)
        else:
            response = result
        response_element = etree.fromstring(response.toxml(
            encoding=constants.ENCODING))
        return response_element

    def create_exception_report(self, code, text, locator=None):
        """Generate an ExceptionReport

        Parameters
        ----------
        code: str
            OSEO exception code. Can be any of the defined exceptionCode
            values in the OSEO and OWS Common specifications.
        text: str
            Text to display in the exception report
        locator: str
            value to display in the 'locator' field

        Returns
        -------
        etree.Element
            The XML exception report

        """

        exception = ows_bindings.Exception(exceptionCode=code)
        if locator is not None:
            exception.locator = locator
        exception.append(text)
        exception_report = ows_bindings.ExceptionReport(
            version=self.OSEO_VERSION)
        exception_report.append(exception)
        result = etree.fromstring(
            exception_report.toxml(encoding=constants.ENCODING))
        return result

    def parse_xml(self, xml):
        """Parse the input XML request and return a valid PyXB object.

        :arg xml: the XML element with the request
        :xml type: lxml.etree.Element
        :return: The instance generated by pyxb
        """

        try:
            document = etree.tostring(xml, encoding=constants.ENCODING,
                                      pretty_print=True)
            oseo_request = oseo.CreateFromDocument(document)
        except (pyxb.UnrecognizedDOMRootNodeError,
                pyxb.UnrecognizedContentError,
                pyxb.SimpleFacetValueError):
            raise errors.NoApplicableCodeError()
        return oseo_request

    def dispatch_product_order(self, order, force=False):
        """Dispatch a product order for processing in the async queue.

        Parameters
        ----------

        order: oseoserver.models.Order
            The order to be dispatched
        force: bool
            Should the order be dispatched regardless of its status?
        :type force: bool
        """

        status = (constants.OrderStatus.ACCEPTED if force
                  else constants.OrderStatus(order.status))
        if status == constants.OrderStatus.ACCEPTED:
            logger.debug("Sending order {0.id} to processing queue...".format(
                order))
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
        if order.order_type == constants.OrderType.PRODUCT_ORDER.value:
            self._moderate_request(
                order,
                approved,
                acceptance_details="Order has been approved and is waiting "
                                   "in the processing queue",
                rejection_details=rejection_details
            )
            self.dispatch_product_order(order)
        elif order.order_type == constants.OrderType.SUBSCRIPTION_ORDER.value:
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

    def _moderate_request(self, order, approved, acceptance_details="",
                          rejection_details=""):
        if approved:
            order.status = constants.OrderStatus.ACCEPTED.value
            order.additional_status_info = acceptance_details
        else:
            order.status = constants.OrderStatus.CANCELLED.value
            order.additional_status_info = rejection_details

        mail_recipients = get_user_model().objects.filter(
            Q(orders__id=order.id) | Q(is_staff=True)
        ).exclude(email="")

        if order.order_type == constants.OrderType.SUBSCRIPTION_ORDER.value:
            utilities.send_subscription_moderated_email(
                order, approved, mail_recipients,
                acceptance_details, rejection_details
            )
        else:
            pass
        order.save()
