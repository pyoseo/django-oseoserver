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
from pyxb import BIND
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.ows_2_0 as ows

from .. import server
from .. import settings

logger = logging.getLogger(__name__)


def get_capabilities(request, user):
    """Implements the OSEO GetCapabilities operation.

    Please refer to section 8. GetCapabilities operation of the OSEO
    standard for more details on this operation.

    Parameters
    ----------

    request: oseo.GetCapabilities
        The incoming request
    user: django.contrib.auth.User
        The django user that placed the request

    Returns
    -------
    oseo.Capabilities
        The response Capabilities instance

    """

    # parse the GetCapabilities request
    # here we just provide a standard response
    caps = oseo.Capabilities(version=server.OseoServer.OSEO_VERSION)
    caps.ServiceIdentification = build_service_identification()
    caps.ServiceProvider = build_service_provider()
    caps.OperationsMetadata = build_operations_metadata()
    caps.Contents = build_contents()
    caps.Notifications = build_notifications()
    return caps


def build_service_identification():
    return None  # not implemented yet


def build_service_provider():
    return None  # not implemented yet


def build_operations_metadata():
    op_meta = ows.OperationsMetadata()
    for op_name in server.OseoServer.OPERATION_CALLABLES.keys():
        op = ows.Operation(name=op_name)
        op.DCP.append(BIND())
        op.DCP[0].HTTP = BIND()
        op.DCP[0].HTTP.Post.append(BIND())
        op.DCP[0].HTTP.Post[0].href = "http://{}{}".format(
            settings.get_site_domain(), reverse("oseo_endpoint"))
        op_meta.Operation.append(op)
    return op_meta


def build_contents():
    product_order_type = settings.get_product_order()
    subscription_order_type = settings.get_subscription_order()
    tasking_order_type = settings.get_tasking_order()
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
            maxNumberOfProducts=settings.get_max_order_items(),
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
    for collection in settings.get_collections():
        c = oseo.CollectionCapability(
            collectionId=collection["collection_identifier"],
            ProductOrders=BIND(
                supported=collection.get(
                    "product_order",
                    {"enabled": False})["enabled"]),
            SubscriptionOrders=BIND(
                supported=collection.get("subscription_order",
                                         {"enabled": False})["enabled"]),
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


def build_notifications():
    # caps.Notifications = swes.NotificationProducerMetadataPropertyType()
    return None
