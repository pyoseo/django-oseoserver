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

from celery import shared_task
from celery import group, chain
from celery.utils.log import get_task_logger
import pytz

from . import mailsender
from . import models
from . import utilities

logger = get_task_logger(__name__)

# TODO - Find another way to send error e-mails now that celery dropped it from tasks


@shared_task(bind=True)
def clean_expired_items(self):
    """Clean order items that are expired.

    This task should be run periodically in a celery beat worker.

    """

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


@shared_task(bind=True)
def process_batch(self, batch_id):
    """Process a batch in the queue."""
    batch = models.Batch.objects.get(id=batch_id)
    batch_group = group(
        process_item.signature((i.id,)) for i in batch.order_items.all())
    config = utilities.get_generic_order_config(batch.order.order_type)
    notify_batch_available = config["notifications"]["batch_availability"]
    if notify_batch_available.lower() == "immediate":
        batch_chain = chain(
            batch_group,
            notify_user_batch_available.signature((batch_id,))
        )
        logger.info("batch_chain: {}".format(batch_chain))
        batch_chain()
    else:
        batch_group.apply_async()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=20,
)
def process_item(self, order_item_id, max_tries=3, sleep_interval=10):
    """Process an order item in the queue.

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
        path = order_item.process()
        url = order_item.deliver(path=path)
    except Exception as err:
        logger.warning(err)
        item_processor = utilities.get_item_processor(order_item)
        item_processor.cleanup()
        self.retry(exc=err)


@shared_task(bind=True)
def terminate_expired_subscriptions(self):
    """Terminate subscriptions that are expired

    This task should be run in a celery beat worker with a daily frequency.
    """

    now = dt.datetime.now(pytz.utc)
    to_terminate = models.Order.objects.filter(
        order_type=models.Order.SUBSCRIPTION_ORDER,
        status=models.CustomizableItem.SUSPENDED,
        end_on__lt=now.strftime("%Y-%m-%d")
    )
    for subscription_order in to_terminate:
        subscription_order.status = models.CustomizableItem.TERMINATED
        subscription_order.completed_on = now
        subscription_order.save()


@shared_task(bind=True)
def test_task(self):
    print('printing something from within a task')
    logger.debug('logging something from within a task with level: debug')
    logger.info('logging something from within a task with level: info')
    logger.warning('logging something from within a task with level: warning')
    logger.error('logging something from within a task with level: error')
