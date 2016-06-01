"""Unit tests for oseoserver.operations.submit"""

import pytest
import mock

from oseoserver.operations import submit
from oseoserver import constants
from oseoserver import errors

pytestmark = pytest.mark.unit


class TestSubmit(object):

    def test_creation(self):
        submit.Submit()

    @pytest.mark.skip
    def test_process_order_specification(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_create_order(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_get_delivery_information(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_get_invoice_address(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_get_delivery_address(self):
        raise NotImplementedError

    def test_validate_status_notification_invalid_status(self):
        status_notification = "dummy"
        with mock.patch("pyxb.bundles.opengis.oseo_1_0.SubmitOrderRequestType",
                        autospec=True) as mock_request, \
                pytest.raises(NotImplementedError):
            mock_request.statusNotification = status_notification
            op = submit.Submit()
            op.validate_status_notification(mock_request)

    def test_validate_status_notification_valid_status(self):
        fake_status_notification = "fake"
        with mock.patch("pyxb.bundles.opengis.oseo_1_0.SubmitOrderRequestType",
                        autospec=True) as mock_request, \
                mock.patch("oseoserver.operations.submit.StatusNotification",
                           autospec=True) as mock_status_notification:
            mock_status_notification.NONE.value = fake_status_notification
            mock_request.statusNotification = fake_status_notification
            op = submit.Submit()
            op.validate_status_notification(mock_request)

    @pytest.mark.skip
    def test_get_collection_id(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_validate_product_order_item(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_validate_subscription_order_item(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_validate_tasking_order_item(self):
        raise NotImplementedError

    def test_validate_collection_id_invalid(self):
        op = submit.Submit()
        fake_identifier = "dummy identifier"
        fake_collection_config = {}
        with mock.patch("oseoserver.operations.submit.settings",
                        autospec=True) as mock_settings, \
                pytest.raises(errors.InvalidParameterValueError):
            mock_settings.OSEOSERVER_COLLECTIONS = [fake_collection_config]
            op._validate_collection_id(fake_identifier)

    def test_validate_collection_id_valid(self):
        op = submit.Submit()
        fake_identifier = "dummy identifier"
        fake_collection_config = {
            "collection_identifier": fake_identifier,
        }
        with mock.patch("oseoserver.operations.submit.settings",
                        autospec=True) as mock_settings:
            mock_settings.get_collections.return_value = [
                fake_collection_config]
            result = op._validate_collection_id(fake_identifier)
            assert result == fake_collection_config

    @pytest.mark.skip
    def test_validate_requested_options(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_validate_global_options(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_validate_selected_option(self):
        raise NotImplementedError

    @pytest.mark.skip
    def test_validate_order_item(self):
        raise NotImplementedError
