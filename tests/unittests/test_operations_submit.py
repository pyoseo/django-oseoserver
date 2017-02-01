"""Unit tests for oseoserver.operations.submit"""

import mock
import pytest
from pyxb import BIND
from pyxb.bundles.opengis import oseo_1_0 as oseo

from oseoserver.operations import submit
from oseoserver.models import Order
from oseoserver.models import CustomizableItem
from oseoserver.utilities import _c

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("order_specification, expected", [
    (oseo.OrderSpecification(orderType="PRODUCT_ORDER"), Order.PRODUCT_ORDER),
    (
        oseo.OrderSpecification(orderType="SUBSCRIPTION_ORDER"),
        Order.SUBSCRIPTION_ORDER
    ),
    (oseo.OrderSpecification(orderType="TASKING_ORDER"), Order.TASKING_ORDER),
    (
        oseo.OrderSpecification(
            orderType="PRODUCT_ORDER",
            orderReference=Order.MASSIVE_ORDER_REFERENCE
        ),
        Order.MASSIVE_ORDER
    ),
    (
        oseo.OrderSpecification(
            orderType="PRODUCT_ORDER",
            orderReference="dummy"
        ),
        Order.PRODUCT_ORDER
    ),
])
def test_get_order_type(order_specification, expected):
        result = submit.get_order_type(order_specification=order_specification)
        assert result == expected


@pytest.mark.parametrize("order_type, enabled, auto_approved, expected", [
    (Order.PRODUCT_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.MASSIVE_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.SUBSCRIPTION_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.TASKING_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.PRODUCT_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.MASSIVE_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.SUBSCRIPTION_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.TASKING_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.PRODUCT_ORDER, True, True, CustomizableItem.ACCEPTED),
    (Order.MASSIVE_ORDER, True, True, CustomizableItem.ACCEPTED),
    (Order.SUBSCRIPTION_ORDER, True, True, CustomizableItem.ACCEPTED),
    (Order.TASKING_ORDER, True, True, CustomizableItem.ACCEPTED),
])
def test_get_initial_status(settings, order_type, enabled,
                            auto_approved, expected):
    setattr(settings, "OSEOSERVER_{}".format(order_type), {
        "enabled": enabled,
        "automatic_approval": auto_approved,
    })
    result = submit._get_initial_status(order_type)
    assert result == expected


@pytest.mark.parametrize("first, last, company, tel, fax", [
    ("dummy", "phony", "fake", "11111", "22222"),
    (None, None, None, None, None),
])
def test_get_delivery_address_no_postal_address(first, last, company,
                                                tel, fax):
    delivery_address_type = oseo.DeliveryAddressType(
        firstName=first,
        lastName=last,
        companyRef=company,
        telephoneNumber=tel,
        facsimileTelephoneNumber=fax,
    )
    result = submit._get_delivery_address(delivery_address_type)
    assert result["first_name"] == _c(first)
    assert result["last_name"] == _c(last)
    assert result["company_ref"] == _c(company)
    assert result["telephone"] == _c(tel)
    assert result["fax"] == _c(fax)


@pytest.mark.parametrize("street, city, state, code, country, po", [
    ("Dummy Av.", "phony", "fake", "11111", "none", "22jd"),
    (None, None, None, None, None, None),
])
def test_get_delivery_address_postal_address(street, city, state, code,
                                             country, po):
    delivery_address_type = oseo.DeliveryAddressType(
        postalAddress=BIND(
            streetAddress=street,
            city=city,
            state=state,
            postalCode=code,
            country=country,
            postBox=po
        )
    )
    result = submit._get_delivery_address(delivery_address_type)
    assert result["postal_address"]["street_address"] == _c(street)
    assert result["postal_address"]["city"] == _c(city)
    assert result["postal_address"]["state"] == _c(state)
    assert result["postal_address"]["postal_code"] == _c(code)
    assert result["postal_address"]["country"] == _c(country)
    assert result["postal_address"]["post_box"] == _c(po)


@pytest.mark.parametrize("status, expected_details", [
    (CustomizableItem.SUBMITTED, "Order is awaiting approval"),
    (CustomizableItem.ACCEPTED, "Order has been placed in processing queue"),
    (CustomizableItem.IN_PRODUCTION, "Order has been rejected"),
    (CustomizableItem.SUSPENDED, "Order has been rejected"),
    (CustomizableItem.CANCELLED, "Order has been rejected"),
    (CustomizableItem.COMPLETED, "Order has been rejected"),
    (CustomizableItem.FAILED, "Order has been rejected"),
    (CustomizableItem.TERMINATED, "Order has been rejected"),
    (CustomizableItem.DOWNLOADED, "Order has been rejected"),
])
def test_get_order_initial_status(status, expected_details):
    with mock.patch.object(submit, "_get_initial_status") as mock_get_initial:
        mock_get_initial.return_value = status
        result = submit.get_order_initial_status(None)
        result_status, result_details = result
        assert result_details == expected_details


@pytest.mark.parametrize("status, expected_details", [
    (CustomizableItem.SUBMITTED, "Order is awaiting approval"),
    (CustomizableItem.ACCEPTED, "Item has been placed in processing queue"),
    (CustomizableItem.IN_PRODUCTION,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.SUSPENDED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.CANCELLED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.COMPLETED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.FAILED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.TERMINATED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.DOWNLOADED,
     "The Order has been rejected, item won't be processed"),
])
def test_get_order_item_initial_status(status, expected_details):
    with mock.patch.object(submit, "_get_initial_status") as mock_get_initial:
        mock_get_initial.return_value = status
        result = submit.get_order_item_initial_status(None)
        result_status, result_details = result
        assert result_details == expected_details


    #def test_process_request_order_specification(self):
    #    order_spec = oseo.OrderSpecification(
    #        order_type="PRODUCT_ORDER",
    #        orderItem=[
    #            oseo.CommonOrderItemType(
    #                itemId="my_id",
    #                productId=oseo.ProductIdType(identifier="my_identifier")
    #            )
    #        ]
    #    )
