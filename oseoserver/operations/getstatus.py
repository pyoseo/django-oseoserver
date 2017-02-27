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

"""Implements the OSEO GetStatus operation"""

from __future__ import absolute_import
import datetime as dt
import logging

import dateutil.parser
from pyxb import BIND
import pyxb.bundles.opengis.oseo_1_0 as oseo

from .. import models
from .. import errors
from ..utilities import _n
from .. import settings

logger = logging.getLogger(__name__)

BRIEF = "brief"
FULL = "full"


def create_oseo_delivery_address(delivery_address):
    return oseo.DeliveryAddressType(
        firstName=_n(delivery_address.first_name),
        lastName=_n(delivery_address.last_name),
        companyRef=_n(delivery_address.company_ref),
        postalAddress=BIND(
            streetAddress=_n(delivery_address.street_address),
            city=_n(delivery_address.city),
            state=_n(delivery_address.state),
            postalCode=_n(delivery_address.postal_code),
            country=_n(delivery_address.country),
            postBox=_n(delivery_address.post_box),
        ),
        telephoneNumber=_n(delivery_address.telephone),
        facsimileTelephoneNumber=_n(delivery_address.fax),
    )


def create_oseo_delivery_information(delivery_information):
    """Create an OSEO DeliveryInformationType"""
    information = oseo.DeliveryInformationType()
    optional_attrs = [
        delivery_information.first_name,
        delivery_information.last_name,
        delivery_information.company_ref,
        delivery_information.street_address,
        delivery_information.city,
        delivery_information.state,
        delivery_information.postal_code,
        delivery_information.country,
        delivery_information.post_box,
        delivery_information.telephone,
        delivery_information.fax
    ]
    if any(optional_attrs):
        information.mailAddress = oseo.DeliveryAddressType()
        information.mailAddress.firstName = _n(delivery_information.first_name)
        information.mailAddress.lastName = _n(delivery_information.last_name)
        information.mailAddress.companyRef = _n(
            delivery_information.company_ref)
        information.mailAddress.postalAddress = BIND()
        information.mailAddress.postalAddress.streetAddress = _n(
            delivery_information.street_address)
        information.mailAddress.postalAddress.city = _n(
            delivery_information.city)
        information.mailAddress.postalAddress.state = _n(
            delivery_information.state)
        information.mailAddress.postalAddress.postalCode = _n(
            delivery_information.postal_code)
        information.mailAddress.postalAddress.country = _n(
            delivery_information.country)
        information.mailAddress.postalAddress.postBox = _n(
            delivery_information.post_box)
        information.mailAddress.telephoneNumber = _n(
            delivery_information.telephone)
        information.mailAddress.facsimileTelephoneNumber = _n(
            delivery_information.fax)
    for oa in delivery_information.onlineaddress_set.all():
        information.onlineAddress.append(oseo.OnlineAddressType())
        information.onlineAddress[-1].protocol = oa.protocol
        information.onlineAddress[-1].serverAddress = oa.server_address
        information.onlineAddress[-1].userName = _n(oa.user_name)
        information.onlineAddress[-1].userPassword = _n(oa.user_password)
        information.onlineAddress[-1].path = _n(oa.path)
    return information


def create_oseo_delivery_options(instance):
    """Create an OSEO DeliveryOptionsType"""
    ModelClass = models.OrderDeliveryOption if isinstance(
        instance, models.Order) else models.ItemSpecificationDeliveryOption

    try:
        instance_delivery = instance.selected_delivery_option
    except ModelClass.DoesNotExist:
        delivery_options = None
    else:
        delivery_options = oseo.DeliveryOptionsType(
            numberOfCopies = _n(instance_delivery.copies),
            productAnnotation = _n(instance_delivery.annotation),
            specialInstructions = _n(instance_delivery.special_instructions),
        )
        if instance_delivery.delivery_type == (
                models.BaseDeliveryOption.ONLINE_DATA_ACCESS):
            delivery_options.onlineDataAccess = BIND(
                protocol=instance_delivery.delivery_details)
        elif instance_delivery.delivery_type == (
                models.BaseDeliveryOption.ONLINE_DATA_DELIVERY):
            delivery_options.onlineDataDelivery = BIND(
                protocol=instance_delivery.delivery_details)
        else:  # media delivery
            medium, shipping = instance_delivery.delivery_details.partition(
                ",")[::2]
            delivery_options.mediaDelivery = BIND(
                packageMedium=medium,
                shippingInstructions=_n(shipping)
            )
    return delivery_options


def create_oseo_items_status(batch):
    items_status = []
    for item in batch.order_items.all():
        collection_id = _get_collection_identifier(
            item.item_specification.collection)
        status_item = oseo.CommonOrderStatusItemType(
            itemId=str(item.item_specification.item_id),
            productId=item.identifier,
            productOrderOptionsId="Options for {} {}".format(
                item.item_specification.collection,
                item.batch.order.order_type
            ),
            orderItemRemark=_n(item.remark),
            orderItemStatusInfo=oseo.StatusType(
                status=item.status,
                additionalStatusInfo=_n(item.additional_status_info),
                missionSpecificStatusInfo=_n(item.mission_specific_status_info)
            )
        )
        if batch.order.order_type in (models.Order.PRODUCT_ORDER,
                                      models.Order.MASSIVE_ORDER):
            status_item.productId = oseo.ProductIdType(
                identifier=item.identifier,
                collectionId=collection_id,
            )
        elif batch.order.order_type == models.Order.SUBSCRIPTION_ORDER:
            status_item.subscriptionId = oseo.SubscriptionIdType(
                collectionId=collection_id)
        else:  # tasking order
            raise NotImplementedError
        # TODO - add the other optional elements
        # add any 'option' elements that may be present
        # add any 'sceneSelection' elements that may be present
        status_item.deliveryOptions = create_oseo_delivery_options(
            instance=item.item_specification)
        # add any 'payment' elements that may be present
        # add any 'extension' elements that may be present
        items_status.append(status_item)
    return items_status


def _get_collection_identifier(name):
    all_collections = settings.get_collections()
    try:
        config = [c for c in all_collections if c["name"] == name][0]
        identifier = config["collection_identifier"]
    except IndexError:
        identifier = ""
    return identifier



def create_oseo_order_monitor(order, presentation="brief"):
    """Generate the oseo.commonOrderMonitor instance used in GetStatus."""
    order_monitor = oseo.CommonOrderMonitorSpecification(
        orderId=str(order.id),
        orderType=(order.PRODUCT_ORDER if
                   order.order_type == order.MASSIVE_ORDER else
                   order.order_type),
        orderReference=(order.MASSIVE_ORDER_REFERENCE if
                        order.order_type == order.MASSIVE_ORDER else
                        _n(order.reference)),
        orderStatusInfo=oseo.StatusType(
            status=order.status,
            additionalStatusInfo=_n(order.additional_status_info),
            missionSpecificStatusInfo=_n(order.mission_specific_status_info)
        ),
        orderDateTime=order.status_changed_on,
        orderRemark=_n(order.remark),
        packaging=_n(order.packaging),
        priority=_n(order.priority),
    )
    try:
        order_monitor.deliveryInformation = create_oseo_delivery_information(
            order.delivery_information)
    except models.DeliveryInformation.DoesNotExist:
        pass
    try:
        order_monitor.invoiceAddress = create_oseo_delivery_address(
            order.invoice_address)
    except models.InvoiceAddress.DoesNotExist:
        pass
    # add any 'option' elements
    order_monitor.deliveryOptions = create_oseo_delivery_options(
        instance=order)
    if presentation == "full":
        for batch in order.batches.all():
            sits = create_oseo_items_status(batch)
            order_monitor.orderItem.extend(sits)
    return order_monitor


def find_orders(user, last_update=None, last_update_end=None,
                statuses=None, order_reference=None):
    """Find orders that match the request's filtering criteria

    Parameters
    ----------
    user: django.contrib.auth.models.User
        The user that made the request
    last_update: datetime.datetime, optional
        Consider only orders that have been updated since the last time
        a GetStatus request has been received
    last_update_end: pyxb.binding.datatypes.anyType, optional
        Consider only orders that have not been updated since the
        last time a GetStatus request has been received
    statuses: list, optional
        Only return orders whose status is in the provided list. The list
        contents should be elements of the
        `oseoserver.constants.OrderStatus` enumeration
    order_reference: str
        Only return orders that have the input order_reference

    Returns
    -------
    django queryset:
        The orders that match the requested filtering criteria

    """

    records_qs = models.Order.objects.filter(user=user)
    if last_update is not None:
        records_qs = records_qs.filter(status_changed_on__gte=last_update)
    if last_update_end is not None:
        end = last_update_end.content()[0]
        ts = end if isinstance(end, dt.datetime) else dateutil.parser.parse(
            end)
        records_qs = records_qs.filter(status_changed_on__lte=ts)
    if order_reference is not None:
        records_qs = records_qs.filter(reference=order_reference)
    if any(statuses or []):
        records_qs = records_qs.filter(status__in=statuses)
    return records_qs


def generate_get_status_response(records, presentation):
    """Create an oseo.GetstatusResponse instance with the input records

    records: list or django queryset
        Either a one element list with a pyoseo.models.Order
        or a django queryset, that will be evaluated to an
        list of pyoseo.models.Order while iterating.
    presentation: str
        The presentation to use

    """

    response = oseo.GetStatusResponse()
    response.status = "success"
    for record in records:
        order_monitor = create_oseo_order_monitor(record, presentation)
        response.orderMonitorSpecification.append(order_monitor)
    return response


def get_status(request, user):
    """Implements the OSEO Getstatus operation.

    See section 14 of the OSEO specification for details on the
    Getstatus operation.

    Parameters
    ----------
    request: oseo.GetStatus
        The incoming request
    user: django.contrib.auth.User
        The django user that placed the request

    Returns
    -------
    oseo.GetStatusResponse
        The response GetStatusResponse instance

    """

    records = []
    if request.orderId is not None:  # 'order retrieve' type of request
        try:
            order = models.Order.objects.get(id=int(request.orderId))
            if order.user == user:
                records.append(order)
            else:
                raise errors.AuthorizationFailedError(locator="orderId")
        except (models.Order.DoesNotExist, ValueError):
            raise errors.InvalidOrderIdentifierError()
    else:  # 'order search' type of request
        records = find_orders(
            user,
            last_update=request.filteringCriteria.lastUpdate,
            last_update_end=request.filteringCriteria.lastUpdateEnd,
            statuses=[
                status for status in request.filteringCriteria.orderStatus],
            order_reference=request.filteringCriteria.orderReference
        )
    response = generate_get_status_response(records, request.presentation)
    return response
