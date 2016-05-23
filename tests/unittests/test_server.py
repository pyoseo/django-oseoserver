"""Unit tests for oseoserver.server"""

import pytest

from oseoserver.server import OseoServer

@pytest.mark.unit
class TestServer(object):

    def test_can_create(self):
        server = OseoServer()
        assert server.ENCODING.lower() == "utf-8"
        assert server.OSEO_VERSION == "1.0.0"

