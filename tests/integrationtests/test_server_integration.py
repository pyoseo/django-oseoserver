"""Integration tests for oseoserver.server"""

from django.contrib.auth import get_user_model
from lxml import etree
import pytest
from pyxb.bundles.opengis import oseo_1_0 as oseo
import pyxb.binding.datatypes as xsd
from pyxb import BIND

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
    @pytest.mark.skip
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

    @pytest.mark.django_db(transaction=True)
    def test_process_request_submit_product_order_disabled(self, settings):
        settings.OSEOSERVER_PRODUCT_ORDER = {
            "enabled": False,
            "automatic_approval": False,
            "notify_creation": True,
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor",
            "item_availability_days": 10,
        }

        request = oseo.Submit(
            service="OS",
            version="1.0.0",
            orderSpecification=oseo.OrderSpecification(
                orderReference="dummy reference",
                orderRemark="dummy remark",
                packaging="zip",
                option=[
                    BIND(oseo.ParameterData(encoding="XMLEncoding",
                                            values=xsd.anyType())),
                    BIND(
                        oseo.ParameterData(encoding="XMLEncoding",
                                           values=xsd.anyType())),
                ],
                deliveryOptions=oseo.deliveryOptions(
                    onlineDataAccess=BIND(
                        protocol="http"
                    )
                ),
                priority="STANDARD",
                orderType="PRODUCT_ORDER",
                orderItem=[
                    oseo.CommonOrderItemType(
                        itemId="dummy item id1",
                        productOrderOptionsId="dummy productorderoptionsid1",
                        orderItemRemark="dumm item remark1",
                        productId=oseo.ProductIdType(
                            identifier="dummy catalog identifier1")
                    ),
                ],
            ),
            statusNotification="None"
        )
        request = _add_request_options(
            request,
            ("oseo:orderSpecification/oseo:option[1]/oseo:ParameterData/"
            "oseo:values"),
            format="fake format"
        )
        request_data = etree.fromstring(request.toxml(encoding="utf-8"))
        server = OseoServer()
        fake_user = None
        response_element = server.process_request(request_data, fake_user)
        root_tag = etree.QName(response_element.tag)
        assert root_tag.localname == "Capabilities"
        assert root_tag.namespace == constants.NAMESPACES["oseo"]


def _add_request_options(request, xpath_expression, **options):
    """Add options to Submit requests

    This function exists in order to overcome dificulties with adding
    arbitrary XML elements using pyxb.

    """

    request_element = etree.fromstring(request.toxml())
    items = request_element.xpath(xpath_expression,
                                  namespaces=constants.NAMESPACES)
    for item in items:
        for option_name, option_value in options.items():
            option_element = etree.SubElement(item, option_name)
            option_element.text = option_value
    request_oseo = oseo.CreateFromDocument(etree.tostring(request_element))
    return request_oseo
