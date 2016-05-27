"""Functions for dealing with SOAP in oseoserver."""

from __future__ import absolute_import

from lxml import etree

from .constants import NAMESPACES
from .errors import NonSoapRequestError
from .auth import usernametoken


def get_soap_version(request_element):
    """Return a request's SOAP version"""
    qname = etree.QName(request_element.tag)
    if qname.localname == "Envelope":
        if qname.namespace == NAMESPACES['soap']:
            result = "1.2"
        elif qname.namespace == NAMESPACES['soap1.1']:
            result = "1.1"
        else:
            raise NonSoapRequestError("Could not detect SOAP version")
    else:
        result = None
    return result


def get_soap_fault_code(response_text):
    """Retrieve the correct SOAP fault code from a response"""



def get_http_headers(soap_version):
    if soap_version == "1.2":
        content_type = "application/soap+xml"
    elif soap_version == "1.1":
        content_type = "text/xml"
    return {
        "Content-Type": content_type
    }


def unwrap_request(request_element):
    """Remove a request's SOAP envelope."""

    soap_version = get_soap_version(request_element)
    if soap_version is not None:
        body_path = "{}:Body/*".format(soap_version)
        request_data = request_element.xpath(body_path.format(soap_version),
                                             namespaces=NAMESPACES)
        user, password, password_attributes = usernametoken.get_details(
            request_element, soap_version)
    else:
        request_data = request_element
        user = None
        password = None
        password_attributes = None
    return request_data, user, password, password_attributes


def wrap_soap(self, response, soap_version):
    """Wrap the OSEO operation response in a SOAP envelope.

    Parameters
    ----------
    response: str
        The generated response
    soap_version: str
        The version of SOAP to use

    Returns
    -------
    str
        The SOAP-wrapped response

    """

    soap_env_ns = {
        'ows': self._namespaces['ows'],
    }
    if soap_version == '1.2':
        soap_env_ns['soap'] = self._namespaces['soap']
    else:
        soap_env_ns['soap'] = self._namespaces['soap1.1']
    soap_env = etree.Element('{%s}Envelope' % soap_env_ns['soap'],
                             nsmap=soap_env_ns)
    soap_body = etree.SubElement(soap_env, '{%s}Body' %
                                 soap_env_ns['soap'])

    response_string = response.toxml(encoding=self.ENCODING)
    response_string = response_string.encode(self.ENCODING)
    response_element = etree.fromstring(response_string)
    soap_body.append(response_element)
    return etree.tostring(soap_env, encoding=self.ENCODING,
                          pretty_print=True)


def wrap_soap_fault(self, exception_report, soap_code, soap_version):
    """Wrap the ExceptionReport in a SOAP envelope.

    Parameters
    ----------
    exception_report: str
        The generated exception report to wrap
    soap_code: str
        The soap code to use
    soap_version: str
        The version of SOAP to use

    Returns
    -------
    str
        The SOAP-wrapped response


    :arg exception_report: The pyxb instance with the previously generated
                           exception report
    :type exception_report: pyxb.bundles.opengis.ows.ExceptionReport
    :arg soap_code: Can be either 'server' or 'client'
    :type soap_code: str
    :arg soap_version: The SOAP version in use
    :type soap_version: str
    """

    code_msg = 'soap:{}'.format(soap_code.capitalize())
    reason_msg = '{} exception was encountered'.format(
        soap_code.capitalize())
    exception_string = exception_report.toxml(encoding=self.ENCODING)
    exception_string = exception_string.encode(self.ENCODING)
    exception_element = etree.fromstring(exception_string)
    soap_env_ns = {
        'ows': self._namespaces['ows'],
        'xml': self._namespaces['xml'],
    }
    if soap_version == '1.2':
        soap_env_ns['soap'] = self._namespaces['soap']
    else:
        soap_env_ns['soap'] = self._namespaces['soap1.1']
    soap_env = etree.Element('{{{}}}Envelope'.format(soap_env_ns['soap']),
                             nsmap=soap_env_ns)
    soap_body = etree.SubElement(soap_env, '{{{}}}Body'.format(
                                 soap_env_ns['soap']))
    soap_fault = etree.SubElement(soap_body, '{{{}}}Fault'.format(
                                  soap_env_ns['soap']))
    if soap_version == '1.2':
        fault_code = etree.SubElement(soap_fault, '{{{}}}Code'.format(
                                      soap_env_ns['soap']))
        code_value = etree.SubElement(fault_code, '{{{}}}Value'.format(
                                      soap_env_ns['soap']))
        code_value.text = code_msg
        fault_reason = etree.SubElement(soap_fault, '{{{}}}Reason'.format(
                                        soap_env_ns['soap']))
        reason_text = etree.SubElement(fault_reason, '{{{}}}Text'.format(
                                       soap_env_ns['soap']))
        reason_text.set("{{{}}}lang".format(soap_env_ns["xml"]), "en")
        reason_text.text = reason_msg
        fault_detail = etree.SubElement(soap_fault, '{{{}}}Detail'.format(
                                        soap_env_ns['soap']))
        fault_detail.append(exception_element)
    else:
        fault_code = etree.SubElement(soap_fault, 'faultcode')
        fault_code.text = code_msg
        fault_string = etree.SubElement(soap_fault, 'faultstring')
        fault_string.text = reason_msg
        fault_actor = etree.SubElement(soap_fault, 'faultactor')
        fault_actor.text = ''
        detail = etree.SubElement(soap_fault, 'detail')
        detail.append(exception_element)
    return etree.tostring(soap_env, encoding=self.ENCODING,
                          pretty_print=True)
