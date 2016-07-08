from __future__ import absolute_import
import os
import os.path
from datetime import datetime
import logging

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.http import HttpResponseBadRequest
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404, get_list_or_404
from django.views.decorators.csrf import csrf_exempt
from lxml import etree
from sendfile import sendfile

from .constants import ENCODING
from . import errors
from . import models
from . import utilities
from . import settings
from . import soap
from .server import OseoServer
from .signals import signals

logger = logging.getLogger(__name__)


@csrf_exempt
def oseo_endpoint(request):
    """OSEO endpoint.

    This view receives the HTTP request from the webserver's WSGI handler.
    It is responsible for validating that a POST request was received,
    instantiating :class:`oseoserver.server.OseoServer` and handing it
    the request. It then returns the response back to the web server.

    """

    if not request.method == "POST":  # OSEO requests must always be POST
        return HttpResponseForbidden()
    soap_version = None
    server = OseoServer()
    headers = {}
    try:
        request_element = etree.fromstring(request.body)
        soap_version = soap.get_soap_version(request_element)
        headers = soap.get_http_headers(soap_version)
        details = soap.unwrap_request(request_element)
        request_data, username, password, password_attributes = details
        user = authenticate(username=username, password=password,
                            password_attributes=password_attributes)
        logger.debug("user: {}".format(user))
        if user is None or not user.is_active:
            raise errors.OseoError(
                code="AuthenticationFailed",
                text="Invalid or missing identity information"
            )
        # TODO: Add authorization controls
        process_response = server.process_request(request_data, user)
        status_code = 200
        if soap_version is None:
            response = process_response
        else:
            response = soap.wrap_response(process_response,
                                          soap_version)
    except errors.OseoError as err:
        if err.code == "AuthorizationFailed":
            status_code = 401
        else:
            status_code = 400
        exception_report = server.create_exception_report(
            err.code, err.text, err.locator)
        if soap_version is None:
            response = exception_report
        else:
            soap_fault_code = soap.get_soap_fault_code(err.code)
            response = soap.wrap_soap_fault(
                exception_element=exception_report,
                soap_code=soap_fault_code,
                soap_version=soap_version
            )
        logger.exception("Received invalid request. Notifying admins...")
        utilities.send_invalid_request_email(
            request_data=request.body,
            exception_report=etree.tostring(exception_report,
                                            pretty_print=True),
        )
    except (errors.InvalidSoapVersionError, etree.XMLSyntaxError,
            errors.ServerError):
        raise
    serialized = etree.tostring(response, encoding=ENCODING,
                                pretty_print=True)
    django_response = HttpResponse(serialized)
    django_response.status_code = status_code
    for k, v in headers.items():
        django_response[k] = v
    return django_response


def get_ordered_file(request, user_name, order_id, item_id, file_name):
    """
    Handle delivery of order items that specify HTTP as method.

    :param request:
    :param user_name:
    :param order_id:
    :param item_id:
    :param file_name:
    :return:
    """

    # 1. authenticate the user
    # 2. authorize the user

    # 3. convert the url into a file system path
    full_uri = request.build_absolute_uri()
    full_uri = full_uri[:-1] if full_uri.endswith('/') else full_uri
    # 4. retrieve the file
    order_type = models.Order.objects.get(id=order_id).order_type
    # TODO: replace PROCESSING_PROCESS_ITEM with a more suitable processing_step
    processor, params = utilities.get_processor(
        order_type, models.ItemProcessor.PROCESSING_PROCESS_ITEM)
    path = processor.get_file_path(full_uri)
    # 5. update oseoserver's database
    oseo_file = get_object_or_404(models.OseoFile, url=full_uri)
    if oseo_file.available:
        oseo_file.downloads += 1
        oseo_file.last_downloaded_at = datetime.utcnow()
        oseo_file.save()
        result = sendfile(request, path, attachment=True,
                          attachment_filename=os.path.basename(path),
                          mimetype=_get_mime_type(path), encoding="utf8")
    else:
        result = HttpResponseNotFound("The requested file is not available")
    return result


def get_ordered_packaged_files(request, user_name, order_id, package_name):
    """
    Handle delivery of order items that specify zip packaging and HTTP.

    :param request:
    :param user_name:
    :param order_id:
    :param package_name:
    :return:
    """

    # 1. authenticate the user
    # 2. authorize the user

    # 3. convert the url into a file system path
    full_uri = request.build_absolute_uri()
    full_uri = full_uri[:-1] if full_uri.endswith('/') else full_uri
    # 4. retrieve the file
    order_type = models.Order.objects.get(id=order_id).order_type
    # TODO: replace PROCESSING_PROCESS_ITEM with a more suitable processing_step
    processor, params = utilities.get_processor(
        order_type, models.ItemProcessor.PROCESSING_PROCESS_ITEM)
    path = processor.get_file_path(full_uri)
    # 5. update oseoserver's database
    oseo_files = get_list_or_404(models.OseoFile, url=full_uri)
    if any(oseo_files) and oseo_files[0].available:
        for f in oseo_files:
            f.downloads += 1
            f.last_downloaded_at = datetime.utcnow()
            f.save()
        result = sendfile(request, path, attachment=True,
                          attachment_filename=os.path.basename(path),
                          mimetype=_get_mime_type(path), encoding="utf8")
    else:
        result = HttpResponseNotFound("The requested file is not available")
    return result


def _get_mime_type(path):
    mime_map = {
        "application/x-hdf": [".h5", ""],
        "application/zip": [".zip",],
        "application/x-bzip2": [".bz2",],
    }
    path_mime = None
    ext = os.path.splitext(path)
    for k, v in mime_map.iteritems():
        if ext in v:
            path_mime = k
    return path_mime

