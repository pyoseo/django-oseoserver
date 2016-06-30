# Copyright 2016 Ricardo Garcia Silva
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Some utility functions for pyoseo
"""

from cStringIO import StringIO
import importlib
import logging

from celery.utils import mail
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from html2text import html2text
from mailqueue.models import MailerMessage
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

from . import settings
from . import constants
from . import errors

logger = logging.getLogger('.'.join(('pyoseo', __name__)))


def import_class(python_path, *instance_args, **instance_kwargs):
    """
    """

    module_path, sep, class_name = python_path.rpartition('.')
    the_module = importlib.import_module(module_path)
    the_class = getattr(the_module, class_name)
    instance = the_class(*instance_args, **instance_kwargs)
    return instance


def get_generic_order_config(order_type):
    """Get the generic configuration for the input order type.

    Parameters
    ----------
    order_type: oseoserver.constants.OrderType
        The enumeration of the order type

    Returns
    -------
    dict
        The configuration parameters that are defined in the settings
        for the selected order_type

    """

    setting = getattr(settings, "get_{}".format(order_type.value.lower()))
    return setting()


def get_order_configuration(order_type, collection):
    """Get the configuration for the input order type and collection.

    Parameters
    ----------
    collection: str
        The requested collection
    order_type: oseoserver.constants.OrderType
        The requested order type

    Returns
    -------
    dict
        A dictionary with the configuration of the requested collection

    """

    for collection_config in settings.get_collections():
        is_collection = collection_config.get("name") == collection
        type_specific_config = collection_config.get(
            order_type.value.lower(), {})
        is_enabled = type_specific_config.get("enabled", False)
        if is_collection and is_enabled:
            result = type_specific_config
            break
    else:
        if order_type in (constants.OrderType.PRODUCT_ORDER,
                          constants.OrderType.MASSIVE_ORDER):
            raise errors.ProductOrderingNotSupportedError()
        elif order_type == constants.OrderType.SUBSCRIPTION_ORDER:
            raise errors.SubscriptionNotSupportedError()
        elif order_type == constants.OrderType.TASKING_ORDER:
            raise errors.FutureProductNotSupportedError()
        else:
            raise errors.OseoServerError(
                "Unable to get order configuration")
    return result


def get_option_configuration(option_name):
    for option in settings.get_processing_options():
        if option["name"] == option_name:
            return option
    else:
        raise errors.OseoServerError("Invalid option {!r}".format(option_name))



def validate_collection_id(collection_id):
    for collection_config in settings.get_collections():
        if collection_config.get("collection_identifier") == collection_id:
            result = collection_config
            break
    else:
        raise errors.InvalidParameterValueError("collectionId")
    return result


def get_collection_settings(collection_name):
    for collection_config in settings.get_collections():
        if collection_config["name"] == collection_name:
            result = collection_config
            break
    else:
        raise errors.OseoServerError(
            "Invalid collection: {!r}".format(collection_name))
    return result


def validate_processing_option(name, value, order_type, collection_name):
    """Validate the input arguments against the configured options"""

    # 1. can this option be used with the current collection and order_type?
    collection_config = get_order_configuration(order_type, collection_name)
    if name not in collection_config.get("options", []):
        raise errors.InvalidParameterValueError("option", value=name)

    # 2. Lets get the parsed value for the option using the external
    #    item_processor
    item_processor_class_path = get_generic_order_config(
        order_type)["item_processor"]
    try:
        item_processor = import_class(item_processor_class_path)
        parsed_value = item_processor.parse_option(name, value)
    except AttributeError:
        raise errors.OseoServerError(
            "Incorrectly configured "
            "item_processor: {}".format(item_processor_class_path)
        )

    # 3. is the parsed value legal?
    for option in settings.get_processing_options():
        if option.get("name") == name:
            choices = option.get("choices", [])
            if parsed_value not in choices and len(choices) > 0:
                raise errors.InvalidParameterValueError("option",
                                                        value=parsed_value)
            break
    else:
        raise errors.InvalidParameterValueError("option", value=parsed_value)
    return parsed_value


def get_item_processor(customizable_item):
    """Return an instance of customizable item's item processor

    Parameters
    ----------
    customizable_item: models.Order or models.OrderItem
        The django model instance representing the current item or order

    """

    try:
        order_type = constants.OrderType(
            customizable_item.batch.order.order_type)
    except AttributeError:
        order_type = constants.OrderType(
            customizable_item.order_type)
    generic_order_config_func = getattr(
        settings, "get_{}".format(order_type.value.lower()))
    generic_order_config = generic_order_config_func()
    processor_class_path = generic_order_config.get("item_processor")
    return import_class(processor_class_path)


# FIXME: Remove this function, it is not needed anymore
def get_custom_code(generic_order_configuration, processing_step):
    item_processor = generic_order_configuration["processor"]
    processing_class = item_processor.python_path
    params = item_processor.export_params(processing_step)
    logger.debug('processing_class: {}'.format(processing_class))
    logger.debug('params: {}'.format(params))
    return processing_class, params


# FIXME: Remove this function, it is not needed anymore
def get_processor(order_type, processing_step,
                  *instance_args, **instance_kwargs):
    processing_class, params = get_custom_code(order_type, processing_step)
    instance = import_class(processing_class, *instance_args, **instance_kwargs)
    return instance, params


def send_moderation_email(order):
    domain = settings.get_site_domain()
    moderation_uri = reverse(
        'admin:oseoserver_orderpendingmoderation_changelist')
    url = "http://{}{}".format(domain, moderation_uri)
    template = "order_waiting_moderation.html"
    context = {
        "order": order,
        "moderation_url": url,
    }
    msg = render_to_string(template, context)
    subject = "Copernicus Global Land Service - {} {} awaits " \
              "moderation".format(order.order_type, order.id)
    UserModel = get_user_model()
    recipients = UserModel.objects.filter(is_staff=True).exclude(email="")
    send_email(subject, msg, recipients, html=True)


def send_cleaning_error_email(order_type, file_paths, error):
    details = "\n".join(file_paths)
    msg = ("Deleting expired files from {} has failed deleting the following "
           "files:\n\n{}\n\nThe error was:\n\n{}".format(order_type.name,
                                                         details,
                                                         error))
    UserModel = get_user_model()
    send_email(
        "Error deleting expired files",
        msg,
        UserModel.objects.filter(is_staff=True).exclude(email="")
    )


def send_batch_packaging_failed_email(batch, error):
    msg = ("There has been an error packaging batch {}. The error "
          "was:\n\n\{}".format(batch, error))
    UserModel = get_user_model()
    send_email(
        "Error packaging batch {}".format(batch),
        msg,
        UserModel.objects.filter(is_staff=True).exclude(email="")
    )


def send_subscription_moderated_email(order, approved, recipients,
                                      acceptance_details="",
                                      rejection_details=""):

    collections = [i.collection for i in
                   order.batches.first().order_items.all()]
    collections = []
    for item in order.batches.first().order_items.all():
        collections.append((i.collection, i.selected_options.all()))
    template = "subscription_moderated.html"
    context = {
        "order": order,
        "collections": collections,
        "approved": approved,
        "details": acceptance_details if approved else rejection_details,
        }
    subject = "Copernicus Global Land Service - Subscription has " \
              "been {}".format("accepted" if approved else "rejected")
    msg = render_to_string(template, context)
    send_email(subject, msg, recipients, html=True)


def send_subscription_batch_available_email(batch):
    urls = []
    collections = set()
    for oi in batch.order_items.all():
        for oseo_file in oi.files.all():
            urls.append(oseo_file.url)
            collections.add(oi.collection)
    context = {
        "batch": batch,
        "urls": urls,
        "collections": collections,
    }
    template = "subscription_batch_available.html"
    subject = "Copernicus Global Land Service - Subscription files available"
    msg = render_to_string(template, context)
    recipients = [batch.order.user]
    send_email(subject, msg, recipients, html=True)


def send_product_batch_available_email(batch):
    urls = []
    for oi in batch.order_items.all():
        for oseo_file in oi.files.all():
            urls.append(oseo_file.url)
    context = {
        "batch": batch,
        "urls": urls,
        }
    template = "normal_product_batch_available.html"
    subject = "Copernicus Global Land Service - Order {} available".format(
        batch.order.id)
    msg = render_to_string(template, context)
    recipients = [batch.order.user]
    send_email(subject, msg, recipients, html=True)


def send_failed_attempt_email(order_id, item_id, message):
    full_message = "Order: {}\n\tOrderItem: {}\n\n\t".format(
        order_id, item_id)
    full_message += message
    subject = ("Copernicus Global Land Service - Unsuccessful processing "
               "attempt")
    UserModel = get_user_model()
    recipients = UserModel.objects.filter(is_staff=True).exclude(email="")
    send_email(subject, full_message, recipients, html=True)


def send_invalid_request_email(request_data, exception_report):
    request = File(
        StringIO(request_data),
        name="request_data.xml"
    )
    exception_report = File(
        StringIO(exception_report),
        name="exception_report.xml"
    )
    template = "invalid_request.html"
    msg = render_to_string(template)
    subject = ("Copernicus Global Land Service - Received invalid request")
    recipients = get_user_model().objects.filter(
        is_staff=True).exclude(email="")
    send_email(
        subject, msg, recipients,
        html=True, attachments=[request, exception_report]
    )


def send_email(subject, message, recipients, html=False, attachments=None):
    """Send emails

    Parameters
    ----------
    subject: str
        The subject of the email
    message: str
        Body of the email
    recipients: list
        An iterable with django users representing the recipients of the email
    html: bool, optional
        Whether the e-mail should be sent in HTML or plain text
    """

    already_emailed = []
    for recipient in recipients:
        address = recipient.email
        if address != "" and address not in already_emailed:
            msg = MailerMessage(
                subject=subject,
                to_address=address,
                from_address=django_settings.EMAIL_HOST_USER,
                app="oseoserver"
            )
            if html:
                text_content = html2text(message)
                msg.content = text_content
                msg.html_content = message
            else:
                msg.content = message
            if attachments is not None:
                for a in attachments:
                    msg.add_attachment(a)
            msg.save()
            already_emailed.append(address)

def _c(value):
    """
    Convert between a None and an empty string.

    This function translates pyxb's empty elements, which are stored as
    None into django's empty values, which are stored as an empty string.
    """

    return '' if value is None else str(value)

def _n(value):
    """
    Convert between an empty string and a None

    This function is translates django's empty elements, which are stored
    as empty strings into pyxb empty elements, which are stored as None.
    """

    return None if value == '' else value


class OseoCeleryErrorMail(mail.ErrorMail):

    def format_body(self, context):
        template = "order_item_failed.html"
        context["highlighted_exc"] = highlight(
            context["exc"], PythonLexer(), HtmlFormatter())
        context["highlighted_traceback"] = highlight(
            context["traceback"], PythonLexer(), HtmlFormatter())
        msg = render_to_string(template, context)
        return msg

    def format_subject(self, context):
        subject = "Copernicus Global Land Service - Task error"
        return subject

    def send(self, context, exc, fail_silently=True):
        if self.should_send(context, exc):
            UserModel = get_user_model()
            send_email(
                self.format_subject(context),
                self.format_body(context),
                UserModel.objects.filter(is_staff=True).exclude(email=""),
                html=True
            )
