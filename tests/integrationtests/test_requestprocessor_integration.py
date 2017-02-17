"""Integration tests for oseoserver.requestprocessor"""

from lxml import etree
import pytest
from pyxb.bundles.opengis import oseo_1_0 as oseo

from oseoserver import requestprocessor
from oseoserver import errors
from oseoserver import constants

pytestmark = pytest.mark.integration


class TestServer(object):

    def test_process_request_get_capabilities(self):
        """GetCapabilities requests are processed OK."""
        fake_user = None
        get_caps = oseo.GetCapabilities(service="OS")
        request = get_caps.toxml(encoding="utf-8")
        request_data = etree.fromstring(request)
        response_element = requestprocessor.process_request(
            request_data, fake_user)
        root_tag = etree.QName(response_element.tag)
        assert root_tag.localname == "Capabilities"
        assert root_tag.namespace == constants.NAMESPACES["oseo"]

    def test_process_request_get_status_invalid_order_id(self):
        """Getstatus with an invalid order id raises the proper error"""
        fake_user = None
        fake_order_id = "fake"
        presentation = "brief"
        get_status = oseo.GetStatus(
            service="OS",
            version="1.0.0",
            orderId=fake_order_id,
            presentation=presentation
        )
        request = get_status.toxml(encoding="utf-8")
        request_data = etree.fromstring(request)
        with pytest.raises(errors.OseoError) as excinfo:
            requestprocessor.process_request(request_data, fake_user)
        assert excinfo.value.code == "InvalidOrderIdentifier"

