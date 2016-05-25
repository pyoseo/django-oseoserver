# Copyright 2015 Ricardo Garcia Silva
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
Implements the OSEO GetCapabilities operation
"""

from __future__ import absolute_import
import logging

from django.core.urlresolvers import reverse
#from django.contrib.sites.models import Site
from pyxb import BIND
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.ows_2_0 as ows

from .. import server
from .. import settings
from .base import OseoOperation

logger = logging.getLogger(__name__)


class GetCapabilities(OseoOperation):

    def __call__(self, request, user, **kwargs):
        """Implements the OSEO GetCapabilities operation.

        Please refer to section 8. GetCapabilities operation of the OSEO
        standard for more details on this operation.

        :param request:
        :param user:
        :param user_password:
        :param kwargs:
        :return:
        """

        status_code = 200
        # parse the GetCapabilities request
        # here we just provide a standard response
        caps = oseo.Capabilities(version=server.OseoServer.OSEO_VERSION)
        caps.ServiceIdentification = self._build_service_identification()
        caps.ServiceProvider = self._build_service_provider()
        caps.OperationsMetadata = self._build_operations_metadata()
        caps.Contents = self._build_contents(user)
        caps.Notifications = self._build_notifications()
        return caps, status_code, None

    def _build_service_identification(self):
        return None  # not implemented yet

    def _build_service_provider(self):
        return None  # not implemented yet

    def _build_operations_metadata(self):
        op_meta = ows.OperationsMetadata()
        #domain = Site.objects.get_current().domain
        domain = settings.OSEOSERVER_SITE_DOMAIN
        for op_name in server.OseoServer.OPERATION_CLASSES.keys():
            op = ows.Operation(name=op_name)
            op.DCP.append(BIND())
            op.DCP[0].HTTP = BIND()
            op.DCP[0].HTTP.Post.append(BIND())
            op.DCP[0].HTTP.Post[0].href = "http://{}{}".format(
                domain, reverse("oseo_endpoint"))
            op_meta.Operation.append(op)
        return op_meta

    def _build_contents(self, user):
        product_order_type = settings.OSEOSERVER_PRODUCT_ORDER
        subscription_order_type = settings.OSEOSERVER_SUBSCRIPTION_ORDER
        tasking_order_type = settings.OSEOSERVER_TASKING_ORDER
        logger.debug("before creating OrderingServiceContentsType...")
        contents = oseo.OrderingServiceContentsType(
            ProductOrders=BIND(supported=product_order_type["enabled"]),
            SubscriptionOrders=BIND(
                supported=subscription_order_type["enabled"]),
            ProgrammingOrders=BIND(supported=tasking_order_type["enabled"]),
            GetQuotationCapabilities=BIND(supported=False,
                                          synchronous=False,
                                          asynchronous=False,
                                          monitoring=False,
                                          off_line=False),
            SubmitCapabilities=BIND(
                asynchronous=False,
                maxNumberOfProducts=settings.OSEOSERVER_MAX_ORDER_ITEMS,
                globalDeliveryOptions=True,
                localDeliveryOptions=True,
                globalOrderOptions=True,
                localOrderOptions=True
            ),
            GetStatusCapabilities=BIND(orderSearch=True,
                                       orderRetrieve=True,
                                       full=True),
            DescribeResultAccessCapabilities=BIND(supported=True),
            CancelCapabilities=BIND(supported=True,
                                    asynchronous=False),
        )
        logger.debug("before adding CollectionCapability...")
        for collection in settings.OSEOSERVER_COLLECTIONS:
            c = oseo.CollectionCapability(
                collectionId=collection["collection_identifier"],
                ProductOrders=BIND(
                    supported=collection["product_orders"]["enabled"]),
                SubscriptionOrders=BIND(
                    supported=collection["subscription_orders"]["enabled"]),
                DescribeResultAccessCapabilities=BIND(supported=True),
                CancelCapabilities=BIND(supported=True, asynchronous=False),
            )
            contents.SupportedCollection.append(c)
        contents.ContentsType.append(
            oseo.EncodingType(
                supportedEncoding=["XMLEncoding", "TextEncoding"]
            )
        )
        return contents

    def _build_notifications(self):
        # caps.Notifications = swes.NotificationProducerMetadataPropertyType()
        return None

