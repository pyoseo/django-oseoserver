import pytest
from pyxb import BIND
from pyxb.bundles.opengis import oseo_1_0 as oseo
from pyxb.bundles.wssplat import soap12
import requests

@pytest.mark.functional
class TestGetCapabilities(object):

    @pytest.mark.skip()
    def test_get_capabilities_no_auth_no_soap(self):
        # will fail because presently our auth scheme requires SOAP
        pass

    #def test_default_get_capabilities(self):
    def test_get_capabilities_no_auth(self, live_server):
        get_caps = oseo.GetCapabilities(service="OS")
        soap_env = soap12.Envelope(Body=BIND(get_caps))
        request_data = soap_env.toxml(encoding="utf-8")
        url = "{0.url}/{1}/".format(live_server, "oseo")
        #url = "http://localhost:8000/oseo/"
        response = requests.post(url, data=request_data)
        response_data = response.text
        print("response_data: {}".format(response_data))
        caps = oseo.CreateFromDocument(response_data)
        print("caps type: {}".format(type(caps)))

    @pytest.mark.skip()
    def test_get_capabilities_no_auth_soap11(self):
        pass

    @pytest.mark.skip()
    def test_get_capabilities_bad_auth_soap12(self):
        pass

    @pytest.mark.skip()
    def test_get_capabilities_good_auth_soap12(self):
        pass
