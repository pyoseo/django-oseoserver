"""Integration tests for oseoserver.server"""

from lxml import etree
import pytest
from pyxb.bundles.opengis import oseo_1_0 as oseo

from oseoserver.server import OseoServer
from oseoserver.constants import NAMESPACES


@pytest.mark.integration
class TestServer(object):

    def test_process_request_get_capabilities(self):
        """GetCapabilities requests are processed OK."""
        fake_user = None
        get_caps = oseo.GetCapabilities(service="OS")
        request = get_caps.toxml(encoding="utf-8")
        request_data = etree.fromstring(request)
        server = OseoServer()
        response_element = server.process_request(request_data, fake_user)
        root_tag = etree.QName(response_element.tag)
        assert root_tag.localname == "Capabilities"
        assert root_tag.namespace == NAMESPACES["oseo"]

