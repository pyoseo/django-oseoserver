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

   pyoseo/pyoseo$ celery worker --app=pyoseo.celery_app --loglevel=info
"""

# TODO
# * Instead of calling oseoserver.models directly, develop a RESTful API
#   and communicate with the database over HTTP. This allows the task to
#   run somewhere else, instead of having it in the same machine

from __future__ import division
import time
import datetime as dt
from datetime import datetime, timedelta
import sys
import traceback

import pytz
from django.conf import settings as django_settings
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.db.models import Q
from celery import shared_task
from celery import group, chord, chain
from celery.utils.log import get_task_logger
from actstream import action

from oseoserver import models
from oseoserver import utilities

logger = get_task_logger(__name__)


@shared_task(bind=True)
def process_product_order(self, order_id):
    """
    Process a product order.

    :arg order_id:
    :type order_id: int
    """

    try:
        order = models.ProductOrder.objects.get(pk=order_id)
        order.status = models.CustomizableItem.IN_PRODUCTION
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
    """Process a normal product order batch."""

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


@shared_task(bind=True)
def process_online_data_access_item(self, order_item_id, max_tries=6,
                                    sleep_interval=30):
    """
    Process an order item that specifies online data access as delivery.

    :arg order_item_id: The id of the order item that is to be processed. It
        corresponds to the primary key of the object in the database.
    :type order_item_id: int
    :arg max_tries: How many times should the processing of the item be
        attempted if it fails?
    :type max_tries: int
    :arg sleep_interval: How long (in seconds) should the server wait before
        attempting another execution?
    :type sleep_interval: int

    This task calls the user defined ItemProcessor to do the actual processing
    of order items.
    """

    order_item = models.OrderItem.objects.get(pk=order_item_id)
    order_item.status = models.CustomizableItem.IN_PRODUCTION
    order_item.additional_status_info = "Item is being processed"
    order_item.save()
    order = order_item.batch.order
    current_try = 0
    item_processed = False
    error_details = ""
    while current_try < max_tries and not item_processed:
        try:
            processor, params = utilities.get_processor(
                order.order_type,
                models.ItemProcessor.PROCESSING_PROCESS_ITEM,
            )
            options = order_item.export_options()
            delivery_options = order_item.export_delivery_options()
            urls, details = processor.process_item_online_access(
                order_item.identifier, order_item.item_id, order.id,
                order.user.user.username, options, delivery_options,
                domain=Site.objects.get_current().domain,
                sub_uri=django_settings.SITE_SUB_URI,
                **params)
            order_item.additional_status_info = details
            if any(urls):
                now = datetime.now(pytz.utc)
                expiry_date = now + timedelta(
                    days=order.order_type.item_availability_days)
                order_item.status = models.CustomizableItem.COMPLETED
                order_item.completed_on = now
                for url in urls:
                    f = models.OseoFile(url=url, available=True,
                                        order_item=order_item,
                                        expires_on=expiry_date)
                    f.save()
                item_processed = True
            else:
                order_item.status = models.CustomizableItem.FAILED
                logger.error('THERE HAS BEEN AN ERROR: order item {} has '
                             'failed'.format(order_item_id))
        except Exception as e:
            formatted_tb = traceback.format_exception(*sys.exc_info())
            error_message = "Attempt ({}/{}). Error: {}.".format(
                current_try+1, max_tries, formatted_tb)
            order_item.status = models.CustomizableItem.FAILED
            order_item.additional_status_info = error_message
            error_details += error_message
            logger.error("THERE HAS BEEN AN ERROR: order item {} has "
                         "failed with the error: {}".format(order_item_id,
                                                            formatted_tb))
        current_try += 1
        if not item_processed:
            logger.critical("Could not process the item ("
                            "Attempt {}/{})".format(current_try, max_tries))
            _send_failed_attempt_email(order, order_item, error_details)
            if current_try < max_tries:
                logger.critical("Trying again in {} "
                                "minutes...".format(sleep_interval/60))
                time.sleep(sleep_interval)
    order_item.save()


def _send_failed_attempt_email(order, order_item, message):
    full_message = "Order: {}\n\tOrderItem: {}\n\n\t".format(
        order.id, order_item.id)
    full_message += message
    subject = ("Copernicus Global Land Service - Unsuccessful processing "
               "attempt")
    recipients = User.objects.filter(is_staff=True).exclude(email="")
    utilities.send_email(subject, full_message, recipients, html=True)


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
    if batch.status() == models.CustomizableItem.COMPLETED and \
                    order.packaging != '':
        try:
            _package_batch(batch, order.packaging)
        except Exception as e:
            order.status = models.CustomizableItem.FAILED
            order.additional_status_info = str(e)
            order.save()
            raise
    new_order_status = batch.status()
    if old_order_status != new_order_status or \
                    old_order_status == models.CustomizableItem.FAILED:
        order.status = new_order_status
        if new_order_status == models.CustomizableItem.COMPLETED:
            order.completed_on = dt.datetime.now(pytz.utc)
            order.additional_status_info = ""
        elif new_order_status == models.CustomizableItem.FAILED:
            details = []
            for oi in batch.order_items.all():
                if oi.status == models.CustomizableItem.FAILED:
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
    """
    Generate a celery group with subtasks for every order item in the batch.
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
        if hasattr(selected.option, 'onlinedataaccess'):
            sig = process_online_data_access_item.subtask((order_item.id,))
        elif hasattr(selected.option, 'onlinedatadelivery'):
            sig = process_online_data_delivery_item.subtask((order_item.id,))
        elif hasattr(selected.option, 'mediadelivery'):
            sig = process_media_delivery_item.subtask((order_item.id,))
        else:
            raise
        g.append(sig)
    return group(g)


def _package_batch(batch, compression):
    order_type = batch.order.order_type
    processor, params = utilities.get_processor(
        order_type,
        models.ItemProcessor.PROCESSING_PROCESS_ITEM,
        logger_type="pyoseo"
    )
    domain = Site.objects.get_current().domain
    files_to_package = []
    try:
        for item in batch.order_items.all():
            for oseo_file in item.files.all():
                files_to_package.append(oseo_file.url)
        packed = processor.package_files(compression, domain,
                                         file_urls=files_to_package,
                                         **params)
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
