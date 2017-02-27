"""Integration tests for oseoserver.operations.getcapabilities."""

import pytest
from pyxb.bundles.opengis import oseo_1_0 as oseo

pytestmark = pytest.mark.integration


def test_get_capabilities():
    request = oseo.GetCapabilities(
        service="OS",
        version="1.0.0"
    )