"""Unit tests for oseoserver.utilities"""

import pytest
import mock

from oseoserver import constants
from oseoserver import utilities

pytestmark = pytest.mark.unit


def test_get_generic_order_config_incorrect_order_type():
    order_type = "fake"
    with pytest.raises(AttributeError) as excinfo:
        config = utilities.get_generic_order_config(order_type)


@pytest.mark.parametrize(["order_type", "fake_config"], [
    (constants.OrderType.PRODUCT_ORDER, "dummy product config"),
    (constants.OrderType.MASSIVE_ORDER, "dummy massive config"),
    (constants.OrderType.SUBSCRIPTION_ORDER, "dummy subscription config"),
    (constants.OrderType.TASKING_ORDER, "dummy tasking config"),
])
def test_get_generic_order_config(order_type, fake_config):
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings:
        setattr(mock_settings,
                "OSEOSERVER_{}".format(order_type.value),
                fake_config)
        result = utilities.get_generic_order_config(order_type)
        assert  result == fake_config
