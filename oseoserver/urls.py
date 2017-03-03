from __future__ import absolute_import

from django.conf.urls import url
from django.conf.urls import include
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view

from . import views

router = DefaultRouter()
router.register(r"subscription", views.SubscriptionOrderViewSet)
router.register(r"subscriptionbatch", views.SubscriptionBatchViewSet)

schema_view = get_schema_view(title="oseoserver extra API")

urlpatterns = [
    url(r"^$", views.oseo_endpoint, name="oseo_endpoint"),
    url(r"^api/", include(router.urls)),
    url(r"^schema/$", schema_view),
    url(r"^api-auth/", include("rest_framework.urls",
                               namespace="rest_framework")),
]
