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
"""Implements the OSEO DescribeResultAccess operation"""

from __future__ import absolute_import
import logging
import datetime as dt

from django.core.exceptions import ObjectDoesNotExist
import pytz
import pyxb
import pyxb.bundles.opengis.oseo_1_0 as oseo

from .. import errors
from .. import models
from ..models import Order
from .. import utilities

logger = logging.getLogger(__name__)


def describe_result_access(request, user):
    """Implements the OSEO DescribeResultAccess operation.

    This operation returns the location of the order items that are
    ready to be downloaded by the user.

    The DescribeResultAccess operation only reports on the availability
    of order items that specify onlineDataAccess as their delivery option.

    Parameters
    ----------
    request: oseo.DescribeResultAccess
        The incoming request
    user: django.contrib.auth.User
        The django user that placed the request

    Returns
    -------
    response: oseo.SubmitAck
        The response SubmitAck instance

    """

    try:
        order = Order.objects.get(id=request.orderId)
    except ObjectDoesNotExist:
        raise errors.InvalidOrderIdentifierError()
    if order.user != user:
        raise errors.AuthorizationFailedError
    completed_items = get_order_completed_items(order, request.subFunction)
    logger.debug("completed_items: {}".format(completed_items))
    order.last_describe_result_access_request = dt.datetime.now(pytz.utc)
    order.save()
    response = oseo.DescribeResultAccessResponse(status='success')

    item_id = None
    for item in completed_items:
        iut = oseo.ItemURLType()
        iut.itemId = item_id or item.item_specification.item_id
        iut.productId = oseo.ProductIdType(
            identifier=item.identifier,
            )
        iut.productId.collectionId = utilities.get_collection_identifier(
            item.item_specification.collection)
        iut.itemAddress = oseo.OnLineAccessAddressType()
        iut.itemAddress.ResourceAddress = pyxb.BIND()
        iut.itemAddress.ResourceAddress.URL = item.url
        iut.expirationDate = item.expires_on
        response.URLs.append(iut)
    return response


def get_order_completed_items(order, behaviour):
    """Get the completed order items for product orders.

    Parameters
    ----------
    order: oseoserver.models.Order
        The order for which completed items are to be returned
    behaviour: str
        Either 'allReady' or 'nextReady', as defined in the OSEO
        specification

    Returns
    --------
    list
        The completed order items for this order

    """

    batches = order.batches.all()
    all_complete = []
    for batch in batches:
        complete_items = get_batch_completed_items(batch, behaviour)
        all_complete.extend(complete_items)
    return all_complete


def get_batch_completed_items(batch, behaviour):
    last_time = batch.order.last_describe_result_access_request
    list_all_items = last_time is None or behaviour == batch.ALL_READY
    order_delivery = batch.order.selected_delivery_option.delivery_type
    batch_complete_items = []
    queryset = batch.order_items.filter(
        status=batch.order.COMPLETED
    ).order_by("item_specification__id")
    for item in queryset:
        item_spec = item.item_specification
        try:
            delivery = (
                item_spec.selected_delivery_option.delivery_type)
        except models.ItemSpecificationDeliveryOption.DoesNotExist:
            delivery = order_delivery
        if delivery != models.BaseDeliveryOption.ONLINE_DATA_ACCESS:
            # describeResultAccess only applies to items that specify
            # 'onlinedataaccess' as delivery type
            logger.debug(
                "item {} does not specify onlinedataaccess as its "
                "delivery type, skipping item...".format(item)
            )
            continue
        completed_since_last = (item.completed_on is None or
                                last_time is None or
                                item.completed_on >= last_time)
        list_this_item = (
            behaviour == batch.NEXT_READY and completed_since_last)
        if list_all_items or list_this_item:
            batch_complete_items.append(item)
    return batch_complete_items
