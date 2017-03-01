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

"""Implements the OSEO GetOptions operation"""

import logging

import pyxb
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.swe_2_0 as swe

from ..models import Order
from .. import settings
from .. import utilities

logger = logging.getLogger(__name__)


def create_oseo_order_options(collection, order_type):
    collection_config = utilities.get_collection_settings(
        collection_id=collection)
    order_options = oseo.CommonOrderOptionsType(
        productOrderOptionsId=".".join((order_type,
                                        collection_config["name"])),
        description="Options for submitting orders of type {!r} for "
                    "collection {!r} ".format(order_type, collection),
        orderType=order_type
    )
    for option in collection_config[order_type.lower()]["options"]:
        data_record = create_swe_data_record(option)
        order_options.option.append(
            pyxb.BIND(AbstractDataComponent=data_record))
    delivery_options = order_options.productDeliveryOptions
    data_access_options = settings.get_online_data_access_options()
    if any(data_access_options):
        delivery_options.append(pyxb.BIND(onlineDataAccess=pyxb.BIND()))
        for data_access_option in data_access_options:
            delivery_options[-1].onlineDataAccess.append(
                oseo.ProtocolType(data_access_option["protocol"]))
    data_delivery_options = settings.get_online_data_delivery_options()
    if any(data_delivery_options):
        delivery_options.append(pyxb.BIND(onlineDataDelivery=pyxb.BIND()))
        for data_delivery_option in data_delivery_options:
            delivery_options[-1].onlineDataDelivery.append(
                oseo.ProtocolType(data_delivery_option["protocol"]))
    media_delivery_options = settings.get_media_delivery_options()
    if any(media_delivery_options["media"]):
        delivery_options.append(pyxb.BIND(mediaDelivery=pyxb.BIND()))
        for medium_options in media_delivery_options["media"]:
            delivery_options[-1].mediaDelivery.append(
                oseo.PackageMedium(medium_options["type"].value))
    return order_options


def create_swe_data_record(option_name):
    option_config = utilities.get_processing_option_settings(option_name)
    data_record = swe.DataRecord()
    data_record.field.append(pyxb.BIND())
    data_record.field[0].name = option_name
    category = swe.Category(updatable=False)
    category.optional = True
    #cat.definition = 'http://geoland2.meteo.pt/ordering/def/%s' % \
    #        option.name
    #cat.identifier = option.name
    #cat.description = _n(option.description)
    choices = option_config.get("choices", [])
    if any(choices):
        category.constraint = pyxb.BIND()
        allowed_tokens = swe.AllowedTokens()
        for choice in choices:
            allowed_tokens.value_.append(choice)
        category.constraint.append(allowed_tokens)
    data_record.field[0].append(category)
    return data_record


# TODO - Implement retrieval of options for subscription orders
def get_options(request, user):
    """Implements the OSEO GetOptions operation.

    Parameters
    ----------
    request: pyxb.bundles.opengis.raw.oseo.OrderOptionsRequestType
        The instance with the request parameters
    user: django.contrib.auth.models.User
        User making the request

    Returns
    -------
    oseo.GetOptionsResponse:
        The response object

    """

    response = oseo.GetOptionsResponse(status="success")
    if request.collectionId is not None:
        product_order_options = create_oseo_order_options(
            collection=request.collectionId,
            order_type=Order.PRODUCT_ORDER
        )
        subscription_order_options = create_oseo_order_options(
            collection=request.collectionId,
            order_type=Order.SUBSCRIPTION_ORDER
        )
        for order_option in (product_order_options,
                             subscription_order_options):
            if order_option is not None:
                response.orderOptions.append(order_option)
    elif any(request.identifier):
        # retrieve the products from the catalogue using the identifier
        # assess their collection and return the collection options
        raise NotImplementedError
    else:  # tasking request id
        raise NotImplementedError
    return response


