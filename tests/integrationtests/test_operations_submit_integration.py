"""Integration tests for oseoserver.operations.submit"""

import pytest
from pyxb.bundles.opengis import oseo_1_0 as oseo

from oseoserver.operations import submit
from oseoserver.constants import OrderType

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
