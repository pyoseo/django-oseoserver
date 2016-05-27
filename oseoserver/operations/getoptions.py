# Copyright 2014 Ricardo Garcia Silva
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
Implements the OSEO GetOptions operation
"""

import logging

from django.core.exceptions import ObjectDoesNotExist
import pyxb
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.swe_2_0 as swe

from oseoserver import models
from oseoserver import errors
from oseoserver.utilities import _n
from oseoserver.operations.base import OseoOperation

logger = logging.getLogger(__name__)


# TODO - Implement retrieval of options for subscription orders
class GetOptions(OseoOperation):

    def __call__(self, request, user, **kwargs):
        """
        Implements the OSEO GetOptions operation.


        :arg request: The instance with the request parameters
        :type request: pyxb.bundles.opengis.raw.oseo.OrderOptionsRequestType
        :arg user: User making the request
        :type user: oseoserver.models.OseoUser
        :return: The XML response object
        :rtype: str
        """

        response = oseo.GetOptionsResponse(status="success")
        if any(request.identifier):  # product identifier query
            # retrieve the products from the catalogue using the identifier
            # assess their collection and return the collection options
            raise NotImplementedError
        elif request.collectionId is not None:  # product or collection query
            try:
                collection = models.Collection.objects.get(
                    collection_id=request.collectionId)
                product_order_options = self.create_oseo_order_options(
                    collection, user, models.Order.PRODUCT_ORDER)
                subscription_order_options = self.create_oseo_order_options(
                    collection, user, models.Order.SUBSCRIPTION_ORDER)
                for order_option in (product_order_options,
                                     subscription_order_options):
                    if order_option is not None:
                        response.orderOptions.append(order_option)
            except models.Collection.DoesNotExist():
                raise errors.UnsupportedCollectionError()
        elif request.taskingRequestId is not None:
            raise NotImplementedError
        return response, None

    def create_oseo_order_options(self, collection, user, order_type_name):
        group = user.oseo_group
        valid, order_config = self._validate_collection_user(collection, user,
                                                             order_type_name)
        oo = None
        if valid:
            options_id = "{} {}".format(order_type_name, collection.name)
            description = ("Options for submitting orders of type {} for "
                           "the {} collection".format(order_type_name,
                                                      collection.name))
            oo = oseo.CommonOrderOptionsType(productOrderOptionsId=options_id,
                                             description=description,
                                             orderType=order_type_name)
            for option in order_config.options.all():
                data_record = self._create_swe_data_record(option)
                oo.option.append(pyxb.BIND(AbstractDataComponent=data_record))
            access, delivery, package = self._extract_delivery_options(
                order_config)
            if any(access):
                self._create_delivery_options_element(oo, "online_data_access",
                                                      access)
            if any(delivery):
                self._create_delivery_options_element(oo,
                                                      "online_data_delivery",
                                                      delivery)
            if any(package):
                self._create_delivery_options_element(oo, "media_delivery",
                                                      package)
        return oo

    def _validate_collection_user(self, col, user, order_type_name):
        """

        :param col: the collection
        :param user:
        :param order_type_name:
        :return:
        """
        group = user.oseo_group
        oc = None
        result = True
        if not group.collection_set.filter(id=col.id).exists():
            # the collection cannot be ordered by this user
            result = False
        if order_type_name == models.Order.PRODUCT_ORDER:
            oc = col.productorderconfiguration.orderconfiguration_ptr
            if not oc.enabled:
                result = False
        elif order_type_name == models.Order.SUBSCRIPTION_ORDER:
            oc = col.subscriptionorderconfiguration.orderconfiguration_ptr
            if not oc.enabled:
                result = False
        return result, oc

    def _extract_delivery_options(self, order_configuration):
        data_access = []
        data_delivery = []
        package_media = []
        for del_opt in order_configuration.delivery_options.all():
            try:
                p = del_opt.onlinedataaccess.protocol
                data_access.append(p)
            except models.OnlineDataAccess.DoesNotExist:
                try:
                    p = del_opt.onlinedatadelivery.protocol
                    data_delivery.append(p)
                except models.OnlineDataDelivery.DoesNotExist:
                    m = del_opt.mediadelivery.package_medium
                    package_media.append(m)
        return data_access, data_delivery, package_media

    def _create_delivery_options_element(self, common_order_options_element,
                                         delivery_option, contents):
        p = common_order_options_element.productDeliveryOptions
        if delivery_option == "online_data_access":
            p.append(pyxb.BIND(onlineDataAccess=pyxb.BIND()))
            for item in contents:
                p[-1].onlineDataAccess.append(oseo.ProtocolType(item))
        elif delivery_option == "online_data_delivery":
            p.append(pyxb.BIND(onlineDataDelivery=pyxb.BIND()))
            for item in contents:
                p[-1].onlineDataDelivery.append(oseo.ProtocolType(item))
        elif delivery_option == "media_delivery":
            p.append(pyxb.BIND(mediaDelivery=pyxb.BIND()))
            for item in contents:
                p[-1].mediaDelivery.append(oseo.PackageMedium(item))

    def _create_swe_data_record(self, option):
        dr = swe.DataRecord()
        dr.field.append(pyxb.BIND())
        dr.field[0].name = option.name
        cat = swe.Category(updatable=False)
        cat.optional = True
        #cat.definition = 'http://geoland2.meteo.pt/ordering/def/%s' % \
        #        option.name
        #cat.identifier = option.name
        #cat.description = _n(option.description)
        choices = option.choices.all()
        if any(choices):
            cat.constraint = pyxb.BIND()
            at = swe.AllowedTokens()
            for choice in choices:
                at.value_.append(choice.value)
            cat.constraint.append(at)
        dr.field[0].append(cat)
        return dr

