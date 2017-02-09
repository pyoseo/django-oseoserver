# Copyright 2017 Ricardo Garcia Silva
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

"""Celery tasks for oseoserver.

The celery worker can be started with the command:

.. code:: bash

   pyoseo/pyoseo$ celery worker --app=config --loglevel=info

And the flower monitoring tool can be started with:

.. code:: bash

   pyoseo/pyoseo$ celery flower --app=config

"""

# TODO
# * Instead of calling oseoserver.models directly, develop a RESTful API
#   and communicate with the database over HTTP. This allows the task to
#   run somewhere else, instead of having it in the same machine

from __future__ import division
from __future__ import absolute_import
from datetime import datetime, timedelta

from celery import shared_task
from celery import group, chain
from celery.utils.log import get_task_logger
from django.contrib.sites.models import Site
import pytz

from . import models
from . import utilities
from .models import CustomizableItem
from .models import SelectedDeliveryOption

logger = get_task_logger(__name__)

# TODO - Find another way to send error e-mails now that celery dropped it from tasks

#@shared_task(bind=True)
#def process_product_order(self, order_id):
#    """Process a product order.
#
#    Parameters
#    ----------
#
#    order_id: int
#        The primary key of the order in django's database. This is used to
#        retrieve order information at the time of processing.
#
#    """
#
#    order = models.ProductOrder.objects.get(pk=order_id)
#    order.status = CustomizableItem.IN_PRODUCTION
#    order.additional_status_info = "Order is being processed"
#    order.save()
#    batch = order.batches.get() # normal product orders have only one batch
#    process_product_order_batch.apply_async((batch.id,))


@shared_task(bind=True)
def process_subscription_order_batch(self, batch_id, notify_user=True):
    """Process a subscription order batch."""

    celery_group = _process_batch(batch_id)
    if notify_user:
        c = chain(
            celery_group,
            notify_user_subscription_batch_available.subtask((batch_id,),
                                                             immutable=True)
        )
        c.apply_async()
    else:
        celery_group.apply_async()


@shared_task(bind=True)
def process_product_order_batch(self, batch_id, notify_user=False):
    """Process a normal product order batch.

    Parameters
    ----------
    batch_id: int
        Django database identifier of the batch so that it can be retrieved
        at processing time
    notify_user: bool
        Whether the user that placed the order should be notified

    """

    batch = models.Batch.objects.get(pk=batch_id)
    logger.debug("batch: {0}".format(batch.id))
    order_item_tasks = create_product_batch_group(batch)
    batch_chain = chain(
        order_item_tasks,
        update_product_order_status.subtask((batch.order.id,), immutable=True)
    )
    if notify_user:
        job = chain(batch_chain,
                    notify_user_product_batch_available.subtask((batch_id,)))
        job.apply_async()
    else:
        batch_chain.apply_async()


@shared_task(bind=True)
def notify_user_subscription_batch_available(self, batch_id):
    batch = models.SubscriptionBatch.objects.get(pk=batch_id)
    utilities.send_subscription_batch_available_email(batch)


@shared_task(bind=True)
def notify_user_product_batch_available(self, batch_id):
    batch = models.Batch.objects.get(pk=batch_id)
    utilities.send_product_batch_available_email(batch)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=20,
)
def process_online_data_access_item(self, order_item_id, max_tries=3,
                                    sleep_interval=10):
    """Process order items that specify online data access as delivery.

    Parameters
    ----------
    order_item_id: int
        The primary key value of the order item in the database
    max_tries: int, optional
        How many times should the processing be retried, in case it fails
    sleep_interval: int, optional
        How many seconds should the worker sleep before retrying the
        processing

    """

    order_item = models.OrderItem.objects.get(pk=order_item_id)
    try:
        order_item.process()
    except Exception as err:
        self.retry(exc=err)


@shared_task(bind=True)
def process_online_data_delivery_item(self, order_item_id):
    """
    Process an order item that specifies online data delivery
    """

    raise NotImplementedError


@shared_task(bind=True)
def process_media_delivery_item(self, order_item_id):
    """
    Process an order item that specifies media delivery
    """

    raise NotImplementedError


@shared_task(bind=True)
def update_product_order_status(self, order_id):
    """
    Update the status of a normal order whenever the status of its batch
    changes

    :arg order_id:
    :type order_id: oseoserver.models.Order
    """

    order = models.ProductOrder.objects.get(pk=order_id)
    old_order_status = order.status
    batch = order.batches.get()  # ProductOrder's have only one batch
    if batch.status == CustomizableItem.COMPLETED and order.packaging != '':
        try:
            _package_batch(batch, order.packaging)
        except Exception as e:
            order.status = CustomizableItem.FAILED
            order.additional_status_info = str(e)
            order.save()
            raise
    new_order_status = batch.status
    if (old_order_status != new_order_status or
                old_order_status == CustomizableItem.FAILED):
        order.status = new_order_status
        if new_order_status == CustomizableItem.COMPLETED:
            order.completed_on = datetime.now(pytz.utc)
            order.additional_status_info = ""
        elif new_order_status == CustomizableItem.FAILED:
            details = []
            for oi in batch.order_items.all():
                if oi.status == CustomizableItem.FAILED:
                    additional = oi.additional_status_info
                    details.append((oi.id, additional))
            msg = "\n".join(["* Order item {}: {}".format(oi, det) for
                             oi, det in details])
            order.additional_status_info = msg
        order.save()


@shared_task(bind=True)
def delete_expired_order_items(self):
    """Delete all order items that are expired from the filesystem

    This task should be run preiodically in a celery beat worker.

    """

    now = datetime.now(pytz.utc)
    for item in models.OrderItem.objects.filter(available=True,
                                                expires_on__lt=now):
        delete_order_item_file.apply_async((item.id,))


@shared_task(bind=True)
def delete_order_item_file(self, order_item_id):
    """Delete a single order_item from the filesystem

    This task calls the `clean_files()` method of the orderitem's order
    processor object. It also takes care of setting the item's `available`
    attribute to False.

    """

    order_item = models.OrderItem.objects.get(id=order_item_id)
    processor = utilities.get_item_processor(order_item)
    try:
        processor.clean_files(order_item.url)
    except Exception as e:
        logger.error("There has been an error deleting "
                     "{}: {}".format(order_item, e))
    finally:
        if order_item.available:
            order_item.available = False
            order_item.save()


@shared_task(bind=True)
def terminate_expired_subscriptions(self):
    """Terminate subscriptions that are expired

    This task should be run in a celery beat worker with a daily frequency.
    """

    now = datetime.now(pytz.utc)
    to_terminate = models.SubscriptionOrder.objects.filter(
        status=models.CustomizableItem.ACCEPTED,
        end_on__lt=now.strftime("%Y-%m-%d")
    )
    for subscription_order in to_terminate:
        subscription_order.status = models.CustomizableItem.TERMINATED
        subscription_order.save()


# TODO - Activate this task
# This is conditional on the existance of a new field in Batches that
# specifies how many times should a failed batch be retried. There must
# be a new celery-beat process that is in charge of running this task
# periodically
#@shared_task(bind=True)
#def retry_failed_batches(self):
#    """Try to process a failed batch again"""
#
#    g = []
#    for failed_batch in models.Batch.objects.filter(
#            status=models.CustomizableItem.FAILED):
#        if failed_batch.processing_attempts < models.Batch.MAX_ATTEMPTS:
#            if hasattr(failed_batch, "subscriptionbatch"):
#                update_order_status = False
#                notify_batch_execution = True
#            else:
#                update_order_status = True
#                notify_batch_execution = False
#            g.append(
#                old_process_batch.subtask(
#                    (failed_batch.id,),
#                    {
#                        "update_order_status": update_order_status,
#                        "notify_batch_execution": notify_batch_execution
#                    }
#                )
#            )
#    job = group(g)
#    job.apply_async()


def create_product_batch_group(batch):
    group_tasks = []
    for order_item in batch.order_items.all():
        delivery_option = (order_item.selected_delivery_option or
                           batch.order.selected_delivery_option)
        task_function = {
            SelectedDeliveryOption.ONLINE_DATA_ACCESS:
                process_online_data_access_item,
            SelectedDeliveryOption.ONLINE_DATA_DELIVERY:
                process_online_data_delivery_item,
            SelectedDeliveryOption.MEDIA_DELIVERY: process_media_delivery_item,
        }[delivery_option.delivery_type]
        order_item_task_signature = task_function.subtask((order_item.id,))
        group_tasks.append(order_item_task_signature)
    return group(*group_tasks)



def _process_batch(batch_id):
    """Generate a celery group with subtasks for every order item in the batch.
    """

    print("batch_id: {}".format(batch_id))
    try:
        batch = models.Batch.objects.get(pk=batch_id)
    except models.Batch.DoesNotExist:
        logger.error('Could not find batch {}'.format(batch_id))
        raise
    g = []
    order = batch.order
    for order_item in batch.order_items.all():
        try:
            selected = order_item.selected_delivery_option
        except models.SelectedDeliveryOption.DoesNotExist:
            selected = order.selected_delivery_option
        task_func = {
            SelectedDeliveryOption.ONLINE_DATA_ACCESS:
                process_online_data_access_item,
            SelectedDeliveryOption.ONLINE_DATA_DELIVERY:
                process_online_data_delivery_item,
            SelectedDeliveryOption.MEDIA_DELIVERY: process_media_delivery_item,
        }[selected.delivery_type]
        sig = task_func.subtask((order_item.id,))
        g.append(sig)
    return group(g)


def _package_batch(batch, compression):
    """Package all order items of a batch into a single archive"""
    item_processor = utilities.get_item_processor(batch.order)
    files_to_package = []
    try:
        for item in batch.order_items.all():
            for oseo_file in item.files.all():
                files_to_package.append(oseo_file.url)
        packed = item_processor.package_files(
            packaging=compression,
            domain=Site.objects.get_current().domain,
            site_name="phony_site_name",
            file_urls=files_to_package,
        )
    except Exception as e:
        logger.error("there has been an error packaging the "
                     "batch {}: {}".format(batch, str(e)))
        utilities.send_batch_packaging_failed_email(batch, str(e))
        raise
    expiry_date = datetime.now(pytz.utc) + timedelta(
        days=order_type.item_availability_days)
    for item in batch.order_items.all():
        item.files.all().delete()
        f = models.OseoFile(url=packed, available=True, order_item=item,
                            expires_on=expiry_date)
        f.save()


@shared_task(bind=True)
def test_task(self):
    print('printing something from within a task')
    logger.debug('logging something from within a task with level: debug')
    logger.info('logging something from within a task with level: info')
    logger.warning('logging something from within a task with level: warning')
    logger.error('logging something from within a task with level: error')

