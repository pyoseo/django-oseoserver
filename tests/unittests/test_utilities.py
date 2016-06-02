"""Unit tests for oseoserver.utilities"""

import pytest
import mock

from oseoserver import constants
from oseoserver import errors
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
        setting_function = getattr(mock_settings,
                                   "get_{}".format(order_type.value.lower()))
        setting_function.return_value = fake_config
        result = utilities.get_generic_order_config(order_type)
        assert  result == fake_config


@pytest.mark.parametrize(["option_name", "option_value", "mocked_config"], [
    ("fake_name", "fake_value", {}),
    ("fake_name", "fake_value", {"name": "fake"}),
    ("fake_name", "fake_value", {
        "name": "fake_name",
        "choices": ["choice1"]
    }),

])
def test_validate_processing_option_invalid_option(option_name, option_value,
                                                   mocked_config):
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings:
        mock_settings.get_processing_options.return_value = [mocked_config]
        with pytest.raises(ValueError):
            utilities.validate_processing_option(option_name, option_value)


@pytest.mark.parametrize(["option_name", "option_value", "mocked_config"], [
    ("fake_name", "fake_value", {"name": "fake_name"}),
    ("fake_name", "fake_value", {
        "name": "fake_name",
        "choices": ["fake_value"]
    }),
])
def test_validate_processing_option_valid_option(option_name, option_value,
                                                 mocked_config):
    with mock.patch("oseoserver.utilities.settings",
                    autospec=True) as mock_settings:
        mock_settings.get_processing_options.return_value = [mocked_config]
        utilities.validate_processing_option(option_name, option_value)


@pytest.mark.parametrize(["order_type", "expected_exception"], [
    (constants.OrderType.PRODUCT_ORDER,
     errors.ProductOrderingNotSupportedError),
    (constants.OrderType.MASSIVE_ORDER,
     errors.ProductOrderingNotSupportedError),
    (constants.OrderType.SUBSCRIPTION_ORDER,
     errors.SubscriptionNotSupportedError),
    (constants.OrderType.TASKING_ORDER,
     errors.FutureProductNotSupportedError)
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
    constants.OrderType.PRODUCT_ORDER,
    constants.OrderType.MASSIVE_ORDER,
    constants.OrderType.SUBSCRIPTION_ORDER,
    constants.OrderType.TASKING_ORDER,
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

