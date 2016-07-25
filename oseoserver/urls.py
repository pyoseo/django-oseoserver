from __future__ import absolute_import
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r"^$", views.oseo_endpoint, name="oseo_endpoint"),
    url(
        "^orders/(?P<user_name>\w+)/"
        "order_(?P<order_id>\d+)/"
        "(?P<item_id>\w+)/"
        "(?P<file_name>[\w.]+)/$",
        views.get_ordered_file,
        name="get_ordered_file"
    ),
]
