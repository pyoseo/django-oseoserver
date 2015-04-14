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

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
import pyxb
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.swe_2_0 as swe

from oseoserver import models
from oseoserver import errors
from oseoserver.utilities import _n
from oseoserver.operations.base import OseoOperation

# TODO - Implement retrieval of options for subscription orders
class GetOptions(OseoOperation):

    def __call__(self, request, user, **kwargs):
        """
        Implements the OSEO GetOptions operation.


        :arg request: The instance with the request parameters
        :type request: pyxb.bundles.opengis.raw.oseo.OrderOptionsRequestType
        :arg user: User making the request
        :type user: oseoserver.models.OseoUser
        :return: The XML response object and the HTTP status code
        :rtype: tuple(str, int)

        Example for creating an option with pyxb:

        from lxml import etree
        import pyxb
        import pyxb.bundles.opengis.swe_2_0 as swe
        at = swe.AllowedTokens()
        at.value_.append('ATS_NL_0P')
        at.value_.append('ATS_TOA_1P')
        c = swe.Category(updatable=False)
        c.optional = True
        c.definition = 'http://www.opengis.net/def/parameter/ESA/1.0/productType'
        c.identifier = 'ProductType'
        c.description = 'Processing for ENVISAT ATS'
        c.constraint = pyxb.BIND()
        c.constraint.append(at)
        dr = swe.DataRecord()
        dr.field.append(pyxb.BIND())
        dr.field[0].name = 'ProductType'
        dr.field[0].append(c)
        print(etree.tostring(etree.fromstring(dr.toxml()), encoding='utf-8', pretty_print=True))
        """

        status_code = 200
        if any(request.identifier):  # product identifier query
            # retrieve the products from the catalogue using the identifier
            # assess their collection and return the collection options
            raise NotImplementedError
        elif request.collectionId is not None:  # product or collection query
            try:
                collection = models.Collection.objects.get(
                    collection_id=request.collectionId)
                response = oseo.GetOptionsResponse(status='success')
                for ot in (models.OrderType.PRODUCT_ORDER,
                           models.OrderType.SUBSCRIPTION_ORDER):
                    available_options = self.get_applicable_options(
                        request.collectionId,
                        ot
                    )
                    av_delivery_opts = models.DeliveryOption.objects.filter(
                        deliveryoptionordertype__order_type__name=ot
                    )
                    for group in models.OptionGroup.objects.all():
                        order_opts = self._get_order_options(
                            group,
                            available_options,
                            av_delivery_opts,
                            ot
                        )
                        response.orderOptions.append(order_opts)
            except ObjectDoesNotExist:
                raise errors.InvalidCollectionError()
        elif request.taskingRequestId is not None:
            raise NotImplementedError
        return response, status_code

    def create_oseo_order_options_product(self, collection, user):
        order_type = models.Order.PRODUCT_ORDER
        group = user.oseo_group
        if group.collection_set.filter(id=collection.id).exists():
            oc = collection.productorderconfiguration.orderconfiguration_ptr
            if oc.enabled:
                options_id = "{} {}".format(order_type, collection.name)
                description = ("Options for submitting orders of type {} for "
                               "the {} collection".format(order_type,
                                                          collection.name))
                oo = oseo.CommonOrderOptionsType(
                    productOrderOptionsId=options_id,
                    description=description,
                    orderType=order_type
                )
                access, delivery, package = self._extract_delivery_options(oc)
                if any(access):
                    self._create_delivery_options_element(
                        oo, "online_data_access", access)
                if any(delivery):
                    self._create_delivery_options_element(
                        oo, "online_data_delivery",
                        delivery
                    )
                if any(package):
                    self._create_delivery_options_element(oo, "media_delivery",
                                                          package)
                # implement paymentOptions
                # implement sceneSelectionOptions
            else:
                # this collection does not allow product orders
                raise errors.InvalidCollectionError
        else:
            # the collection cannot be ordered by this user
            raise errors.InvalidCollectionError

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
        if delivery_option == "online_data_acess":
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

