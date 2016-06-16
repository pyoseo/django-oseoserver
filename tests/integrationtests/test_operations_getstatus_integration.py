"""Integration tests for oseoserver.operations.getstatus"""

from lxml import etree
import pytest
from pyxb import BIND
from pyxb.bundles.opengis import oseo_1_0 as oseo
from pyxb.binding import datatypes as xsd
from pyxb.binding import basis
from pyxb import namespace

from oseoserver import constants
from oseoserver import errors
from oseoserver import models
from oseoserver.operations import getstatus

pytestmark = pytest.mark.integration


class TestGetStatusOperation(object):

    def test_get_status_no_orders(self, admin_user):
        request = oseo.GetStatus(
            service="OS",
            version="1.0.0",
            presentation=constants.Presentation.BRIEF.value,
            orderId="fake"
        )
        op = getstatus.GetStatus()
        with pytest.raises(errors.OseoError):
            op(request, admin_user)


    def test_get_status_order_id(self, admin_user):
        test_order = models.ProductOrder(
            status=constants.OrderStatus.SUBMITTED.value,
            user=admin_user,
            order_type=constants.OrderType.PRODUCT_ORDER.value,
            status_notification=constants.StatusNotification.FINAL.value
        )
        test_order.save()
        request = oseo.GetStatus(
            service="OS",
            version="1.0.0",
            presentation=constants.Presentation.BRIEF.value,
            orderId=str(test_order.pk)
        )
        op = getstatus.GetStatus()
        result = op(request, admin_user)
        print("result: {}".format(result))
        assert 0
