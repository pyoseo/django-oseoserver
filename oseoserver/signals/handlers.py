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
try:
    from io import StringIO
except ImportError:  # python2
    from StringIO import StringIO
import logging

from django.dispatch import receiver
from django.db.models.signals import post_save, post_init, pre_save

from . import signals
from ..models import CustomizableItem
from ..models import Order
from ..models import OrderItem
from .. import utilities

logger = logging.getLogger(__name__)


@receiver(post_init, sender=Order, weak=False,
          dispatch_uid='id_for_get_old_status_order')
def get_old_status_order(sender, **kwargs):
    order = kwargs['instance']
    order.old_status = order.status


@receiver(pre_save, sender=Order, weak=False,
          dispatch_uid='id_for_update_status_changed_on_order')
def update_status_changed_on_order(sender, **kwargs):
    order = kwargs['instance']
    if order.status_changed_on is None or order.status != order.old_status:
        order.status_changed_on = dt.datetime.now(pytz.utc)
        signals.order_status_changed.send_robust(sender=sender, instance=order,
                                                 old_status=order.old_status,
                                                 new_status=order.status)
        sig = {
            CustomizableItem.SUBMITTED: signals.order_submitted,
            CustomizableItem.ACCEPTED: signals.order_accepted,
            CustomizableItem.IN_PRODUCTION: signals.order_in_production,
            CustomizableItem.FAILED: signals.order_failed,
            CustomizableItem.COMPLETED: signals.order_completed,
            CustomizableItem.DOWNLOADED: signals.order_downloaded,
            CustomizableItem.CANCELLED: signals.order_cancelled,
            CustomizableItem.TERMINATED: signals.order_terminated,
        }[order.status]
        sig.send_robust(sender=sender, instance=order)
        order.old_status = order.status


@receiver(post_init, sender=OrderItem, weak=False,
          dispatch_uid='id_for_get_old_status_order_item')
def get_old_status_order_item(sender, **kwargs):
    order_item = kwargs['instance']
    order_item.old_status = order_item.status


@receiver(pre_save, sender=OrderItem, weak=False,
          dispatch_uid='id_for_update_status_changed_on_order_item')
def update_status_changed_on_by_order_item(sender, **kwargs):
    order_item = kwargs['instance']
    if order_item.status_changed_on is None or \
            order_item.status != order_item.old_status:
        order_item.status_changed_on = dt.datetime.now(pytz.utc)


#@receiver(post_save, sender=OrderItem, weak=False,
#          dispatch_uid='id_for_update_batch')
#def update_batch(sender, **kwargs):
#    order_item = kwargs["instance"]
#    batch = order_item.batch
#    now = dt.datetime.now(pytz.utc)
#    batch.updated_on = now
#    status = batch.status()
#    if status in (OrderStatus.COMPLETED.value, OrderStatus.FAILED.value,
#                  OrderStatus.TERMINATED.value):
#        batch.completed_on = now
#    elif status == OrderStatus.DOWNLOADED.value:
#        pass
#    else:
#        batch.completed_on = None


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
    if order.status_notification == Order.ALL:
        # send and OSEO notification
        print("Order {0} status has changed from {1.value} "
              "to {2.value}".format(order, old, new))
    elif order.status_notification == Order.FINAL:
        if new in (CustomizableItem.CANCELLED, CustomizableItem.COMPLETED,
                   CustomizableItem.FAILED, CustomizableItem.TERMINATED):
            # send an OSEO notification
            print("Order {0} has reached a FINAL status of "
                  "{1.value}".format(order, old))


@receiver(signals.order_submitted, weak=False,
          dispatch_uid='id_for_handle_order_submission')
def handle_order_submission(sender, **kwargs):
    order = kwargs["instance"]
    generic_order_config = utilities.get_generic_order_config(order.order_type)
    automatic_approval = generic_order_config.get("automatic_approval", False)
    if order.status == CustomizableItem.SUBMITTED and not automatic_approval:
        # send email asking admins to moderate the order
        print("Order {} must be moderated by an admin before continuing to "
              "be processed".format(order))
        # where's the code that sends email?


