from __future__ import absolute_import
import logging

from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from lxml import etree
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.response import Response

from .constants import ENCODING
from . import errors
from . import models
from . import serializers
from . import soap
from . import requestprocessor
from .utilities import get_etree_parser

logger = logging.getLogger(__name__)


class SubscriptionOrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Order.objects.filter(
        order_type=models.Order.SUBSCRIPTION_ORDER)
    serializer_class = serializers.SubscriptionOrderSerializer

    @detail_route(methods=["POST",])
    def cancel(self, request, *args, **kwargs):
        subscription = self.get_object()
        logger.debug("Would cancel subscription {0.id}".format(subscription))
        return Response()


class SubscriptionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Batch.objects.filter(
        order__order_type=models.Order.SUBSCRIPTION_ORDER)
    serializer_class = serializers.SubscriptionBatchSerializer

    @detail_route(methods=["POST",])
    def clean(self, request, *args, **kwargs):
        batch = self.get_object()
        logger.debug("Would clean subscription "
                     "batch {0.id}".format(subscription))
        return Response()


# TODO: Add authorization controls
@csrf_exempt
def oseo_endpoint(request):
    """OSEO endpoint.

    This view receives the HTTP request from the webserver's WSGI handler.
    It is responsible for validating that a POST request was received
    handing it to a request processor. It then returns the response back to
    the web server.

    """

    if not request.method == "POST":  # OSEO requests must always be POST
        return HttpResponseForbidden()
    soap_version = None
    soap_fault_code = None
    try:
        request_element = etree.fromstring(
            request.body, parser=get_etree_parser())
        soap_version = soap.get_soap_version(request_element)
        request_data = soap.unwrap_request(request_element)[0]
        logger.debug("user: {}".format(request.user))
        if request.user is None or not request.user.is_active:
            logger.error("authentication failed: {}".format(request.user))
            raise errors.OseoError(
                code="AuthenticationFailed",
                text="Invalid or missing identity information"
            )
        response = requestprocessor.process_request(request_data, request.user)
        status_code = 200
    except errors.OseoError as err:
        logger.error(err)
        response = requestprocessor.create_exception_report(
            err.code, err.text, err.locator)
        status_code = 401 if err.code == "AuthorizationFailed" else 400
        soap_fault_code = soap.get_soap_fault_code(err.code)
        #utilities.send_invalid_request_email(
        #    request_data=request.body,
        #    exception_report=etree.tostring(response, pretty_print=True),
        #)
    wrapped = _wrap_response(response, soap_version=soap_version,
                             soap_code=soap_fault_code)
    serialized = etree.tostring(wrapped, encoding=ENCODING, pretty_print=True)
    django_response = HttpResponse(serialized)
    django_response.status_code = status_code
    for k, v in _get_response_headers(soap_version).items():
        django_response[k] = v
    return django_response


def _get_response_headers(soap_version=None):
    headers = {}
    if soap_version is not None:
        headers["Content-Type"] = soap.get_response_content_type(soap_version)
    return headers


def _wrap_response(response_element, soap_version=None, soap_code=None):
    """Wrap the response in a SOAP envelope, if needed

    Parameters
    ----------
    response_element: etree.Element
        The already processed response
    soap_version: str, optional
        Version of SOAP in use
    soap_code: str, optional
        SOAP code to use for SOAP faults.

    """

    if soap_code is not None:
        result = soap.wrap_soap_fault(
            response_element, soap_code, soap_version)
    elif soap_version is not None:
        result = soap.wrap_response(response_element, soap_version)
    else:
        result = response_element
    return result

