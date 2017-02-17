"""Unit tests for the oseoserver.requestprocessor module."""

import pytest
from lxml import etree

from oseoserver import errors
from oseoserver import requestprocessor

pytestmark = pytest.mark.unit


def test_parse_xml_correct():
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
    """.encode("utf-8").strip())
    result = requestprocessor.parse_xml(fake_xml)
    parsed_result = etree.QName(etree.fromstring(result.toxml()))
    assert parsed_result.localname == "GetCapabilities"


def test_parse_xml_unrecognized():
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
    """.encode("utf-8").strip())
    with pytest.raises(errors.NoApplicableCodeError):
        requestprocessor.parse_xml(fake_xml)
