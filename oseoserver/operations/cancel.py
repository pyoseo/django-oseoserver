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

"""
Implements the OSEO Cancel operation
"""

import pyxb.bundles.opengis.oseo_1_0 as oseo

from oseoserver import models
from oseoserver import errors
from oseoserver.server import OseoServer

# TODO - Use the status_notification
def cancel(request, user, **kwargs):
    """Implements the OSEO Cancel operation.

    :param request:
    :param user:
    :param kwargs:
    :return:
    """

    try:
        order = models.Order.objects.get(id=request.orderId)
    except models.Order.DoesNotExist:
        raise errors.InvalidOrderIdentifierError()
    status_notification = validate_status_notification(request)
    s = OseoServer()
    if not _user_is_authorized(user, order):
        raise errors.AuthorizationFailedError()
    if order.order_type.name == models.Order.PRODUCT_ORDER:
        raise errors.ServerError("Cancellation of product orders is "
                                 "not implemented")
    elif order.order_type.name == models.Order.SUBSCRIPTION_ORDER:
        msg = "Subscription has been cancelled by user's request"
        s.moderate_order(order, False, rejection_details=msg)
    else:
        raise errors.ServerError("Cancellation of tasking orders is "
                                 "not implemented")
    response = oseo.CancelAck(status="success")
    return response, None
