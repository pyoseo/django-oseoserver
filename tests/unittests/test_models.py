"""unit tests for oseoserver.models"""

from django.core.exceptions import ValidationError
import pytest

from oseoserver import models

pytestmark = pytest.mark.unit


class TestOrderItem(object):

    def test_validation_invalid_collection(self, settings):
        settings.OSEOSERVER_COLLECTIONS = [{"name": "phony_collection"},]
        with pytest.raises(ValidationError):
            item = models.OrderItem(
                collection="fake_collection",
                item_id="fake_item_id",
            )
            item.full_clean()

    #def test_creation(self):
    #    item = models.OrderItem.objects.create(
    #        collection="fake_collection",
    #        item_id="fake_item_id",
    #    )
