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
Implements the OSEO GetStatus operation
"""

from __future__ import absolute_import
import re
import datetime as dt
import logging

import pyxb.bundles.opengis.oseo_1_0 as oseo

from .. import models
from .. import errors
from .. import constants

logger = logging.getLogger(__name__)


class GetStatus(object):

    SUCCESS = "success"

    def __call__(self, request, user):
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
                    raise errors.OseoError('AuthorizationFailed',
                                           'The client is not authorized to '
                                           'call the operation',
                                           locator='orderId')
            except (models.Order.DoesNotExist, ValueError):
                raise errors.OseoError('InvalidOrderIdentifier',
                                       'Invalid value for order',
                                       locator=request.orderId)
        else:  # 'order search' type of request
            records = self._find_orders(
                user,
                last_update=request.filteringCriteria.lastUpdate,
                last_update_end=request.filteringCriteria.lastUpdateEnd,
                statuses=[constants.OrderStatus(s) for s in
                          request.filteringCriteria.orderStatus],
                order_reference=request.filteringCriteria.orderReference
            )
        response = self._generate_get_status_response(records,
                                                      request.presentation)
        return response

    def _generate_get_status_response(self, records, presentation):
        """
        :arg records:
        :type records: either a one element list with a pyoseo.models.Order
                       or a django queryset, that will be evaluated to an
                       list of pyoseo.models.Order while iterating.
        :arg presentation:
        :type presentation: str
        """

        response = oseo.GetStatusResponse()
        response.status = self.SUCCESS
        for record in records:
            om = record.create_oseo_order_monitor(presentation)
            response.orderMonitorSpecification.append(om)
        return response

    def _find_orders(self, user, last_update=None, last_update_end=None,
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

        logger.debug("locals(): {}".format(locals()))
        records_qs = models.Order.objects.filter(user=user)
        if last_update is not None:
            records_qs = records_qs.filter(status_changed_on__gte=last_update)
        if last_update_end is not None:
            end = last_update_end.content()[0]
            if not isinstance(end, dt.datetime):
                m = re.search(r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?',
                              end)
                try:
                    ts = dt.datetime.strptime(m.group(), '%Y-%m-%dT%H:%M:%SZ')
                except ValueError:
                    ts = dt.datetime.strptime(m.group(), '%Y-%m-%d')
            else:
                ts = end
            records_qs = records_qs.filter(status_changed_on__lte=ts)
        if order_reference is not None:
            records_qs = records_qs.filter(reference=order_reference)
        if any(statuses or []):
            records_qs = records_qs.filter(
                status__in=[s.value for s in statuses])
        return records_qs
