"""unit tests for oseoserver.models"""

import pytest

from oseoserver import models

pytestmark = pytest.mark.unit


class TestOrderItem(object):

    @pytest.mark.django_db
    def test_create_no_batch(self):
        item = models.OrderItem.objects.create(
            collection="fake_collection",
            item_id="fake_item_id",
        )

    @pytest.mark.django_db
    def test_create_with_batch(self):
        batch = models.ProcessingBatch.objects.create()
        item = models.OrderItem.objects.create(
            collection="fake_collection",
            item_id="fake_item_id",
            product_order_batch=batch
        )


class TestProductOrder():

    @pytest.mark.django_db
    def test_create(self, admin_user):
        order = models.Order.objects.create(user=admin_user)
        assert order.order_type == models.Order.PRODUCT_ORDER

    @pytest.mark.django_db
    def test_add_batch_product_order(self, admin_user):
        order = models.Order.objects.create(user=admin_user)
        batch = models.ProcessingBatch.objects.create()
        order.add_batch(batch)
        order.save()
        assert order.regular_batches.count() == 1

