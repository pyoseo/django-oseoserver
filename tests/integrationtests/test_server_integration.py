"""Integration tests for oseoserver.server"""

from django.contrib.auth import get_user_model
from lxml import etree
import pytest
from pyxb.bundles.opengis import oseo_1_0 as oseo

from oseoserver.server import OseoServer
from oseoserver import errors
from oseoserver import constants
from oseoserver import models


@pytest.mark.integration
class TestServer(object):

    def test_process_request_get_capabilities(self):
        """GetCapabilities requests are processed OK."""
        fake_user = None
        get_caps = oseo.GetCapabilities(service="OS")
        request = get_caps.toxml(encoding="utf-8")
        request_data = etree.fromstring(request)
        server = OseoServer()
        response_element = server.process_request(request_data, fake_user)
        root_tag = etree.QName(response_element.tag)
        assert root_tag.localname == "Capabilities"
        assert root_tag.namespace == constants.NAMESPACES["oseo"]

    def test_process_request_get_status_invalid_order_id(self):
        """Getstatus with an invalid order id raises the proper error"""
        fake_user = None
        fake_order_id = "fake"
        presentation = "brief"
        get_status = oseo.GetStatus(
            service="OS",
            version="1.0.0",
            orderId=fake_order_id,
            presentation=presentation
        )
        request = get_status.toxml(encoding="utf-8")
        request_data = etree.fromstring(request)
        server = OseoServer()
        with pytest.raises(errors.OseoError) as excinfo:
            server.process_request(request_data, fake_user)
        assert excinfo.value.code == "InvalidOrderIdentifier"

    @pytest.mark.django_db(transaction=True)
    def test_process_request_get_status_valid_order_id(self):
        UserModel = get_user_model()
        test_user = UserModel.objects.create_user("test_user",
                                                  "fake.email@dummy")
        test_option = models.Option(name="test_option")
        test_option.choices.add(models.OptionChoice(value="choice1"),
                                bulk=False)
        test_delivery_optin = models.DeliveryOption()
        test_order = models.ProductOrder(
            status=constants.OrderStatus.SUBMITTED.value,
            #additional_status_info
            #mission_specific_status_info
            #remark
            user=test_user,
            order_type=constants.OrderType.PRODUCT_ORDER.value,
            #reference
            #packaging
            #priority
            #status_notification
        )
        test_order.save()
