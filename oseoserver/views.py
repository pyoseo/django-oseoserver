from __future__ import absolute_import
import logging

from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt
from lxml import etree

from .constants import ENCODING
from . import errors
from . import soap
from .server import OseoServer

logger = logging.getLogger(__name__)


# TODO: Add authorization controls
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
    soap_fault_code = None
    server = OseoServer()
    try:
        request_element = etree.fromstring(request.body)
        soap_version = soap.get_soap_version(request_element)
        request_data = soap.unwrap_request(request_element)[0]
        logger.debug("user: {}".format(request.user))
        if request.user is None or not request.user.is_active:
            logger.error("authentication failed: {}".format(request.user))
            raise errors.OseoError(
                code="AuthenticationFailed",
                text="Invalid or missing identity information"
            )
        response = server.process_request(request_data, request.user)
        status_code = 200
    except errors.OseoError as err:
        logger.error(err)
        response = server.create_exception_report(
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


# TODO - This view does not belong in the oseoserver. Order item availability
#        is to be handled by custom code, in a similar fashion as order item
#        processing
#def get_ordered_file(request, user_name, order_id, item_id, file_name):
#    """Handle delivery of order items that specify HTTP as method."""
#
#    UserModel = get_user_model()
#    try:
#        user = UserModel.objects.get(username=user_name)
#        order = models.Order.objects.get(pk=int(order_id))
#        if order.user != user:
#            raise RuntimeError  # this user cannot access the order
#        else:
#            # 3. convert the url into a file system path
#            full_url = request.build_absolute_uri()
#            full_url = full_url[:-1] if full_url.endswith('/') else full_url
#
#            # 4. retrieve the file
#            order_item = models.OrderItem.objects.get(
#                batch__order__id=int(order_id), item_id=item_id)
#            item_processor = utilities.get_item_processor(order_item)
#            path = item_processor.get_file_path(full_url)
#
#            # 5. update oseoserver's database
#            if order_item.available:
#                order_item.downloads += 1
#                order_item.last_downloaded_at = datetime.now(pytz.utc)
#                order_item.save()
#                result = sendfile(request, path, attachment=True,
#                                  attachment_filename=os.path.basename(path),
#                                  mimetype=_get_mime_type(path), encoding="utf8")
#            else:
#                raise IOError  # the order is not available anymore
#    except (UserModel.DoesNotExist, RuntimeError):
#        result = HttpResponseForbidden()
#    except IOError:
#        result = HttpResponseNotFound()
#    return result
#
#
#def _get_mime_type(path):
#    mime_map = {
#        "application/x-hdf": [".h5", ""],
#        "application/zip": [".zip",],
#        "application/x-bzip2": [".bz2",],
#    }
#    path_mime = None
#    ext = os.path.splitext(path)
#    for k, v in mime_map.iteritems():
#        if ext in v:
#            path_mime = k
#    return path_mime

