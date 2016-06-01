"""Unit tests for the oseoserver.server module."""

import pytest
import mock

from oseoserver.server import OseoServer
from oseoserver import constants


@pytest.mark.unit
class TestServer(object):

    def test_can_create(self):
        server = OseoServer()
        assert constants.ENCODING.lower() == "utf-8"
        assert server.OSEO_VERSION == "1.0.0"

    def test_process_request_no_submit(self):
        fake_request_data = "fake_request"
        fake_user = None
        fake_response = mock.MagicMock()
        fake_xml = "fake_xml"
        fake_response.toxml.return_value = fake_xml
        fake_response_element = "fake_response_element"
        fake_order = "fake_order"
        fake_request_instance = "fake_request_instance"
        fake_operation = mock.MagicMock()
        fake_operation_name = "fake_operation_name"
        fake_operation.return_value = (fake_response, fake_order)

        server = OseoServer()
        with mock.patch.multiple(server, parse_xml=mock.DEFAULT,
                                 _get_operation=mock.DEFAULT) as mocks, \
                mock.patch("oseoserver.server.etree",
                           autospec=True) as mocked_etree:
            mocks["parse_xml"].return_value = fake_request_instance
            mocks["_get_operation"].return_value = (fake_operation,
                                                    fake_operation_name)
            mocked_etree.fromstring.return_value = fake_response_element
            response_element = server.process_request(
                request_data=fake_request_data, user=fake_user)
            assert response_element == fake_response_element
            mocks["parse_xml"].assert_called_once_with(fake_request_data)
            mocks["_get_operation"].assert_called_once_with(
                fake_request_instance)
            fake_operation.assert_called_once_with(fake_request_instance,
                                                   fake_user)
            fake_response.toxml.assert_called_once_with(
                encoding=constants.ENCODING)
            mocked_etree.fromstring.assert_called_once_with(fake_xml)


