import logging
try:
    from io import StringIO
except ImportError:  # python2
    from StringIO import StringIO

from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.core.files import File
from html2text import html2text
from django.conf import settings as django_settings
from mailqueue.models import MailerMessage

from . import settings as oseo_settings
from .models import Order

logger = logging.getLogger(__name__)

MAIL_SUBJECT = "Copernicus Global Land Service"


def send_moderation_request_email(order_type, order_id):
    """Send an e-mail to admins informing that an order needs approval.

    Parameters
    ----------
    order_type: str
        The type of order that is waiting to be moderated
    order_id: int
        The order's id in the database

    """

    domain = Site.objects.get_current().domain
    moderation_uri = reverse(
        'admin:oseoserver_orderpendingmoderation_changelist')
    url = "http://{}{}".format(domain, moderation_uri)
    template = "order_waiting_moderation.html"
    context = {
        "order_type": order_type,
        "order_id": order_id,
        "moderation_url": url,
    }
    msg = render_to_string(template, context)
    subject = "Copernicus Global Land Service - {} {} awaits " \
              "moderation".format(order_type, order_id)
    UserModel = get_user_model()
    recipients = UserModel.objects.filter(is_staff=True).exclude(email="")
    if any(recipients):
        send_email(subject, msg, recipients, html=True)
    else:
        logger.warning(
            "Could not dispatch order moderation e-mail for {0}:{1} - None "
            "of the admin users has a valid e-mail.".format(order_type,
                                                            order_id)
        )


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


def send_order_cancelled_email(order, recipients):
    template = "order_cancelled.html"
    context = {
        "order_type": order.order_type,
        "reference": order.reference,
        "details": order.additional_status_info,
    }
    subject = ("Copernicus Global Land Service - {0.order_type} {0.reference} "
               "has been cancelled".format(order))
    msg = render_to_string(template, context)
    send_email(subject, msg, recipients, html=True)


def send_subscription_moderated_email(order, approved, recipients):
    """Notify recipients via e-mail that subscription has been moderated.

    Parameters
    ----------
    order: oseoserver.models.Order
        The order that has been moderated
    approved: bool
        The moderation result
    recipients: list
        An iterable with the e-mail addresses to be notified

    """

    subscription_order_settings = oseo_settings.get_subscription_order()
    item_availability_days = subscription_order_settings[
        "item_availability_days"]
    collections = []
    for item in order.item_specifications.all():
        collections.append((item.collection, item.selected_options.all()))
    template = "subscription_moderated.html"
    context = {
        "order": order,
        "collections": collections,
        "approved": approved,
        "item_availability_days": item_availability_days,
    }
    subject = "Copernicus Global Land Service - Subscription has " \
              "been {}".format("accepted" if approved else "rejected")
    msg = render_to_string(template, context)
    send_email(subject, msg, recipients, html=True)


def send_product_order_moderated_email(order, approved, recipients):
    product_order_settings = oseo_settings.get_product_order()
    item_availability_days = product_order_settings["item_availability_days"]
    template = "productorder_moderated.html"
    context = {
        "order": order,
        "approved": approved,
        "item_availability_days": item_availability_days,
    }
    subject = " - ".join((
        MAIL_SUBJECT,
        "Order {reference!r} has been {status}".format(
            reference=order.reference,
            status=order.status.lower()
        )
    ))
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
    logger.warning("Received invalid request. Notifying admins...")
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
