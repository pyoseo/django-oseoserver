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

import re
import datetime as dt

import pyxb.bundles.opengis.oseo_1_0 as oseo

from oseoserver import models
from oseoserver import errors
from oseoserver.operations.base import OseoOperation


class GetStatus(OseoOperation):

    SUCCESS = "success"
    FULL_PRESENTATION = "full"

    def __call__(self, request, user, **kwargs):
        """Implements the OSEO Getstatus operation.

        See section 14 of the OSEO specification for details on the
        Getstatus operation.

        :arg request: The instance with the request parameters
        :type request: pyxb.bundles.opengis.raw.oseo.GetStatusRequestType
        :arg user: User making the request
        :type user: oseoserver.models.OseoUser
        :return: The XML response object
        :rtype: str
        """

        records = []
        if request.orderId is not None:  # 'order retrieve' type of request
            try:
                order = models.Order.objects.get(id=int(request.orderId))
                if self._user_is_authorized(user, order):
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
            records = self._find_orders(request, user)
        response = self._generate_get_status_response(records,
                                                      request.presentation)
        return response, None

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
        for r in records:
            om = r.create_oseo_order_monitor(presentation)
            response.orderMonitorSpecification.append(om)
        return response

    def _find_orders(self, request, user):
        """
        Find orders that match the request's filtering criteria
        """

        records = models.Order.objects.filter(user=user)
        if request.filteringCriteria.lastUpdate is not None:
            lu = request.filteringCriteria.lastUpdate
            records = records.filter(status_changed_on__gte=lu)
        if request.filteringCriteria.lastUpdateEnd is not None:
            # workaround for a bug in the oseo.xsd that does not
            # assign a dateTime type to the lastUpdateEnd element
            lue = request.filteringCriteria.lastUpdateEnd.toxml()
            m = re.search(r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?', lue)
            try:
                ts = dt.datetime.strptime(m.group(), '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                ts = dt.datetime.strptime(m.group(), '%Y-%m-%d')
            records = records.filter(status_changed_on__lte=ts)
        if request.filteringCriteria.orderReference is not None:
            ref = request.filteringCriteria.orderReference
            records = records.filter(reference=ref)
        statuses = [s for s in request.filteringCriteria.orderStatus]
        if any(statuses):
            records = records.filter(status__in=statuses)
        return records
