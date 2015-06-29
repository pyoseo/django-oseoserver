import os
import os.path
from datetime import datetime

from django.http import (HttpResponse, HttpResponseForbidden,
                         HttpResponseNotFound)
from django.shortcuts import get_object_or_404, get_list_or_404
from django.views.decorators.csrf import csrf_exempt
from sendfile import sendfile

from . import server
from . import models
from . import utilities


@csrf_exempt
def oseo_endpoint(request):
    """
    Django's endpoint to pyoseo.

    This view receives the HTTP request from the webserver's WSGI handler.
    It is responsible for validating that a POST request was received,
    instantiating :class:`oseoserver.server.OseoServer` and handing it
    the request. It then returns the response back to the web server.
    """

    if request.method == 'POST':
        s = server.OseoServer()
        resp, status_code, headers = s.process_request(request.body)
        response = HttpResponse(resp)
        for k, v in headers.iteritems():
            response[k] = v
    else:
        response = HttpResponseForbidden()
    return response


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

