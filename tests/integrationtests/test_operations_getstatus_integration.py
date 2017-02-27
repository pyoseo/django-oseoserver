"""Integration tests for oseoserver.operations.getstatus"""

import pytest
from pyxb.bundles.opengis import oseo_1_0 as oseo

from lxml import etree
from oseoserver import errors
from oseoserver import models
from oseoserver.operations import getstatus
from oseoserver import requestprocessor

pytestmark = pytest.mark.integration


def test_get_status_no_orders(admin_user):
    request = oseo.GetStatus(
        service="OS",
        version="1.0.0",
        presentation=getstatus.BRIEF,
        orderId="fake"
    )
    with pytest.raises(errors.InvalidOrderIdentifierError):
        response = getstatus.get_status(request=request, user=admin_user)


@pytest.mark.django_db
def test_get_status_order_id_no_items(admin_user):
    test_order = models.Order(
        status=models.CustomizableItem.SUBMITTED,
        user=admin_user,
        order_type=models.Order.PRODUCT_ORDER,
        status_notification=models.Order.FINAL
    )
    test_order.save()
    requestprocessor.handle_submit(test_order, approved=False, notify=False)
    request = oseo.GetStatus(
        service="OS",
        version="1.0.0",
        presentation=getstatus.BRIEF,
        orderId=str(test_order.pk)
    )
    result = getstatus.get_status(request, admin_user)
    assert isinstance(result, oseo.GetStatusResponseType)
    assert result.status == "success"
    monitor = result.orderMonitorSpecification[0]
    assert monitor.orderType == test_order.order_type
    assert monitor.orderId == str(test_order.pk)
    assert monitor.orderStatusInfo.status == test_order.status
    assert len(monitor.orderItem) == 0


@pytest.mark.django_db
def test_get_status_failed_order_id_items(admin_user):
    order = models.Order.objects.create(
        status=models.CustomizableItem.SUBMITTED,
        user=admin_user,
        order_type=models.Order.PRODUCT_ORDER,
        status_notification=models.Order.FINAL,
    )
    item_spec = models.ItemSpecification.objects.create(
        order=order,
        remark="Some item remark",
        collection="lst",
        identifier = "",
        item_id="some id for the item",
    )
    requestprocessor.handle_submit(order, approved=False, notify=False)
    request = oseo.GetStatus(
        service="OS",
        version="1.0.0",
        presentation=getstatus.BRIEF,
        orderId=str(order.pk)
    )
    result = getstatus.get_status(request, admin_user)
    assert isinstance(result, oseo.GetStatusResponseType)
    assert result.status == "success"
    monitor = result.orderMonitorSpecification[0]
    assert monitor.orderType == order.order_type
    assert monitor.orderId == str(order.pk)
    assert monitor.orderStatusInfo.status == order.status
    assert len(monitor.orderItem) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "item_specification_identifiers, presentation, expected_items",
    [
        ([""], "brief", 0),
        ([""], "full", 1)
    ]
)
def test_get_status_order_id_items(admin_user, item_specification_identifiers,
                                   presentation, expected_items):
    order = models.Order.objects.create(
        status=models.CustomizableItem.SUBMITTED,
        user=admin_user,
        order_type=models.Order.PRODUCT_ORDER,
        status_notification=models.Order.FINAL,
    )
    for identifier in item_specification_identifiers:
        models.ItemSpecification.objects.create(
            order=order,
            remark="Some item remark",
            collection="lst",
            identifier = identifier,
            item_id="some id for the item",
        )
    requestprocessor.create_product_order_batch(order)
    request = oseo.GetStatus(
        service="OS",
        version="1.0.0",
        presentation=presentation,
        orderId=str(order.pk)
    )
    print("order status: {}".format(order.status))
    print("order item specifications: {}".format(order.item_specifications.count()))
    print("order batches: {}".format(order.batches.count()))
    print("batch order items: {}".format(order.batches.get().order_items.count()))
    result = getstatus.get_status(request, admin_user)
    _print_response(result)
    assert isinstance(result, oseo.GetStatusResponseType)
    assert result.status == "success"
    monitor = result.orderMonitorSpecification[0]
    assert monitor.orderType == order.order_type
    assert monitor.orderId == str(order.pk)
    assert monitor.orderStatusInfo.status == order.status
    assert len(monitor.orderItem) == expected_items


def _print_response(oseo_response):
    print(
        etree.tostring(
            etree.fromstring(
                oseo_response.toxml()
            ),
            pretty_print=True,
        ).decode("utf-8")
    )
