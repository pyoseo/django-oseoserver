"""Unit tests for the oseoserver.server module."""

import pytest
import mock
from lxml import etree

from oseoserver import constants
from oseoserver import errors
from oseoserver.server import OseoServer
from pyxb.bundles.opengis import oseo_1_0 as oseo

pytestmark = pytest.mark.unit


class TestServer(object):

    def test_can_create(self):
        OseoServer()

    def test_parse_xml_correct(self):
        fake_xml = etree.fromstring("""
        <?xml version="1.0" encoding="UTF-8"?>
        <GetCapabilities xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns="http://www.opengis.net/oseo/1.0"
                xsi:schemaLocation="http://www.opengis.net/oseo/1.0
                    http://schemas.opengis.net/oseo/1.0/oseo.xsd"
                xmlns:m0="http://www.opengis.net/ows/2.0"
                updateSequence=""
                service="OS"
        >
            <m0:AcceptVersions>
                <m0:Version>1.0.0</m0:Version>
            </m0:AcceptVersions>
        </GetCapabilities>
        """.strip())
        server = OseoServer()
        result = server.parse_xml(fake_xml)
        parsed_result = etree.QName(etree.fromstring(result.toxml()))
        assert parsed_result.localname == "GetCapabilities"

    def test_parse_xml_unrecognized(self):
        fake_xml = etree.fromstring("""
        <?xml version="1.0" encoding="UTF-8"?>
        <Phony xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns="http://www.opengis.net/oseo/1.0"
                xsi:schemaLocation="http://www.opengis.net/oseo/1.0
                    http://schemas.opengis.net/oseo/1.0/oseo.xsd"
                xmlns:m0="http://www.opengis.net/ows/2.0"
                updateSequence=""
                service="OS"
        >
            <m0:AcceptVersions>
                <m0:Version>1.0.0</m0:Version>
            </m0:AcceptVersions>
        </Phony>
        """.strip())
        server = OseoServer()
        with pytest.raises(errors.NoApplicableCodeError):
            server.parse_xml(fake_xml)

    @pytest.mark.parametrize("oseo_request, expected", [
        (oseo.GetCapabilities(), "GetCapabilities")
    ])
    def test_get_operation(self):
        server = OseoServer()
        server._get_operation()

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


