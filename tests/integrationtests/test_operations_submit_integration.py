"""Integration tests for oseoserver.operations.submit"""

from lxml import etree
import pytest
from pyxb import BIND
from pyxb.bundles.opengis import oseo_1_0 as oseo
from pyxb.binding import datatypes as xsd
from pyxb.binding import basis
from pyxb import namespace

from oseoserver.operations import submit
from oseoserver.models import Order
from oseoserver import constants

pytestmark = pytest.mark.integration


class TestSubmitOperation(object):

    @pytest.mark.parametrize("collection, options, delivery_protocol", [
        (
            {"id": "fake_id", "name": "dummy_collection"},
            [],
            None,
        ),
        (
            {"id": "fake_id", "name": "dummy_collection"},
            [
                {"name": "fakeoption", "value": "fakevalue"}
            ],
            None,
        ),
        (
                {"id": "fake_id", "name": "dummy_collection"},
                [],
                "ftp",
        ),
        (
                {"id": "fake_id", "name": "dummy_collection"},
                [
                    {"name": "fakeoption", "value": "fakevalue"}

                ],
                "ftp",
        ),
    ])
    def test_validate_order_item(self, settings, collection, options,
                                 delivery_protocol):
        settings.DEBUG = True
        settings.OSEOSERVER_ONLINE_DATA_ACCESS_OPTIONS = []
        if delivery_protocol is not None:
            settings.OSEOSERVER_ONLINE_DATA_ACCESS_OPTIONS.append(
                {"protocol": delivery_protocol})
        settings.OSEOSERVER_PROCESSING_OPTIONS = [
            {"name": opt["name"]} for opt in options]
        settings.OSEOSERVER_PRODUCT_ORDER = {
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor"
        }
        settings.OSEOSERVER_COLLECTIONS = [
            {
                "name": collection["name"],
                "collection_identifier": collection["id"],
                "product_order": {
                    "enabled": True,
                    "options": [opt["name"] for opt in options],
                    "online_data_access_options": [delivery_protocol],
                }
            }
        ]
        requested_item = oseo.CommonOrderItemType(
            itemId="dummy item id1",
            productOrderOptionsId="dummy productorderoptionsid1",
            orderItemRemark="dummy item remark1",
            productId=oseo.ProductIdType(
                identifier="dummy catalog identifier1",
                collectionId=collection["id"]
            ),
            option=[
                BIND(oseo.ParameterData(encoding="XMLEncoding",
                                        values=xsd.anyType()))
            ],
        )
        if delivery_protocol is not None:
            requested_item.deliveryOptions = oseo.DeliveryOptionsType(
                onlineDataAccess=BIND(protocol=delivery_protocol))
        for index in range(len(options)):
            xpath_expression = (
                "oseo:option[{0}]/oseo:ParameterData/"
                "oseo:values".format(index + 1)
            )
            requested_item = _add_item_options(
                requested_item, xpath_expression, options[index])
        order_type = Order.PRODUCT_ORDER
        operation = submit.Submit()
        item_spec = operation.validate_order_item(requested_item, order_type)
        print("item_spec: {}".format(item_spec))
        assert item_spec["item_id"] == requested_item.itemId
        assert item_spec["collection"] == collection["name"]
        assert item_spec["identifier"] == requested_item.productId.identifier
        assert len(item_spec["option"]) == len(options)
        for item in options:
            assert item["value"] == item_spec["option"][item["name"]]
        if delivery_protocol is None:
            assert item_spec["delivery_options"] is None
        else:
            assert item_spec["delivery_options"]["protocol"].value == (
                delivery_protocol)

    def test_process_order_specification(self, settings):
        col_id = "fake collection id"
        col_name = "fake collection name"
        online_data_access_option = "http"
        option_name = "fakeoption"
        option_value = "fakevalue"
        settings.OSEOSERVER_PROCESSING_OPTIONS = [
            {
                "name": option_name
            }
        ]
        settings.OSEOSERVER_PRODUCT_ORDER = {
            "enabled": True,
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor"
        }
        settings.OSEOSERVER_ONLINE_DATA_ACCESS_OPTIONS = [
            online_data_access_option]
        settings.OSEOSERVER_COLLECTIONS = [
            {
                "name": col_name,
                "collection_identifier": col_id,
                "product_order": {
                    "enabled": True,
                    "options": [option_name],
                    "online_data_access_options": [online_data_access_option]
                }
            }
        ]
        order_spec = oseo.OrderSpecification(
            orderReference="dummy reference",
            orderRemark="dummy remark",
            packaging="zip",
            option=[
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
                        identifier="dummy catalog identifier1",
                        collectionId=col_id
                    )
                ),
            ],
        )
        order_spec = _add_order_specification_options(
            order_spec,
            "oseo:option[1]/oseo:ParameterData/oseo:values",
            **{option_name: option_value}
        )
        op = submit.Submit()
        result = op.process_order_specification(order_spec)
        print("result: {}".format(result))


def _add_order_specification_options(order_spec, xpath_expression, **options):
    """Add options to Submit requests

    This function exists in order to overcome dificulties with adding
    arbitrary XML elements using pyxb.

    """
    order_spec_element = etree.fromstring(order_spec.toxml(
        element_name="ns1:orderSpecification"))
    items = order_spec_element.xpath(xpath_expression,
                                     namespaces=constants.NAMESPACES)
    for item in items:
        for option_name, option_value in options.items():
            option_element = etree.SubElement(item, option_name)
            option_element.text = option_value

    submit_oseo = _add_order_specification_to_skeleton_request(
        order_spec_element)
    order_spec_oseo = submit_oseo.orderSpecification
    return order_spec_oseo


def _add_item_options(order_item, xpath_expression, option):
    """Add options to orderItem elements

    This function exists in order to overcome difficulties with adding
    arbitrary XML elements using pyxb.

    """

    order_item_pyxb_element = basis.element(
        namespace.ExpandedName(oseo.Namespace, "orderItem"),
        oseo.CommonOrderItemType
    )
    order_item._setElement(order_item_pyxb_element)
    item_element = etree.fromstring(order_item.toxml())
    values = item_element.xpath(xpath_expression,
                                  namespaces=constants.NAMESPACES)
    for value in values:
        option_element = etree.SubElement(value, option["name"])
        option_element.text = option["value"]
    submit_oseo = _add_item_to_skeleton_request(item_element)
    order_item_oseo = submit_oseo.orderSpecification.orderItem[0]
    return order_item_oseo


def _add_order_specification_to_skeleton_request(order_specification_element):
    submit_request = oseo.Submit(
        service="OS",
        version="1.0.0",
        orderSpecification=oseo.OrderSpecification(
            orderType="PRODUCT_ORDER",
            orderItem=[
                oseo.CommonOrderItemType(
                    itemId="replaceable dummy item id",
                    productId=oseo.ProductIdType(
                        identifier="replaceable dummy identifier",
                    )
                ),
            ],
        ),
        statusNotification="None"
    )
    submit_el = etree.fromstring(
        submit_request.toxml(encoding=constants.ENCODING))
    submit_el.replace(
        submit_el.xpath("oseo:orderSpecification",
                        namespaces=constants.NAMESPACES)[0],
        order_specification_element
    )
    submit_completed = oseo.CreateFromDocument(etree.tostring(submit_el))
    return submit_completed



def _add_item_to_skeleton_request(item_element):
    """Create an OSEO Submit request pyxb object with the input order item"""
    submit_request = oseo.Submit(
        service="OS",
        version="1.0.0",
        orderSpecification=oseo.OrderSpecification(
            orderType="PRODUCT_ORDER",
            orderItem=[
                oseo.CommonOrderItemType(
                    itemId="replaceable dummy item id",
                    productId=oseo.ProductIdType(
                        identifier="replaceable dummy identifier",
                    )
                ),
            ],
        ),
        statusNotification="None"
    )
    submit_el = etree.fromstring(
        submit_request.toxml(encoding=constants.ENCODING))
    order_spec_el = submit_el.xpath("oseo:orderSpecification",
                                    namespaces=constants.NAMESPACES)[0]
    order_spec_el.replace(
        order_spec_el.xpath("oseo:orderItem",
                            namespaces=constants.NAMESPACES)[0],
        item_element
    )
    submit_completed = oseo.CreateFromDocument(etree.tostring(submit_el))
    return submit_completed
