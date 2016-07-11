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

from __future__ import absolute_import
import logging
import datetime as dt

from django.core.exceptions import ObjectDoesNotExist
import pyxb
import pyxb.bundles.opengis.oseo_1_0 as oseo

from .. import errors
from .. import models
from ..utilities import get_collection_settings
from ..constants import OrderType

logger = logging.getLogger(__name__)


class DescribeResultAccess(object):

    def __call__(self, request, user):
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
            order = models.Order.objects.get(id=request.orderId)
        except ObjectDoesNotExist:
            raise errors.InvalidOrderIdentifierError()
        # TODO: Authorization should be handled by Django instead
        if order.user != user:
            raise errors.AuthorizationFailedError
        completed_items = self.get_order_completed_items(order,
                                                         request.subFunction)
        logger.debug('completed_items: {}'.format(completed_items))
        order.last_describe_result_access_request = dt.datetime.utcnow()
        order.save()
        response = oseo.DescribeResultAccessResponse(status='success')

        item_id = None
        if len(completed_items) == 1 and order.packaging == models.Order.ZIP:
            item_id = "Packaged order items"
        for item in completed_items:
            iut = oseo.ItemURLType()
            iut.itemId = item_id if item_id is not None else item.item_id
            iut.productId = oseo.ProductIdType(
                identifier=item.identifier,
                )
            collection_settings = get_collection_settings(item.collection)
            iut.productId.collectionId = collection_settings[
                "collection_identifier"]
            iut.itemAddress = oseo.OnLineAccessAddressType()
            iut.itemAddress.ResourceAddress = pyxb.BIND()
            iut.itemAddress.ResourceAddress.URL = item.url
            iut.expirationDate = item.expires_on
            response.URLs.append(iut)
        return response

    def get_order_completed_items(self, order, behaviour):
        """
        Get the completed order items for product orders.

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

        batches = []
        if order.order_type == OrderType.PRODUCT_ORDER.value:
            batches = order.batches.all()
        elif order.order_type == OrderType.SUBSCRIPTION_ORDER.value:
            batches = order.batches.all()[1:]
        all_complete = []
        for b in batches:
            #batch_complete = self.get_batch_completed_files(b, behaviour)
            batch_complete = b.get_completed_items(behaviour)
            all_complete.extend(batch_complete)
        return all_complete

