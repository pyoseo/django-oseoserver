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

"""Implements the OSEO Cancel operation"""

import logging

import pyxb.bundles.opengis.oseo_1_0 as oseo

from ..models import Order
from .. import errors
from .. import requestprocessor

logger = logging.getLogger(__name__)


def cancel(request, user):
    """OSEO Cancel handler.

    Parameters
    ----------
    request: pyxb.bundles.opengis.oseo_1_0.Submit
        The request to process
    user: django.contrib.auth.models.User
        USer that has placed the request

    Returns
    -------
    response: pyxb.bundles.opengis.oseo_1_0.CancelAck
        OSEO response to be sent to the client

    """

    if request.statusNotification != Order.NONE:
        raise NotImplementedError("Status notifications are not supported")
    try:
        order = Order.objects.get(id=request.orderId)
    except Order.DoesNotExist:
        raise errors.InvalidOrderIdentifierError()
    if order.user != user:
        raise errors.AuthorizationFailedError()
    if order.order_type in (Order.MASSIVE_ORDER, Order.SUBSCRIPTION_ORDER):
        msg = ("Order {0.reference} has been cancelled "
               "by user request".format(order))
        logger.info(msg)
        requestprocessor.cancel_order(
            order=order,
            notify=True,
            notification_details=msg
        )
    elif order.order_type == Order.PRODUCT_ORDER:
        raise errors.ServerError(
            "Cancellation of product orders is not implemented")
    else:  # tasking order
        raise errors.ServerError("Cancellation of tasking orders is "
                                 "not implemented")
    return oseo.CancelAck(status="success")
