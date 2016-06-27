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

"""
Celery tasks for pyoseo

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
import pytz

from . import models
from . import utilities
from . import settings
from .constants import OrderStatus
from .constants import DeliveryOption

logger = get_task_logger(__name__)


@shared_task(bind=True)
def process_product_order(self, order_id):
    """Process a product order.

    Parameters
    ----------

    order_id: int
        The primary key of the order in django's database. This is used to
        retrieve order information at the time of processing.

    """

    try:
        order = models.ProductOrder.objects.get(pk=order_id)
        order.status = OrderStatus.IN_PRODUCTION.value
        order.additional_status_info = "Order is being processed"
        order.save()
    except models.ProductOrder.DoesNotExist:
        logger.error('Could not find order {}'.format(order_id))
        raise
    batch = order.batches.get() # normal product orders have only one batch
    process_product_order_batch.apply_async((batch.id,))


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

    celery_group = _process_batch(batch_id)
    batch = models.Batch.objects.get(pk=batch_id)
    c = chain(
        celery_group,
        update_product_order_status.subtask((batch.order.id,), immutable=True)
    )
    if notify_user:
        job = chain(c,
                    notify_user_product_batch_available.subtask((batch_id,)))
        job.apply_async()
    else:
        c.apply_async()


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
    if batch.status() == OrderStatus.COMPLETED.value and order.packaging != '':
        try:
            _package_batch(batch, order.packaging)
        except Exception as e:
            order.status = OrderStatus.FAILED.value
            order.additional_status_info = str(e)
            order.save()
            raise
    new_order_status = batch.status()
    if (old_order_status != new_order_status or
                old_order_status == OrderStatus.FAILED.value):
        order.status = new_order_status
        if new_order_status == OrderStatus.COMPLETED.value:
            order.completed_on = datetime.now(pytz.utc)
            order.additional_status_info = ""
        elif new_order_status == OrderStatus.FAILED.value:
            details = []
            for oi in batch.order_items.all():
                if oi.status == OrderStatus.FAILED.value:
                    additional = oi.additional_status_info
                    details.append((oi.id, additional))
            msg = "\n".join(["* Order item {}: {}".format(oi, det) for
                             oi, det in details])
            order.additional_status_info = msg
        order.save()


@shared_task(bind=True)
def delete_expired_oseo_files(self):
    """Delete all oseo files that are expired from the filesystem"""

    qs = models.OseoFile.objects.filter(available=True,
                                        expires_on__lt=datetime.now(pytz.utc))
    for oseo_file in qs:
        delete_oseo_file.apply_async((oseo_file.id,))


@shared_task(bind=True)
def delete_oseo_file(self, oseo_file_id):
    """Delete an oseofile from the filesystem"""

    oseo_file = models.OseoFile.objects.get(id=oseo_file_id)
    processor, params = utilities.get_processor(
        oseo_file.order_item.batch.order.order_type,
        models.ItemProcessor.PROCESSING_CLEAN_ITEM,
        logger_type="pyoseo"
    )
    try:
        processor.clean_files(oseo_file.url)
    except Exception as e:
        logger.error("There has been an error deleting "
                     "{}: {}".format(oseo_file, e))
    finally:
        if oseo_file.available:
            oseo_file.available = False
            oseo_file.save()


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
            DeliveryOption.ONLINE_DATA_ACCESS.value:
                process_online_data_access_item,
            DeliveryOption.ONLINE_DATA_DELIVERY.value:
                process_online_data_delivery_item,
            DeliveryOption.MEDIA_DELIVERY.value: process_media_delivery_item,
        }[selected.delivery_type]
        sig = task_func.subtask((order_item.id,))
        g.append(sig)
    return group(g)


def _package_batch(batch, compression):
    item_processor = utilities.get_item_processor(batch.order)
    files_to_package = []
    try:
        for item in batch.order_items.all():
            for oseo_file in item.files.all():
                files_to_package.append(oseo_file.url)
        packed = item_processor.package_files(
            packaging=compression,
            domain=settings.get_site_domain(),
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

