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

import datetime as dt
import pytz
from cStringIO import StringIO

from django.dispatch import receiver
from django.db.models.signals import post_save, post_init, pre_save
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.core.files import File

from . import signals
from .. import models
from .. import utilities
from ..constants import OrderStatus
from ..constants import OrderType
from ..constants import StatusNotification


@receiver(post_init, sender=models.TaskingOrder, weak=False,
          dispatch_uid='id_for_get_old_status_tasking_order')
@receiver(post_init, sender=models.SubscriptionOrder, weak=False,
          dispatch_uid='id_for_get_old_status_subscription_order')
@receiver(post_init, sender=models.MassiveOrder, weak=False,
          dispatch_uid='id_for_get_old_status_massive_order')
@receiver(post_init, sender=models.ProductOrder, weak=False,
          dispatch_uid='id_for_get_old_status_product_order')
@receiver(post_init, sender=models.Order, weak=False,
          dispatch_uid='id_for_get_old_status_order')
def get_old_status_order(sender, **kwargs):
    order = kwargs['instance']
    order.old_status = order.status


@receiver(pre_save, sender=models.TaskingOrder, weak=False,
          dispatch_uid='id_for_update_status_changed_on_tasking_order')
@receiver(pre_save, sender=models.SubscriptionOrder, weak=False,
          dispatch_uid='id_for_update_status_changed_on_subscription_order')
@receiver(pre_save, sender=models.MassiveOrder, weak=False,
          dispatch_uid='id_for_update_status_changed_on_massive_order')
@receiver(pre_save, sender=models.ProductOrder, weak=False,
          dispatch_uid='id_for_update_status_changed_on_product_order')
@receiver(pre_save, sender=models.Order, weak=False,
          dispatch_uid='id_for_update_status_changed_on_order')
def update_status_changed_on_order(sender, **kwargs):
    order = kwargs['instance']
    if order.status_changed_on is None or order.status != order.old_status:
        order.status_changed_on = dt.datetime.now(pytz.utc)
        signals.order_status_changed.send_robust(sender=sender, instance=order,
                                                 old_status=order.old_status,
                                                 new_status=order.status)
        sig = {
            OrderStatus.SUBMITTED.value: signals.order_submitted,
            OrderStatus.ACCEPTED.value: signals.order_accepted,
            OrderStatus.IN_PRODUCTION.value: signals.order_in_production,
            OrderStatus.FAILED.value: signals.order_failed,
            OrderStatus.COMPLETED.value: signals.order_completed,
            OrderStatus.DOWNLOADED.value: signals.order_downloaded,
            OrderStatus.CANCELLED.value: signals.order_cancelled,
            OrderStatus.TERMINATED.value: signals.order_terminated,
        }[order.status]
        sig.send_robust(sender=sender, instance=order)
        order.old_status = order.status


@receiver(post_init, sender=models.OrderItem, weak=False,
          dispatch_uid='id_for_get_old_status_order_item')
def get_old_status_order_item(sender, **kwargs):
    order_item = kwargs['instance']
    order_item.old_status = order_item.status


@receiver(pre_save, sender=models.OrderItem, weak=False,
          dispatch_uid='id_for_update_status_changed_on_order_item')
def update_status_changed_on_by_order_item(sender, **kwargs):
    order_item = kwargs['instance']
    if order_item.status_changed_on is None or \
            order_item.status != order_item.old_status:
        order_item.status_changed_on = dt.datetime.now(pytz.utc)


@receiver(post_save, sender=models.OrderItem, weak=False,
          dispatch_uid='id_for_update_batch')
def update_batch(sender, **kwargs):
    order_item = kwargs["instance"]
    batch = order_item.batch
    now = dt.datetime.now(pytz.utc)
    batch.updated_on = now
    status = batch.status()
    if status in (OrderStatus.COMPLETED.value, OrderStatus.FAILED.value,
                  OrderStatus.TERMINATED.value):
        batch.completed_on = now
    elif status == OrderStatus.DOWNLOADED.value:
        pass
    else:
        batch.completed_on = None


@receiver(signals.order_status_changed, weak=False,
          dispatch_uid='id_for_handle_order_status_change')
def handle_order_status_change(sender, **kwargs):
    """Handle OSEO notifications to the user whenever an order changes status

    This handler should delegate to the appropriate OSEO async operation class
    (something which is not implemented yet)
    """

    order = kwargs["instance"]
    old = OrderStatus(kwargs["old_status"])
    new = OrderStatus(kwargs["new_status"])
    if order.status_notification == StatusNotification.ALL.value:
        # send and OSEO notification
        print("Order {0} status has changed from {1.value} "
              "to {2.value}".format(order, old, new))
    elif order.status_notification == StatusNotification.FINAL.value:
        if new in (OrderStatus.CANCELLED, OrderStatus.COMPLETED,
                   OrderStatus.FAILED, OrderStatus.TERMINATED):
            # send an OSEO notification
            print("Order {0} has reached a FINAL status of "
                  "{1.value}".format(order, old))


@receiver(signals.order_submitted, weak=False,
          dispatch_uid='id_for_handle_order_submission')
def handle_order_submission(sender, **kwargs):
    order = kwargs["instance"]
    generic_order_config = utilities.get_generic_order_config(
        OrderType(order.order_type))
    automatic_approval = generic_order_config.get("automatic_approval", False)
    if order.status == OrderStatus.SUBMITTED.value and not automatic_approval:
        # send email asking admins to moderate the order
        print("Order {} must be moderated by an admin before continuing to "
              "be processed".format(order))
        # where's the code that sends email?


@receiver(signals.order_failed, weak=False,
          dispatch_uid='id_for_handle_order_failure')
def handle_order_failure(sender, **kwargs):
    """Notify the staff by e-mail that an order has failed

    :param sender:
    :param kwargs:
    :return:
    """

    order = kwargs["instance"]
    if order.status == OrderStatus.FAILED.value:
        print("Order {} has failed.".format(order))
        details = [d.replace("* Order item ", "").split(":") for d in
                   order.additional_status_info.split("\n")]
        template = "order_failed.html"
        context = {
            "order": order,
            "details": details,
        }
        msg = render_to_string(template, context)
        subject = ("Copernicus Global Land Service - Order {} has "
                   "failed".format(order))
        recipients = User.objects.filter(is_staff=True).exclude(email="")
        utilities.send_email(subject, msg, recipients, html=True)


@receiver(signals.invalid_request, weak=False,
          dispatch_uid="id_for_handle_invalid_request")
def handle_invalid_request(sender, **kwargs):
    print("received invalid request")
    template = "invalid_request.html"
    request_data = File(StringIO(kwargs["request_data"]),
                        name="request_data.xml")
    exception_report = File(StringIO(kwargs["exception_report"]),
                            name="exception_report.xml")
    msg = render_to_string(template)
    subject = ("Copernicus Global Land Service - Received invalid request")
    recipients = User.objects.filter(is_staff=True).exclude(email="")
    utilities.send_email(
        subject, msg, recipients,
        html=True, attachments=[request_data, exception_report]
    )

