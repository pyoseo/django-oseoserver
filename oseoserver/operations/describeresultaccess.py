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
Implements the OSEO DescribeResultAccess operation
"""

import logging
import datetime as dt

from django.core.exceptions import ObjectDoesNotExist
import pyxb
import pyxb.bundles.opengis.oseo_1_0 as oseo

from oseoserver import models
from oseoserver import errors
from oseoserver.operations.base import OseoOperation

logger = logging.getLogger(__name__)

class DescribeResultAccess(OseoOperation):

    def __call__(self, request, user, **kwargs):
        """Implements the OSEO DescribeResultAccess operation.

        This operation returns the location of the order items that are 
        ready to be downloaded by the user.

        The DescribeResultAccess operation only reports on the availability
        of order items that specify onlineDataAccess as their delivery option.

        :arg request: The instance with the request parameters
        :type request: pyxb.bundles.opengis.raw.oseo.OrderOptionsRequestType
        :arg user: User making the request
        :type user: oseoserver.models.OseoUser
        :arg user_password: Password of the user making the request
        :type user_password: str
        :return: The DescribeResultAccess response object and the HTTP status
                 code
        :rtype: tuple(pyxb.bundles.opengis.oseo.DescribeResultAccessResponse,
                int)
        """

        status_code = 200
        try:
            order = models.Order.objects.get(id=request.orderId)
        except ObjectDoesNotExist:
            raise errors.InvalidOrderIdentifierError()
        if not self._user_is_authorized(user, order):
            raise errors.AuthorizationFailedError()
        completed_files = self.get_order_completed_files(order,
                                                         request.subFunction)
        logger.info('completed_files: {}'.format(completed_files))
        order.last_describe_result_access_request = dt.datetime.utcnow()
        order.save()
        response = oseo.DescribeResultAccessResponse(status='success')

        item_id = None
        if len(completed_files) == 1 and order.packaging == models.Order.ZIP:
            item_id = "Packaged order items"
        for oseo_file, delivery in completed_files:
            item = oseo_file.order_item
            iut = oseo.ItemURLType()
            iut.itemId = item_id if item_id is not None else item.item_id
            iut.productId = oseo.ProductIdType(
                identifier=item.identifier,
                )
            iut.productId.collectionId = item.collection.collection_id
            iut.itemAddress = oseo.OnLineAccessAddressType()
            iut.itemAddress.ResourceAddress = pyxb.BIND()
            iut.itemAddress.ResourceAddress.URL = oseo_file.url
            iut.expirationDate = oseo_file.expires_on
            response.URLs.append(iut)
        return response, status_code, None

    def get_order_completed_files(self, order, behaviour):
        """
        Get the completed files for product orders.

        :arg order:
        :type order: oseoserver.models.Order
        :arg behaviour: Either 'allReady' or 'nextReady', as defined in the 
                        OSEO specification
        :type behaviour: str
        :return: a list with the completed order items for this order
        :rtype: [(models.OseoFile, models.DeliveryOption)]
        """

        batches = []
        if order.order_type.name == models.Order.PRODUCT_ORDER:
            batches = order.batches.all()
        elif order.order_type.name == models.Order.SUBSCRIPTION_ORDER:
            batches = order.batches.all()[1:]
        all_complete = []
        for b in batches:
            #batch_complete = self.get_batch_completed_files(b, behaviour)
            batch_complete = b.get_completed_files(behaviour)
            all_complete.extend(batch_complete)
        return all_complete

