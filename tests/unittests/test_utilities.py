"""Unit tests for oseoserver.utilities"""

import pytest
import mock
from mock import DEFAULT

from oseoserver import errors
from oseoserver.models import Order
from oseoserver import utilities

pytestmark = pytest.mark.unit


def test_get_generic_order_config_incorrect_order_type():
    order_type = "fake"
    with pytest.raises(AttributeError) as excinfo:
        config = utilities.get_generic_order_config(order_type)


@pytest.mark.parametrize(["order_type", "fake_config"], [
    (Order.PRODUCT_ORDER, "dummy product config"),
    (Order.MASSIVE_ORDER, "dummy massive config"),
    (Order.SUBSCRIPTION_ORDER, "dummy subscription config"),
    (Order.TASKING_ORDER, "dummy tasking config"),
])
def test_get_generic_order_config(order_type, fake_config):
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings:
        setting_function = getattr(mock_settings,
                                   "get_{}".format(order_type.value.lower()))
        setting_function.return_value = fake_config
        result = utilities.get_generic_order_config(order_type)
        assert  result == fake_config


def test_validate_processing_option_no_choices():
    fake_option_name = "dummy name"
    fake_parsed_value = "dummy value"
    order_type = Order.PRODUCT_ORDER
    with mock.patch.multiple("oseoserver.utilities",
                             get_order_configuration=DEFAULT,
                             get_generic_order_config=DEFAULT,
                             import_class=DEFAULT) as mock_util, \
            mock.patch("oseoserver.settings.get_processing_options",
                       autospec=True) as mock_get_options:
        mock_util["get_order_configuration"].return_value = {
            "product_order": {"options": [fake_option_name]}
        }
        mock_util["get_generic_order_config"].return_value = {
            "item_processor": "dummy"}
        mock_util["import_class"].return_value.parse_option.return_value = (
            fake_parsed_value)
        mock_get_options.return_value = [{"name": fake_option_name}]
        result = utilities.validate_processing_option(
            fake_option_name, fake_parsed_value, order_type, "dummy")
        assert result == fake_parsed_value


@pytest.mark.parametrize(["order_type", "expected_exception"], [
    (Order.PRODUCT_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.MASSIVE_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.SUBSCRIPTION_ORDER, errors.SubscriptionNotSupportedError),
    (Order.TASKING_ORDER, errors.FutureProductNotSupportedError)
])
def test_get_order_configuration_disabled(order_type, expected_exception):
    """The proper exceptions are raised when order types are disabled"""
    fake_collection = "dummy collection"
    fake_collection_config = {
        "name": fake_collection,
        order_type.value.lower(): {"enabled": False},
    }
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings, \
            pytest.raises(expected_exception):
        mock_settings.get_collections.return_value = [fake_collection_config]
        utilities.get_order_configuration(order_type, fake_collection)

@pytest.mark.parametrize("order_type", [
    Order.PRODUCT_ORDER,
    Order.MASSIVE_ORDER,
    Order.SUBSCRIPTION_ORDER,
    Order.TASKING_ORDER,
])
def test_get_order_configuration_enabled(order_type):
    fake_collection = "dummy collection"
    fake_collection_config = {
        "name": fake_collection,
        order_type.value.lower(): {"enabled": True},
    }
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings:
        mock_settings.get_collections.return_value = [fake_collection_config]
        result = utilities.get_order_configuration(order_type, fake_collection)
    assert result == fake_collection_config


def test_get_option_configuration_invalid_option():
    fake_name = "fake_option"
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings, \
            pytest.raises(errors.OseoServerError):
        mock_settings.get_processing_options.return_value = []
        utilities.get_option_configuration(fake_name)


def test_get_option_configuration_valid_option():
    fake_name = "fake_option"
    fake_option_config = {"name": fake_name}
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings:
        mock_settings.get_processing_options.return_value = [
            fake_option_config]
        result = utilities.get_option_configuration(fake_name)
        assert result == fake_option_config


def test_validate_collection_id_invalid_id():
    fake_id = "fake collection id"
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings, \
            pytest.raises(errors.InvalidParameterValueError):
        mock_settings.get_collections.return_value = []
        utilities.validate_collection_id(fake_id)


def test_validate_collection_id_valid_id():
    fake_id = "fake collection id"
    fake_collection_config = {"collection_identifier": fake_id}
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings:
        mock_settings.get_collections.return_value = [fake_collection_config]
        result = utilities.validate_collection_id(fake_id)
        assert result == fake_collection_config

