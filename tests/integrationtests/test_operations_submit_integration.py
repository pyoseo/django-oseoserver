"""Integration tests for oseoserver.operations.submit"""

from lxml import etree
import pytest
from pyxb import BIND
from pyxb.bundles.opengis import oseo_1_0 as oseo
from pyxb.binding import datatypes as xsd
from pyxb.binding import basis
from pyxb import namespace

from oseoserver.operations import submit
from oseoserver import constants
from oseoserver.constants import OrderType
from oseoserver.constants import DeliveryOption
from oseoserver.constants import DeliveryOptionProtocol

pytestmark = pytest.mark.integration


class TestSubmitOperation(object):

    def test_validate_order_item_no_options_no_delivery(self, settings):
        col_id = "fakeid"
        col_name = "dummy collection"
        settings.OSEOSERVER_COLLECTIONS = [
            {
                "name": col_name,
                "collection_identifier": col_id,
                "product_order": {"enabled": True}
            }
        ]
        requested_item = oseo.CommonOrderItemType(
            itemId="dummy item id1",
            productOrderOptionsId="dummy productorderoptionsid1",
            orderItemRemark="dummy item remark1",
            productId=oseo.ProductIdType(
                identifier="dummy catalog identifier1",
                collectionId=col_id
            )
        )
        order_type = OrderType.PRODUCT_ORDER

        op = submit.Submit()
        item_spec = op.validate_order_item(requested_item, order_type)
        assert item_spec["item_id"] == requested_item.itemId
        assert len(item_spec["option"]) == 0
        assert item_spec["delivery_options"] is None
        assert item_spec["collection"] == col_name
        assert item_spec["identifier"] == requested_item.productId.identifier

    def test_validate_order_item_options_no_delivery(self, settings):
        """Validates an orderItem featuring valid processing options."""
        col_id = "fakeid"
        col_name = "dummy collection"
        option_name = "fakeoption"
        option_value = "fakevalue"
        settings.OSEOSERVER_PROCESSING_OPTIONS = [
            {
                "name": option_name
            }
        ]
        settings.OSEOSERVER_PRODUCT_ORDER = {
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor"
        }
        settings.OSEOSERVER_COLLECTIONS = [
            {
                "name": col_name,
                "collection_identifier": col_id,
                "product_order": {
                    "enabled": True,
                    "options": [option_name]
                }
            }
        ]
        requested_item = oseo.CommonOrderItemType(
            itemId="dummy item id1",
            productOrderOptionsId="dummy productorderoptionsid1",
            orderItemRemark="dummy item remark1",
            productId=oseo.ProductIdType(
                identifier="dummy catalog identifier1",
                collectionId=col_id
            ),
            option=[
                BIND(oseo.ParameterData(encoding="XMLEncoding",
                                        values=xsd.anyType())),
            ],
        )
        requested_item = _add_item_options(
            requested_item,
            "oseo:option[1]/oseo:ParameterData/oseo:values",
            **{option_name: option_value}
        )
        order_type = OrderType.PRODUCT_ORDER

        op = submit.Submit()
        item_spec = op.validate_order_item(requested_item, order_type)
        print("item_spec: {}".format(item_spec))
        assert item_spec["item_id"] == requested_item.itemId
        assert item_spec["option"] == {option_name: option_value}
        assert item_spec["delivery_options"] is None
        assert item_spec["collection"] == col_name
        assert item_spec["identifier"] == requested_item.productId.identifier

    @pytest.mark.parametrize("online_data_access_option", ["http", "ftp"])
    def test_validate_order_item_no_options_delivery_online_data_access(
            self, online_data_access_option, settings):
        """Validates an orderItem featuring valid delivery options."""

        col_id = "fakeid"
        col_name = "dummy collection"
        settings.OSEOSERVER_ONLINE_DATA_ACCESS_OPTIONS = [
            online_data_access_option]
        settings.OSEOSERVER_COLLECTIONS = [
            {
                "name": col_name,
                "collection_identifier": col_id,
                "product_order": {
                    "enabled": True,
                    "online_data_access_options": [online_data_access_option]
                }
            }
        ]
        requested_item = oseo.CommonOrderItemType(
            itemId="dummy item id1",
            productOrderOptionsId="dummy productorderoptionsid1",
            orderItemRemark="dummy item remark1",
            productId=oseo.ProductIdType(
                identifier="dummy catalog identifier1",
                collectionId=col_id
            ),
            deliveryOptions=oseo.DeliveryOptionsType(
                onlineDataAccess=BIND(protocol=online_data_access_option))
        )
        order_type = OrderType.PRODUCT_ORDER

        op = submit.Submit()
        item_spec = op.validate_order_item(requested_item, order_type)
        assert item_spec["item_id"] == requested_item.itemId
        assert item_spec["delivery_options"][
                   "type"] == DeliveryOption.ONLINE_DATA_ACCESS
        assert item_spec["delivery_options"][
                   "protocol"] == DeliveryOptionProtocol(
            online_data_access_option)
        assert item_spec["collection"] == col_name
        assert item_spec["identifier"] == requested_item.productId.identifier

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
    order_spec_pyxb_element = basis.element(
        namespace.ExpandedName(oseo.Namespace, "orderSpecification"),
        oseo.orderSpecification
    )
    order_spec._setElement(order_spec_pyxb_element)
    order_spec_element = etree.fromstring(order_spec.toxml())
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


def _add_item_options(order_item, xpath_expression, **options):
    """Add options to orderItem elements

    This function exists in order to overcome dificulties with adding
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
        for option_name, option_value in options.items():
            option_element = etree.SubElement(value, option_name)
            option_element.text = option_value
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
