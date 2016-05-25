"""Unit tests for oseoserver.server"""

import pytest
from pyxb import BIND
from pyxb.bundles.opengis import oseo_1_0 as oseo
from pyxb.bundles.wssplat import soap12
from pyxb.bundles.wssplat import wsse

from oseoserver.server import OseoServer


@pytest.mark.unit
class TestServer(object):

    def test_can_create(self):
        server = OseoServer()
        assert server.ENCODING.lower() == "utf-8"
        assert server.OSEO_VERSION == "1.0.0"

    def test_process_get_capabilities(self):
        """GetCapabilities requests are processed OK."""
        server = OseoServer()
        fake_username = "fake_user"
        fake_password = "fake_pass"
        fake_password_type = "fake"
        fake_user = None

        get_caps = oseo.GetCapabilities(service="OS")
        security = wsse.Security(
            wsse.UsernameToken(
                fake_username,
                wsse.Password(fake_password, Type=fake_password_type)
            )
        )
        soap_request_env = soap12.Envelope(
            Header=BIND(security),
            Body=BIND(get_caps)
        )
        request_data = soap_request_env.toxml(encoding="utf-8")

        response, status, headers = server.process_request(request_data,
                                                           fake_user)
        assert status == 200

