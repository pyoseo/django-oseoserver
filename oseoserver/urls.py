from __future__ import absolute_import
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r"^$", views.oseo_endpoint, name="oseo_endpoint"),
]
