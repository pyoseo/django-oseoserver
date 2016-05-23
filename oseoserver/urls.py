from __future__ import absolute_import
from django.conf.urls import patterns, url, include
#from tastypie.api import Api  # tastypie?

from . import views
#import oseoserver.api.resources

#v1_api = Api(api_name="v1")
#v1_api.register(oseoserver.api.resources.SubscriptionBatchResource())
#v1_api.register(oseoserver.api.resources.SubscriptionOrderResource())
#v1_api.register(oseoserver.api.resources.CollectionResource())
#v1_api.register(oseoserver.api.resources.OseoFileResource())
#v1_api.register(oseoserver.api.resources.UserResource())

urlpatterns = patterns(
    '',
    url(r'^$', views.oseo_endpoint, name='oseo_endpoint'),
    #url(r'^api/', include(v1_api.urls)),
    url('^orders/(?P<user_name>\w+)/order_(?P<order_id>\d+)/(?P<item_id>\w+)/'
        #'(?P<file_name>\w+\.?\w+)/$', views.get_ordered_file,
        '(?P<file_name>[\w.]+)/$', views.get_ordered_file,
        name='get_ordered_file'),
    url('^orders/(?P<user_name>\w+)/order_(?P<order_id>\d+)/'
        '(?P<package_name>\w+\.?\w+)/$', views.get_ordered_packaged_files,
        name='get_ordered_packaged_files'),
)
