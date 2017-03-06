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
#
from __future__ import absolute_import
import importlib
import logging
from itertools import product

import celery
from django.db.models import Q
from django.db import transaction
from django.contrib.auth import get_user_model
from lxml import etree
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.ows as ows_bindings
import pyxb

from . import errors
from . import mailsender
from . import models
from .models import Order
from .models import CustomizableItem
from . import utilities
from .constants import ENCODING

logger = logging.getLogger(__name__)

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


def cancel_order(order, notify=False,
                 notification_details="User has cancelled the order"):
    order.status = CustomizableItem.CANCELLED
    order.additional_status_info = notification_details
    order.save()
    if notify:
        _notify_order_stakeholders(
            order=order,
            notification_function=mailsender.send_order_cancelled_email,
        )


def terminate_subscription(subscription, notify=True,
                           notification_details=None):
    subscription.status = CustomizableItem.TERMINATED
    subscription.additional_status_info = (
        notification_details or "Subscription {0.id has been "
                                "terminated".format(subscription)
    )
    subscription.save()
    if notify:
        _notify_order_stakeholders(
            subscription,
            mailsender.send_subscription_terminated_email,
        )


def create_exception_report(code, text, locator=None):
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
        version=OSEO_VERSION)
    exception_report.append(exception)
    result = etree.fromstring(
        exception_report.toxml(encoding=ENCODING),
        parser=utilities.get_etree_parser()
    )
    return result


@transaction.atomic()
def create_massive_order_batch(order, batch_index=0):
    if order.status == Order.CANCELLED:
        logger.error("Order {} has a {} status. Cannot create new "
                     "batches".format(order, order.status))
        raise errors.InvalidOrderIdentifierError()
    processor = utilities.get_item_processor(order.order_type)
    all_identifiers = []
    for item_specification in order.item_specifications.all():
        start, end = processor.get_order_duration(item_specification)
        identifiers = processor.get_massive_order_batch_item_identifiers(
            batch_index=batch_index,
            collection=item_specification.collection,
            start=start,
            end=end
        )
        all_identifiers.extend(product([item_specification], identifiers))
    batch = models.Batch(
        order=order,
        status=order.status,
        additional_status_info=order.additional_status_info
    )
    batch.full_clean()
    batch.save()
    for (item_specification, item_identifier) in all_identifiers:
        order_item = models.OrderItem(
            item_specification=item_specification,
            batch=batch,
            identifier=item_identifier,
        )
        order_item.full_clean()
        order_item.save()
    return batch


@transaction.atomic()
def create_product_order_batch(order):
    logger.debug("Deleting any previous batch that order {} "
                 "might have...".format(order))
    order.batches.all().delete()
    logger.debug("Creating a new batch...")
    batch = models.Batch(
        order=order,
        status=order.status,
        additional_status_info=order.additional_status_info
    )
    batch.full_clean()
    batch.save()
    for item_specification in order.item_specifications.all():
        order_item = models.OrderItem(
            status=order.status,
            additional_status_info=order.additional_status_info,
            item_specification=item_specification,
            batch=batch,
            identifier=item_specification.identifier,
        )
        order_item.full_clean()
        order_item.save()
    return batch


@transaction.atomic()
def create_subscription_batch(order, timeslot, collection,
                              force_creation=False):
    """Create a new batch for a subscription order.

    This method will only create a new batch if the order's status allows it.
    Cancelled, terminated and submitted orders cannot have new batches created.

    A batch is created but it is not dispatched to the processing queue. The
    caller of this method is responsible for dispatching it, if needed.

    Parameters
    ----------
    order: models.Order
        Order for which a new batch is to be created.
    timeslot: datetime.datetime
        Timeslot of the subscription batch
    collection: str
        Collection to process
    force_creation: bool, optional
        Whether a new batch should be created even if it already exists

    Returns
    -------
    batch: models.Batch
        The subscription batch
    created: bool
        Whether the batch has been created or not

    """

    if order.status in (Order.SUBMITTED,
                        Order.CANCELLED,
                        Order.TERMINATED):
        logger.error("Order {!r} has a {!r} status. Cannot create new "
                     "batches".format(order.id, order.status))
        raise errors.InvalidOrderIdentifierError()
    previous_batch = find_subscription_batch(order, timeslot, collection)
    result = None
    created = False
    if previous_batch:
        logger.debug(
            "Found a previously existing batch for the same timeslot and "
            "collection: {!r}".format(previous_batch.id)
        )
        if force_creation:
            logger.debug("Deleting previously existing batch...")
            previous_batch.delete()
        else:
            result = previous_batch
    if result is None:
        batch = models.Batch(
            order=order,
            status=order.status,
            additional_status_info="timeslot:{!r} collection:{!r}".format(
                timeslot, collection)
        )
        batch.full_clean()
        batch.save()
        processor = utilities.get_item_processor(order.order_type)
        for item_spec in order.item_specifications.filter(
                collection=collection):
            identifier = processor.get_subscription_item_identifier(
                timeslot, collection)
            order_item = models.OrderItem(
                item_specification=item_spec,
                batch=batch,
                identifier=identifier,
            )
            order_item.full_clean()
            order_item.save()
        result = batch
        created = True
    return result, created


@transaction.atomic()
def create_tasking_order_batch():
    raise NotImplementedError


def find_subscription_batch(order, timeslot, collection):
    processor = utilities.get_item_processor(order.order_type)
    item_identifier = processor.get_subscription_item_identifier(
        timeslot, collection)
    try:
        existing_order_item = models.OrderItem.objects.get(
            identifier=item_identifier,
            batch__order=order
        )
        existing_batch = existing_order_item.batch
    except models.OrderItem.DoesNotExist:
        logger.debug("Could not find a previous batch in order {!r} for "
                     "{!r} {!r}".format(order, timeslot, collection))
        existing_batch = None
    return existing_batch


def get_operation(request):
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
    operation_function_path = OPERATION_CALLABLES[oseo_op]
    module_path, _, function_name = operation_function_path.rpartition(".")
    the_module = importlib.import_module(module_path)
    the_operation = getattr(the_module, function_name)
    return the_operation, oseo_op


def handle_massive_order(order):
    """Handle an already accepted massive order.

    The handling process consists in creating the first batch of the massive
    order, updating the status accordingly and send the batch to the processing
    queue.

    """

    order.status = CustomizableItem.SUSPENDED
    order.additional_status_info = ("Order is waiting in the queue for an "
                                    "available processing slot")
    batch = create_massive_order_batch(order, batch_index=0)
    batch.order = order
    order.save()
    logger.info(
        "Sending first batch of order {!r} to processing queue".format(order))
    celery.current_app.send_task(
        "oseoserver.tasks.process_batch", (batch.id,))


def handle_product_order(order):
    """Handle an already accepted product order.

    The handling process consists in creating an appropriate batch for the
    order, updating the status and placing the batch in the processing queue.

    Parameters
    ----------
    order: models.Order
        Product order to be handled

    """

    order.status = CustomizableItem.SUSPENDED
    order.additional_status_info = ("Order is waiting in the queue for an "
                                    "available processing slot")
    batch = create_product_order_batch(order)
    order.save()
    logger.info("Sending order {!r} to processing queue...".format(order))
    celery.current_app.send_task(
        "oseoserver.tasks.process_batch", (batch.id,))


def handle_submit(order, approved, notify=False):
    """Handle a newly submitted order after it has been moderated

    Parameters
    ----------
    order: models.Order
        The order to handle
    approved: bool
        Whether the order has been approved or rejected
    notify: bool, optional
        Whether to e-mail the order's user informing of the moderation result
    """

    if approved:
        order.status = Order.ACCEPTED
        order.additional_status_info = (
            "Order has been approved and will be processed when there are "
            "available processing resources."
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
        mail_func = {
            Order.PRODUCT_ORDER: mailsender.send_product_order_moderated_email,
            Order.SUBSCRIPTION_ORDER: (
                mailsender.send_subscription_moderated_email)
        }[order.order_type]

        _notify_order_stakeholders(
            order=order,
            notification_function=mail_func,
            approved=approved
        )
    return approved


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
        result = handle_submit(
            order=order,
            approved=True,
            notify=config["notifications"]["moderation"]
        )
    else:
        logger.debug("Orders of type {!r} have to be manually approved by an "
                     "admin".format(order.order_type))
        mailsender.send_moderation_request_email(
            order_type=order.order_type,
            order_id=order.id
        )
        result = False
    return result


def parse_xml(xml):
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


def process_request(request_data, user):
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

    schema_instance = parse_xml(request_data)
    operation, op_name = get_operation(schema_instance)
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


def _notify_order_stakeholders(order, notification_function, **kwargs):
    mail_recipients = get_user_model().objects.filter(
        Q(oseoserver_order_orders__id=order.pk) | Q(is_staff=True)
    ).exclude(email="").distinct("email")
    notification_function(
        order=order,
        recipients=mail_recipients,
        **kwargs
    )


