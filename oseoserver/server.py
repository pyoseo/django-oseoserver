# Copyright 2017 Ricardo Garcia Silva
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
import datetime as dt
import importlib
import logging

from django.db.models import Q
from django.contrib.auth import get_user_model
from lxml import etree
import pytz
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.ows as ows_bindings
import pyxb

from . import errors
from . import mailsender
from . import models
from .models import Order
from .models import CustomizableItem
from . import tasks
from . import utilities
from .constants import ENCODING

logger = logging.getLogger(__name__)


def moderate_order(order):
    """Moderate a newly placed order.

    Orders may be moderated:

    - Automatically, when the configuration of the order type has the
      ``automatic_approval`` parameter set to ``True``.

    - Manually

    Parameters
    ----------
    order: models.Order
        The order object to be moderated

    """

    config = utilities.get_generic_order_config(order.order_type)
    if config["automatic_approval"]:
        result = handle_submit_order(
            order=order,
            approved=True,
            notify=config["notify_moderation"]
        )
    else:
        mailsender.send_moderation_request_email(
            order_type=order.order_type)
        result = None  # admin will moderate the order later
    return result


def handle_submit(order, approved, notify=False):
    if approved:
        order.status = Order.ACCEPTED
        order.additional_status_info = (
            "Order has been approved and is waiting in the "
            "processing queue for an available slot"
        )
        handler = {
            Order.PRODUCT_ORDER: handle_product_order,
            Order.MASSIVE_ORDER: handle_massive_order,
            Order.SUBSCRIPTION_ORDER: handle_subscription_order,
            Order.TASKING_ORDER: handle_tasking_order,
        }[order.order_type]
        handler(order)
    else:
        order.status = CustomizableItem.CANCELLED
        order.additional_status_info = (
            "Order request has been rejected by the administrators")
    order.save()
    if notify:
        mail_recipients = get_user_model().objects.filter(
            Q(oseoserver_order_orders__id=order.id) | Q(is_staff=True)
        ).exclude(email="").distinct("email")
        mail_func = {
            Order.PRODUCT_ORDER: mailsender.send_product_order_moderated_email,
            Order.SUBSCRIPTION_ORDER: (
                mailsender.send_subscription_moderated_email)
        }[order.order_type]
        mail_func(
            order=order,
            approved=approved,
            recipients=mail_recipients
        )
    return approved


def handle_product_order(order):
    """Handle an already accepted product order.

    The handling process consists in creating an appropriate batch for the
    order, updating the status and placing the batch in the processing queue.

    Parameters
    ----------
    order: models.Order
        Product order to be handled

    """

    order.status = CustomizableItem.IN_PRODUCTION
    order.additional_status_info = "Order is being processed"
    batch = create_product_order_batch(order)
    order.save()
    batch.dispatch()


def handle_massive_order(order):
    """Handle an already accepted massive order.

    The handling process consists in creating the first batch of the massive
    order, updating the status accordingly and send the batch to the processing
    queue.

    """

    batch = create_massive_order_batch(order, batch_index=0)
    batch.order = order
    order.status = CustomizableItem.IN_PRODUCTION
    order.additional_status_info = "Order is being processed"
    order.save()
    batch.dispatch()


def handle_subscription_order(order):
    """Handle an already accepted subscription order.

    The handling process consists in changing the status of the order so that
    it reflects its waiting procedure. Subscription orders are processed on
    demand and they're batches are only created when necessary.

    """

    order.status = Order.SUSPENDED
    order.additional_status_info = ("Subscription is active. New batches "
                                    "will be processed when requested.")
    order.save()


def handle_tasking_order(order):
    order.status = Order.SUSPENDED
    order.additional_status_info = ("Tasking order is active. It will be "
                                    "processed when appropriate.")
    order.save()


def create_product_order_batch(order):
    batch = models.Batch(
        order=order,
        status=order.status
    )
    batch.full_clean()
    batch.save()
    for item_specification in order.item_specifications.all():
        order_item = models.OrderItem(
            item_specification=item_specification,
            batch=batch,
            identifier=item_specification.identifier,
        )
        order_item.full_clean()
        order_item.save()
    return batch


# TODO - untested code!
def create_massive_order_batch(order, batch_index=0):
    config = utilities.get_generic_order_config(order.order_type)
    processor = utilities.import_class(config["item_processor"])
    order_total_items = processor.estimate_number_massive_order_items(order)
    order_total_batches = processor.estimate_number_massive_order_batches(
        order)
    batch_item_identifiers = processor.get_batch_item_identifiers(
        batch_number=batch_index)
    batch = models.Batch(
        order=order,
        status=order.status
    )
    batch.full_clean()
    batch.save()
    for (item_identifier, item_specification) in batch_item_identifiers:
        order_item = models.OrderItem(
            item_specification=item_specification,
            batch=batch,
            identifier=item_identifier,
        )
        order_item.full_clean()
        order_item.save()
    return batch


def create_subscription_batch(order, timeslot, collection):
    raise NotImplementedError


def create_tasking_order_batch():
    raise NotImplementedError


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

    OPERATION_CALLABLES = {
        "GetCapabilities": "oseoserver.operations.getcapabilities."
                           "get_capabilities",
        "Submit": "oseoserver.operations.submit.submit",
        "DescribeResultAccess": "oseoserver.operations.describeresultaccess."
                                "describe_result_access",
        "GetOptions": "oseoserver.operations.getoptions.get_options",
        "GetStatus": "oseoserver.operations.getstatus.get_status",
        "Cancel": "oseoserver.operations.cancel.cancel",
    }

    def process_request(self, request_data, user):
        """Entry point for the ordering service.

        This method receives the request data and then parses it into a
        valid pyxb OSEO object. It will then send the request to the
        appropriate operation processing function. Later, after the request has
        been processed, it may send order processing tasks to the processing
        queue, according to the configured behaviour on automatic approvals.

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
        logger.debug("Requested operation: {!r}".format(op_name))
        result = operation(schema_instance, user)
        if op_name == "Submit":
            response, order = result
            moderate_order(order)
        else:
            response = result
        response_element = etree.fromstring(response.toxml(
            encoding=ENCODING), parser=utilities.get_etree_parser())
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
            exception_report.toxml(encoding=ENCODING),
            parser=utilities.get_etree_parser()
        )
        return result

    def parse_xml(self, xml):
        """Parse input XML request and return a valid PyXB object.

        Parameters
        ----------
        xml: lxml.etree.Element
            the XML element with the request

        Returns
        -------
        The instance generated by pyxb

        """

        try:
            document = etree.tostring(xml, encoding=ENCODING)
            oseo_request = oseo.CreateFromDocument(document)
        except (pyxb.UnrecognizedDOMRootNodeError,
                pyxb.UnrecognizedContentError,
                pyxb.SimpleFacetValueError):
            raise errors.NoApplicableCodeError()
        return oseo_request

    def dispatch_subscriptions(self, timeslot, collection):
        """Create new subscription batch and send it to the processing queue"""
        # for each subscription order, call self.dispatch_subscription_batch
        raise NotImplementedError

    def dispatch_subscription_batch(self, order, timeslot, collection):
        #   create subscription_processing_batch
        #   call order.dispatch(batch)
        raise NotImplementedError

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
            batch.updated_on = dt.datetime.now(pytz..utc)
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
            order.dispatch()

    def reprocess_order(self, order_id, **kwargs):
        order = models.Order.objects.get(id=order_id)
        if order.order_type.name == models.Order.PRODUCT_ORDER:
            order.dispatch(force=True)
        elif order.order_type.name == models.Order.SUBSCRIPTION_ORDER:
            self.dispatch_subscription_order(order, kwargs["timeslot"],
                                             kwargs["collection"])
        else:
            raise ValueError("Invalid order type: {}".format(
                order.order_type.name))

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

    def _get_operation(self, request):
        """Dynamically import the requested operation function at runtime.

        Parameters
        ----------
        request: pyxb.bundles.opengis.oseo_1_0 subtype

        Returns
        -------
        function
            The operation function that can be called in order to process the
            request.
        str
            The name of the OSEO operation that has been requested

        """

        oseo_op = request.toDOM().firstChild.tagName.partition(":")[-1]
        operation_function_path = self.OPERATION_CALLABLES[oseo_op]
        module_path, _, function_name = operation_function_path.rpartition(".")
        the_module = importlib.import_module(module_path)
        the_operation = getattr(the_module, function_name)
        return the_operation, oseo_op
