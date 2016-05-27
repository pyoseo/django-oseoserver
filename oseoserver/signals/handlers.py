# Copyright 2015 Ricardo Garcia Silva
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
from lxml import etree
#from actstream import action

from .. import models
from ..models import CustomizableItem as ci
from . import signals
from ..utilities import send_email


@receiver(post_save, sender=User, weak=False,
          dispatch_uid="id_for_add_user_profile")
def add_user_profile_callback(sender, **kwargs):
    instance = kwargs['instance']
    try:
        profile = models.OseoUser.objects.get(user__id=instance.id)
    except models.OseoUser.DoesNotExist:
        profile = models.OseoUser()
        profile.user = kwargs['instance']
    profile.save()


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
    if order.status_changed_on is None or \
            order.status != order.old_status:
        order.status_changed_on = dt.datetime.now(pytz.utc)
        signals.order_status_changed.send_robust(
            sender=sender,
            instance=order,
            old_status=order.old_status,
            new_status=order.status
        )
        if order.status == ci.SUBMITTED:
            signals.order_submitted.send_robust(sender=sender, instance=order)
        elif order.status == ci.ACCEPTED:
            signals.order_accepted.send_robust(sender=sender, instance=order)
        elif order.status == ci.IN_PRODUCTION:
            signals.order_in_production.send_robust(sender=sender,
                                                    instance=order)
        elif order.status == ci.FAILED:
            signals.order_failed.send_robust(sender=sender, instance=order)
        elif order.status == ci.COMPLETED:
            signals.order_completed.send_robust(sender=sender, instance=order)
        elif order.status == ci.DOWNLOADED:
            signals.order_downloaded.send_robust(sender=sender, instance=order)
        elif order.status == ci.CANCELLED:
            signals.order_cancelled.send_robust(sender=sender, instance=order)
        elif order.status == ci.TERMINATED:
            signals.order_terminated.send_robust(sender=sender, instance=order)
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
    if status in (models.CustomizableItem.COMPLETED,
                          models.CustomizableItem.FAILED,
                          models.CustomizableItem.TERMINATED):
        batch.completed_on = now
    elif status == models.CustomizableItem.DOWNLOADED:
        pass
    else:
        batch.completed_on = None


@receiver(post_save, sender=models.OseoFile, weak=False,
          dispatch_uid="id_for_update_item_status")
def update_item_status(sender, **kwargs):
    """
    Update an order item's status when one of its oseo files is downloaded

    This handler checks if all of an order item's oseo_files have already
    been downloaded and updates the order item's status accordingly.
    """

    oseo_file = kwargs["instance"]
    order_item = oseo_file.order_item
    if order_item.status != models.CustomizableItem.DOWNLOADED and \
            all([f.downloads > 0 for f in order_item.files.all()]):
        order_item.status = models.CustomizableItem.DOWNLOADED
        order_item.save()


@receiver(post_save, sender=models.Collection, weak=False,
          dispatch_uid='id_for_create_order_configurations')
def create_order_configurations(sender, **kwargs):
    c = kwargs["instance"]
    models.ProductOrderConfiguration.objects.get_or_create(collection=c)
    models.MassiveOrderConfiguration.objects.get_or_create(collection=c)
    models.SubscriptionOrderConfiguration.objects.get_or_create(collection=c)
    models.TaskingOrderConfiguration.objects.get_or_create(collection=c)


#@receiver(post_save, sender=models.ProductOrder, weak=False,
#          dispatch_uid='id_for_notify_product_order')
#def notify_product_order(sender, **kwargs):
#    order = kwargs["instance"]
#    user = order.user
#    if kwargs["created"]:
#        if order.order_type.notify_creation:
#            action.send(user, verb="created", target=order)
#    else:
#        if order.status == models.Order.COMPLETED:
#            action.send(order, verb="has been completed")
#        elif order.status == models.Order.FAILED:
#            action.send(order, verb="has failed")


#@receiver(post_save, sender=models.ProductOrder, weak=False,
#          dispatch_uid='id_for_moderate_product_order')
#def moderate_product_order(sender, **kwargs):
#    order = kwargs["instance"]
#    created = kwargs["created"]
#    if created and not order.order_type.automatic_approval:
#        for staff in User.objects.filter(is_staff=True):
#            action.send(order, verb="awaits moderation by",
#                        target=staff.oseouser)


#@receiver(post_save, sender=models.SubscriptionOrder, weak=False,
#          dispatch_uid='id_for_notify_subscription_order')
#def notify_subscription_order(sender, **kwargs):
#    order = kwargs["instance"]
#    user = order.user
#    if kwargs["created"]:
#        if order.order_type.notify_creation:
#            action.send(user, verb="created", target=order)
#    elif order.status == models.Order.CANCELLED:
#        action.send(order, verb="has been cancelled")


#@receiver(post_save, sender=models.SubscriptionBatch, weak=False,
#          dispatch_uid='id_for_notify_subscription_batch')
#def notify_subscription_batch(sender, **kwargs):
#    batch = kwargs["instance"]
#    if kwargs["created"]:
#        action.send(batch, verb="created")


@receiver(signals.order_status_changed, weak=False,
          dispatch_uid='id_for_handle_order_status_change')
def handle_order_status_change(sender, **kwargs):
    """Handle OSEO notifications to the user whenever an order changes status

    This handler should delegate to the appropriate OSEO async operation class
    (something which is not implemented yet)
    """

    order = kwargs["instance"]
    old = kwargs["old_status"]
    new = kwargs["new_status"]
    if order.status_notification == models.Order.ALL:
        # send and OSEO notification
        print("Order {} status has changed from {} to {}".format(order,
                                                                 old, new))
    elif order.status_notification == models.Order.FINAL:
        final_statuses = [ci.CANCELLED, ci.COMPLETED, ci.FAILED, ci.TERMINATED]
        if new in final_statuses:
            # send an OSEO notification
            print("Order {} has reached a FINAL status of {}".format(order,
                                                                     old))


@receiver(signals.order_submitted, weak=False,
          dispatch_uid='id_for_handle_order_submission')
def handle_order_submission(sender, **kwargs):
    order = kwargs["instance"]
    if order.status == ci.SUBMITTED and not order.order_type.automatic_approval:
        # send the email asking admins to moderate the order
        print("Order {} must be moderated by an admin before continuing to "
              "be processed".format(order))


@receiver(signals.order_failed, weak=False,
          dispatch_uid='id_for_handle_order_failure')
def handle_order_failure(sender, **kwargs):
    """Notify the staff by e-mail that an order has failed

    :param sender:
    :param kwargs:
    :return:
    """

    order = kwargs["instance"]
    if order.status == ci.FAILED:
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
        send_email(subject, msg, recipients, html=True)


@receiver(signals.invalid_request, weak=False,
          dispatch_uid="id_for_handle_invalid_request")
def handle_invalid_request(sender, **kwargs):
    print("received invalid request")
    template = "invalid_request.html"
    request_data = File(StringIO(kwargs["request_data"]),
                        name="request_data.xml")
    exception_report_string = etree.tostring(kwargs["exception_report"],
                                             pretty_print=True)
    exception_report = File(StringIO(kwargs["exception_report"]),
                            name="exception_report.xml")
    msg = render_to_string(template)
    subject = ("Copernicus Global Land Service - Received invalid request")
    recipients = User.objects.filter(is_staff=True).exclude(email="")
    send_email(
        subject, msg, recipients,
        html=True, attachments=[request_data, exception_report]
    )

