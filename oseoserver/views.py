from __future__ import absolute_import
import os
import os.path
from datetime import datetime
import logging
import pytz

from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from lxml import etree
from sendfile import sendfile

from .constants import ENCODING
from . import errors
from . import models
from . import utilities
from . import soap
from .server import OseoServer

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
    """Handle delivery of order items that specify HTTP as method."""

    UserModel = get_user_model()
    try:
        user = UserModel.objects.get(username=user_name)
        order = models.Order.objects.get(pk=int(order_id))
        if order.user != user:
            raise RuntimeError  # this user cannot access the order
        else:
            # 3. convert the url into a file system path
            full_url = request.build_absolute_uri()
            full_url = full_url[:-1] if full_url.endswith('/') else full_url

            # 4. retrieve the file
            order_item = models.OrderItem.objects.get(
                batch__order__id=int(order_id), item_id=item_id)
            item_processor = utilities.get_item_processor(order_item)
            path = item_processor.get_file_path(full_url)

            # 5. update oseoserver's database
            if order_item.available:
                order_item.downloads += 1
                order_item.last_downloaded_at = datetime.now(pytz.utc)
                order_item.save()
                result = sendfile(request, path, attachment=True,
                                  attachment_filename=os.path.basename(path),
                                  mimetype=_get_mime_type(path), encoding="utf8")
            else:
                raise IOError  # the order is not available anymore
    except (UserModel.DoesNotExist, RuntimeError):
        result = HttpResponseForbidden()
    except IOError:
        result = HttpResponseNotFound()
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

