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

from datetime import datetime

from tastypie.resources import ModelResource
from tastypie.authentication import ApiKeyAuthentication
from tastypie.authorization import DjangoAuthorization
from tastypie import fields
from tastypie.constants import ALL, ALL_WITH_RELATIONS

from oseoserver import models
import oseoserver.server


class OseoFileResource(ModelResource):

    class Meta:
        queryset = models.OseoFile.objects.all()
        allowed_methods = ["get", "put"]
        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()
        filtering = {
            "url": ALL,
            "last_downloaded_at": ALL,
            }


class SubscriptionOrderResource(ModelResource):

    class Meta:
        queryset = models.SubscriptionOrder.objects.all()
        allowed_methods = ["get", "post"]
        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()
        filtering = {
            "status": ALL,
            "id": ALL,
            "begin_on": ALL,
            "end_on": ALL,
        }


class CollectionResource(ModelResource):

    class Meta:
        queryset = models.Collection.objects.all()
        allowed_methods = ["get", "post"]
        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()
        filtering = {
            "name": ALL,
            "id": ALL,
        }


# TODO - Add a field that shows a batch's status
# TODO - Decide on how to handle HTTP PUT and PATCH (if at all)
class SubscriptionBatchResource(ModelResource):
    order = fields.ForeignKey(SubscriptionOrderResource, "order")
    collection = fields.ForeignKey(CollectionResource, "collection")

    class Meta:
        queryset = models.SubscriptionBatch.objects.all()
        allowed_methods = ["get", "post"]
        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()
        filtering = {
            "order": ALL_WITH_RELATIONS,
            }

    def obj_create(self, bundle, **kwargs):
        """Create a subscription bath and place it in the processing queue

        This method reimplements the one in its base class in order
        to use the `oseoserver.server.Oseoserver.dispatch_subscription()`
        method.

        :param bundle:
        :param kwargs:
        :return:
        """

        bundle = self.full_hydrate(bundle)
        collection_uri = bundle.data["collection"]
        collection_resource = CollectionResource()
        collection = collection_resource.get_via_uri(collection_uri,
                                                     request=bundle.request)
        order_uri = bundle.data["order"]
        order_resource = SubscriptionOrderResource()
        order = order_resource.get_via_uri(order_uri, request=bundle.request)
        timeslot = datetime.strptime(bundle.data["timeslot"],
                                     "%Y-%m-%dT%H:%M:%S")
        s = oseoserver.server.OseoServer()
        s.process_subscription_orders(timeslot, collections=[collection.name],
                                      order_id=order.id)

