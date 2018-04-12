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

from __future__ import division
from __future__ import absolute_import
import datetime as dt

from celery import chain
from celery import chord
from celery import group
from celery import shared_task
from celery import Task
from celery.result import allow_join_result
from celery.utils.log import get_task_logger
import pytz

from . import mailsender
from . import models
from . import utilities

logger = get_task_logger(__name__)


@shared_task(bind=True)
def clean_expired_items(self):
    """Clean order items that are expired.

    This task should be run periodically in a celery beat worker.

    """

    logger.debug("Cleaning expired items...")
    expired_qs = models.OrderItem.objects.filter(
        available=True, expires_on__lt=dt.datetime.now(pytz.utc))
    deletion_group = group(
        expire_item.signature((item.id,)) for item in expired_qs)
    deletion_group.apply_async()


@shared_task(bind=True)
def expire_item(self, item_id):
    """Clean a single order_item."""

    order_item = models.OrderItem.objects.get(id=item_id)
    order_item.expire()


@shared_task(bind=True)
def notify_user_batch_available(self, batch_id):
    batch = models.Batch.objects.get(pk=batch_id)
    mailsender.send_product_batch_available_email(batch)


def prepare_items_by_processing_type(order_items):
    sequential_items = []
    parallel_items = []
    for item in order_items:
        processing_type = utilities.get_item_processing_type(
            collection=item.item_specification.collection,
            item_identifier=item.identifier,
            item_options=item.export_options()
        )
        if processing_type == "sequential":
            sequential_items.append({
                "id": item.id,
                "identifier": item.identifier,
                "options": item.export_options(),
            })
        else:
            parallel_items.append({
                "id": item.id,
                "identifier": item.identifier,
                "options": item.export_options()
            })
    return sequential_items, parallel_items


@shared_task(bind=True)
def process_batch(self, batch_id):
    """Process a batch in the queue.

    Order items may be processed in parallel or in sequence, depending on the
    value of the ``item_processing`` setting of their respective collection.

    Parameters
    ----------
    batch_id: int
        Primary key of the batch in the database.

    """

    batch = models.Batch.objects.get(id=batch_id)
    sequential_items, parallel_items = prepare_items_by_processing_type(
        batch.order_items.all())
    logger.debug("sequential_item: {}".format(sequential_items))
    logger.debug("parallel_items: {}".format(parallel_items))
    batch_data = {}
    for processor in batch.get_item_processors():
        batch_processor_data = processor.prepare_batch(
            sequential_items, parallel_items, batch.order.user.username)
        batch_data[processor.__class__.__name__] = batch_processor_data
    tasks = []
    for item_info in parallel_items:
        sig = process_item.signature(
            (item_info["id"],),
            {"batch_data": batch_data}
        )
        tasks.append(sig)
    if len(sequential_items) > 0:
        tasks += [
            process_items_sequentially.signature(
                ([i["id"] for i in sequential_items],),
                {"batch_data": batch_data}
            )
        ]
    logger.debug("tasks: {}".format(tasks))
    config = utilities.get_generic_order_config(batch.order.order_type)
    notify_batch_available = config.get(
        "notifications", {}).get("batch_availability", "")
    notification = notify_batch_available.lower()
    callback = notify_user_batch_available.signature(
        (batch_id,), immutable=True)
    if len(tasks) == 1:
        if notification == "immediate":
            chain(tasks[0], callback).apply_async()
        else:
            tasks[0].apply_async()
    elif len(tasks) > 1:
        batch_group = group(*tasks)
        if notification == "immediate":
            chord(batch_group, header=callback).apply_async()
        else:
            batch_group.apply_async()


class ProcessItemTaskSequential(Task):
    """A custom task that implements custom handlers.

    This class is the base for the ``process_items_sequentially()`` task.
    This task is responsible for processing ordered items. The on_failure
    and on_success methods are reimplemented here in order to update each
    order item's status in the database after the task is done.

    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        for item_id in args[0]:
            order_item = models.OrderItem.objects.get(pk=item_id)
            order_item.set_status(
                order_item.FAILED,
                exc.args
            )
            mailsender.send_item_processing_failed_email(
                order_item, task_id, exc, args, einfo.traceback)

    def on_success(self, retval, task_id, args, kwargs):
        for item_id in args[0]:
            order_item = models.OrderItem.objects.get(pk=item_id)
            order_item.set_status(order_item.COMPLETED)


@shared_task(
    bind=True,
    base=ProcessItemTaskSequential,
)
def process_items_sequentially(self, item_ids, batch_data=None):
    """Process a series of order items sequentially, one after the other"""
    for item_id in item_ids:
        process_item(item_id, batch_data=batch_data)


class ProcessItemTask(Task):
    """A custom task that implements custom handlers.

    This class is the base for the ``process_item()`` task. This task is
    responsible for processing ordered items. The on_failure and on_success
    methods are reimplemented here in order to update an order item's status
    in the database after the task is done.

    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        order_item = models.OrderItem.objects.get(pk=args[0])
        order_item.set_status(
            order_item.FAILED,
            exc.args
        )
        mailsender.send_item_processing_failed_email(order_item, task_id, exc,
                                                     args, einfo.traceback)

    def on_success(self, retval, task_id, args, kwargs):
        logger.debug("on_success called with: {}".format(locals()))
        order_item = models.OrderItem.objects.get(pk=args[0])
        order_item.set_status(order_item.COMPLETED)


@shared_task(
    bind=True,
    base=ProcessItemTask,
    autoretry_for=(Exception,),
    default_retry_delay=30,  # seconds
    max_retries=3,
)
def process_item(self, order_item_id, batch_data=None):
    """Process an order item

    Processing is composed by two steps:

    * Preparing the item according to any customization options that might
      have been requested;
    * Delivering the prepared item using the delivery method requested

    This task inherits the ProcessItemTask so that it may be possible to
    update the order item's status in case of failure

    """

    order_item = models.OrderItem.objects.get(pk=order_item_id)
    order_item.set_status(
        order_item.IN_PRODUCTION,
        "Item is being processed (Try number {})".format(self.request.retries)
    )
    prepared_url = order_item.prepare(batch_data=batch_data)
    delivered_url = order_item.deliver(prepared_url)
    return delivered_url


# TODO - Test this code
@shared_task(bind=True)
def terminate_expired_subscriptions(self, notify_user=False):
    """Terminate subscriptions that are expired

    This task should be run in a celery beat worker with a daily frequency.
    """

    now = dt.datetime.now(pytz.utc)
    queryset = models.Order.objects.filter(
        order_type=models.Order.SUBSCRIPTION_ORDER
    ).exclude(status__in=[
        models.Order.CANCELLED,
        models.Order.SUBMITTED,
        models.Order.TERMINATED,
    ])
    for subscription in queryset:
        for item_spec in subscription.item_specifications.all():
            date_range = item_spec.get_option("DateRange")
            start, stop = utilities.convert_date_range_option(date_range.value)
            if stop < now:
                logger.info("Terminating subscription {}".format(subscription))
                subscription.status = models.Order.TERMINATED
                subscription.status_changed_on = now
                subscription.completed_on = now
                subscription.save()
                if notify_user:
                    pass


@shared_task(bind=True)
def test_task(self):
    print('printing something from within a task')
    logger.debug('logging something from within a task with level: debug')
    logger.info('logging something from within a task with level: info')
    logger.warning('logging something from within a task with level: warning')
    logger.error('logging something from within a task with level: error')


