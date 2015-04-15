from django.conf.urls import patterns, url, include
from tastypie.api import Api

from oseoserver import views
import oseoserver.api.resources

v1_api = Api(api_name="v1")
v1_api.register(oseoserver.api.resources.SubscriptionBatchResource())
v1_api.register(oseoserver.api.resources.SubscriptionOrderResource())
v1_api.register(oseoserver.api.resources.CollectionResource())

urlpatterns = patterns(
    '',
    url(r'^server$', views.oseo_endpoint, name='oseo_endpoint'),
    url(r'^api/', include(v1_api.urls)),
)
