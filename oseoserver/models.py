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

"""Database models for oseoserver."""

from __future__ import absolute_import
import datetime as dt
import sys
import traceback
import logging

from django.db import models
from django.conf import settings as django_settings
from django.utils.encoding import python_2_unicode_compatible
import pytz

from . import utilities

logger = logging.getLogger(__name__)


class AbstractDeliveryAddress(models.Model):
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    company_ref = models.CharField(max_length=50, blank=True)
    street_address = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)
    post_box = models.CharField(max_length=50, blank=True)
    telephone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)

    class Meta:
        abstract = True


@python_2_unicode_compatible
class CustomizableItem(models.Model):
    SUBMITTED = "Submitted"
    ACCEPTED = "Accepted"
    IN_PRODUCTION = "InProduction"
    SUSPENDED = "Suspended"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"
    FAILED = "Failed"
    TERMINATED = "Terminated"
    DOWNLOADED = "Downloaded"
    STATUS_CHOICES = [
        (SUBMITTED, SUBMITTED),
        (ACCEPTED, ACCEPTED),
        (IN_PRODUCTION, IN_PRODUCTION),
        (SUSPENDED, SUSPENDED),
        (CANCELLED, CANCELLED),
        (COMPLETED, COMPLETED),
        (FAILED, FAILED),
        (TERMINATED, TERMINATED),
        (DOWNLOADED, DOWNLOADED),
    ]

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=SUBMITTED,
    )
    additional_status_info = models.TextField(
        help_text="Additional information about the status",
        blank=True
    )
    mission_specific_status_info = models.TextField(
        help_text="Additional information about the status that is specific "
                  "to the mission",
        blank=True
    )
    created_on = models.DateTimeField(
        auto_now_add=True
    )
    completed_on = models.DateTimeField(
        null=True,
        blank=True
    )
    status_changed_on = models.DateTimeField(
        editable=False,
        blank=True,
        null=True
    )
    remark = models.TextField(
        help_text="Some specific remark about the item",
        blank=True
    )

    class Meta:
        abstract = True

@python_2_unicode_compatible
class Extension(models.Model):

    text = models.CharField(
        max_length=255, blank=True,
        help_text="Custom extensions to the OSEO standard"
    )

    def __str__(self):
        return self.text


@python_2_unicode_compatible
class DeliveryInformation(AbstractDeliveryAddress):
    order = models.OneToOneField(
        "Order",
        null=True,
        blank=True,
        related_name="delivery_information"
    )


@python_2_unicode_compatible
class InvoiceAddress(AbstractDeliveryAddress):
    order = models.OneToOneField(
        "Order",
        blank=True,
        null=True,
        related_name="invoice_address"
    )

    class Meta:
        verbose_name_plural = "invoice addresses"


@python_2_unicode_compatible
class OnlineAddress(models.Model):
    FTP = 'ftp'
    SFTP = 'sftp'
    FTPS = 'ftps'
    PROTOCOL_CHOICES = (
        (FTP, FTP),
        (SFTP, SFTP),
        (FTPS, FTPS),
    )
    delivery_information = models.ForeignKey(
        'DeliveryInformation', related_name="online_addresses")
    protocol = models.CharField(max_length=20, default=FTP,
                                choices=PROTOCOL_CHOICES)
    server_address = models.CharField(max_length=255)
    user_name = models.CharField(max_length=50, blank=True)
    user_password = models.CharField(max_length=50, blank=True)
    path = models.CharField(max_length=1024, blank=True)

    class Meta:
        verbose_name_plural = 'online addresses'

    def __str__(self):
        return "{} {}".format(self.protocol, self.server_address)


@python_2_unicode_compatible
class Order(CustomizableItem):
    MASSIVE_ORDER_REFERENCE = "Massive order"
    PRODUCT_ORDER = "PRODUCT_ORDER"
    SUBSCRIPTION_ORDER = "SUBSCRIPTION_ORDER"
    MASSIVE_ORDER = "MASSIVE_ORDER"
    TASKING_ORDER = "TASKING_ORDER"
    ORDER_TYPE_CHOICES = [
        (PRODUCT_ORDER, PRODUCT_ORDER),
        (SUBSCRIPTION_ORDER, SUBSCRIPTION_ORDER),
        (MASSIVE_ORDER, MASSIVE_ORDER),
        (TASKING_ORDER, TASKING_ORDER),
    ]
    ZIP = "zip"
    PACKAGING_CHOICES = [
        (ZIP, ZIP),
    ]
    NONE = "None"
    FINAL = "Final"
    ALL = "All"
    STATUS_NOTIFICATION_CHOICES = [
        (NONE, NONE),
        (FINAL, FINAL),
        (ALL, ALL),
    ]
    STANDARD = "STANDARD"
    FAST_TRACK = "FAST_TRACK"
    PRIORITY_CHOICES = [
        (STANDARD, STANDARD),
        (FAST_TRACK, FAST_TRACK),
    ]

    extensions = models.ForeignKey(
        "Extension",
        related_name="order",
        blank=True,
        null=True
    )
    user = models.ForeignKey(django_settings.AUTH_USER_MODEL,
                             related_name="%(app_label)s_%(class)s_orders")
    order_type = models.CharField(
        max_length=30,
        default=PRODUCT_ORDER,
        choices=ORDER_TYPE_CHOICES
    )

    last_describe_result_access_request = models.DateTimeField(null=True,
                                                               blank=True)
    reference = models.CharField(max_length=30,
                                 help_text="Some specific reference about "
                                           "this order",
                                 blank=True)
    packaging = models.CharField(max_length=30,
                                 choices=PACKAGING_CHOICES,
                                 blank=True)
    priority = models.CharField(
        max_length=30,
        choices=PRIORITY_CHOICES,
        default=STANDARD,
        blank=True,
    )
    status_notification = models.CharField(
        max_length=10,
        default=NONE,
        choices=STATUS_NOTIFICATION_CHOICES
    )

    def __str__(self):
        return '{0.order_type}, {0.id}, {0.reference!r}'.format(self)

    def export_delivery_information(self):
        """Return a dictionary with the instance's delivery information.

        This method's result is passed to custom order processor objects when
        a request is delivered.

        """

        result = {"online_addresses": []}
        for online_address in self.delivery_information.online_addresses.all():
            result["online_addresses"].append({
                "protocol": online_address.protocol,
                "server_address": online_address.server_address,
                "user_name": online_address.user_name,
                "user_password": online_address.user_password,
                "path": online_address.path,
            })
        return result


@python_2_unicode_compatible
class OrderPendingModerationManager(models.Manager):

    def get_queryset(self):
        return super(OrderPendingModerationManager,
                     self).get_queryset().filter(
            status=Order.SUBMITTED)


@python_2_unicode_compatible
class OrderPendingModeration(Order):
    objects = OrderPendingModerationManager()

    class Meta:
        proxy = True
        verbose_name_plural = "orders pending moderation"


class ItemSpecification(models.Model):
    """Specification from which actual order items are generated at runtime."""
    order = models.ForeignKey(
        "Order",
        related_name="item_specifications",
        null=True,
        blank=True,
    )
    remark = models.TextField(
        help_text="Some specific remark about the item",
        blank=True
    )
    extension = models.ForeignKey(
        "Extension",
        related_name="item_specifications",
        null=True,
        blank=True
    )
    collection = models.CharField(
        max_length=255,
    )
    identifier = models.CharField(
        max_length=255,
        blank=True,
        help_text="identifier for the order item. It is the product Id in "
                  "the catalogue."
    )
    item_id = models.CharField(
        max_length=80,
        help_text="Id for the item in the order request"
    )

    def __str__(self):
        return "{0.id}".format(self)


@python_2_unicode_compatible
class OrderItem(CustomizableItem):
    identifier = models.CharField(
        max_length=255,
        blank=True,
        help_text="identifier for this order item. It is the product Id in "
                  "the catalog"
    )
    url = models.CharField(
        max_length=255,
        help_text="URL where this item is available",
        blank=True
    )
    item_specification = models.ForeignKey(
        "ItemSpecification",
        related_name="order_items",
        null=True
    )
    batch = models.ForeignKey(
        "Batch",
        null=True,
        blank=True,
        related_name="order_items",
    )
    expires_on = models.DateTimeField(
        null=True,
        blank=True
    )
    last_downloaded_at = models.DateTimeField(
        null=True,
        blank=True
    )
    available = models.BooleanField(default=False)
    downloads = models.SmallIntegerField(
        default=0,
        help_text="Number of times this order item has been downloaded."
    )

    def __str__(self):
        return ("id: {0.id}, batch: {0.batch}".format(self))

    def export_delivery_options(self):
        """Return a dictionary with the instance's delivery options.

        This method's result is passed to custom order processor objects when
        a request is actually processed. Order prcoessors receive a simplified
        version of the delivery options.

        """

        try:
            delivery_options = self.item_specification.selected_delivery_option
        except ItemSpecificationDeliveryOption.DoesNotExist:
            delivery_options = self.batch.order.selected_delivery_option
        result = {
            "copies": delivery_options.copies,
            "annotation": delivery_options.annotation,
            "special_instructions": delivery_options.special_instructions,
            "delivery_type": delivery_options.delivery_type,
        }
        delivery_type = delivery_options.delivery_type
        if delivery_type == BaseDeliveryOption.ONLINE_DATA_ACCESS:
            result["protocol"] = delivery_options.delivery_details
        elif delivery_type == BaseDeliveryOption.ONLINE_DATA_DELIVERY:
            pass
        elif delivery_type == BaseDeliveryOption.MEDIA_DELIVERY:
            result["medium"] = delivery_options.delivery_details
        return result

    def export_options(self):
        valid_options = dict()
        for order_option in self.batch.order.selected_options.all():
            valid_options[order_option.option] = order_option.value
        for item_option in self.item_specification.selected_options.all():
            valid_options[item_option.option] = item_option.value
        return valid_options

    def process(self):
        """Process the item.

        Processing is done by delegating to the defined item processor for the
        item's order type.

        """

        self._set_status(self.IN_PRODUCTION, "Item is being processed")
        item_processor = utilities.get_item_processor(
            order_type=self.batch.order.order_type)
        try:
            output_path = item_processor.prepare_item(
                identifier=self.identifier,
                options=self.export_options()
            )
        except Exception:
            formatted_tb = traceback.format_exception(*sys.exc_info())
            error_message = (
                "Could not process order item {!r}. The error "
                "was: {}".format(self, formatted_tb)
            )
            logger.error(error_message)
            self._set_status(self.FAILED, error_message)
            raise
        return output_path

    def deliver(self, path):
        """Deliver the item

        Delivery is done by delegating to the defined item processor.
        """

        self._set_status(self.IN_PRODUCTION, "Item is being delivered")
        item_processor = utilities.get_item_processor(
            order_type=self.batch.order.order_type)
        delivery_options = self.export_delivery_options()
        try:
            delivery_information = (
                self.batch.order.export_delivery_information())
        except DeliveryInformation.DoesNotExist:
            delivery_information = None
        try:
            url = item_processor.deliver_item(
                item_path=path,
                identifier=self.identifier,
                item_id=self.item_specification.item_id,
                batch_id=self.batch.id,
                order_id=self.batch.order.id,
                user_name=self.batch.order.user.username,
                packaging=self.batch.order.packaging,
                delivery_options=delivery_options,
                delivery_information=delivery_information
            )
            self.url = url
        except Exception:
            formatted_tb = traceback.format_exception(*sys.exc_info())
            error_message = (
                "Could not deliver order item {!r}. The error "
                "was: {}".format(self, formatted_tb)
            )
            self.status = self.FAILED
            logger.error(error_message)
            self.additional_status_info = error_message
            raise
        else:
            self._set_status(self.COMPLETED, "Item processed successfully")
            self.available = True
            self.expires_on = self._create_expiry_date()
        finally:
            self.save()
        return url


    def _set_status(self, status, additional_info=""):
        self.status = status
        self.additional_status_info = additional_info
        if self.status == self.COMPLETED:
            self.completed_on = dt.datetime.now(pytz.utc)
        self.save()


    def save(self, *args, **kwargs):
        """Save instance into the database.

        This method reimplements django's default model.save() behaviour in
        order to update the item's batch's status.

        """

        super(OrderItem, self).save(*args, **kwargs)
        if self.status not in (self.ACCEPTED,
                               self.CANCELLED,
                               self.SUBMITTED,
                               self.SUSPENDED):
            self.update_batch_status()

    def update_batch_status(self):
        """Update a batch's status

        This method is called whenever an order item is saved.
        """

        logger.debug("Updating item's batch status...")
        batch = self.batch
        now = dt.datetime.now(pytz.utc)
        additional = ""
        completed_items = 0
        failed_items = 0
        for status, details in batch.order_items.values_list(
                "status", "additional_status_info"):
            if status == CustomizableItem.COMPLETED:
                completed_items += 1
            elif status == CustomizableItem.FAILED:
                failed_items += 1
                additional = " ".join((additional, details))
        if batch.order_items.count() == completed_items + failed_items:
            completed_on = now
            if failed_items > 0:
                new_status = CustomizableItem.FAILED
            else:
                new_status = CustomizableItem.COMPLETED
        else:
            completed_on = None
            new_status = CustomizableItem.IN_PRODUCTION
            additional = "Items are being processed"
        previous_status = batch.status
        if previous_status != new_status:
            batch.status = new_status
            batch.additional_status_info = additional
            batch.updated_on = now
            batch.completed_on = completed_on
            batch.save()

    def _create_expiry_date(self):
        generic_order_config = utilities.get_generic_order_config(
            self.batch.order.order_type)
        now = dt.datetime.now(pytz.utc)
        expiry_date = now + dt.timedelta(
            days=generic_order_config.get("item_availability_days", 1))
        return expiry_date


@python_2_unicode_compatible
class SelectedItemOption(models.Model):
    option = models.CharField(max_length=255)
    value = models.CharField(max_length=255, help_text='Value for this option')
    item_specification = models.ForeignKey(
        "ItemSpecification",
        related_name="selected_options",
        null=True,
        blank=True
    )

    def __str__(self):
        return "{}={!r}".format(self.option, self.value)


@python_2_unicode_compatible
class SelectedOrderOption(models.Model):
    option = models.CharField(max_length=255)
    value = models.CharField(max_length=255, help_text='Value for this option')
    order = models.ForeignKey(
        "Order",
        related_name="selected_options",
        null=True,
        blank=True
    )

    def __str__(self):
        return "{}={!r}".format(self.option, self.value)


@python_2_unicode_compatible
class SelectedPaymentOption(models.Model):
    item_specification = models.OneToOneField(
        'ItemSpecification',
        related_name='selected_payment_option',
    )
    option = models.CharField(max_length=255)

    def __str__(self):
        return self.option.name


@python_2_unicode_compatible
class SelectedSceneSelectionOption(models.Model):
    item_specification = models.ForeignKey(
        'ItemSpecification',
        related_name='selected_scene_selection_options'
    )
    option = models.CharField(max_length=255)
    value = models.CharField(max_length=255,
                             help_text='Value for this option')

    def __str__(self):
        return self.value


class BaseDeliveryOption(models.Model):
    MEDIA_DELIVERY = "mediadelivery"
    ONLINE_DATA_ACCESS = "onlinedataaccess"
    ONLINE_DATA_DELIVERY = "onlinedatadelivery"
    DELIVERY_CHOICES = [
        (MEDIA_DELIVERY, MEDIA_DELIVERY),
        (ONLINE_DATA_ACCESS, ONLINE_DATA_ACCESS),
        (ONLINE_DATA_DELIVERY, ONLINE_DATA_DELIVERY),
    ]

    delivery_type = models.CharField(
        max_length=30,
        choices=DELIVERY_CHOICES,
        default=ONLINE_DATA_ACCESS,
        help_text="Type of delivery that has been specified"
    )
    delivery_details = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        help_text="A comma separated string with further details pertaining "
                  "the selected delivery type, such as the protocol to use "
                  "for online data delivery. Each delivery type expects a "
                  "concrete string format."
    )
    copies = models.PositiveSmallIntegerField(null=True, blank=True)
    annotation = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return "{0.delivery_type}, {0.delivery_details}".format(self)


@python_2_unicode_compatible
class OrderDeliveryOption(BaseDeliveryOption):
    order = models.OneToOneField(
        'Order',
        related_name='selected_delivery_option',
        blank=True,
        null=True
    )


@python_2_unicode_compatible
class ItemSpecificationDeliveryOption(BaseDeliveryOption):
    item_specification = models.OneToOneField(
        'ItemSpecification',
        related_name='selected_delivery_option',
        blank=True,
        null=True
    )


@python_2_unicode_compatible
class Batch(models.Model):
    # subFunction values for DescribeResultAccess operation
    ALL_READY = "allReady"
    NEXT_READY = "nextReady"

    order = models.ForeignKey(
        "Order",
        null=True,
        blank=True,
        related_name="batches"
    )
    created_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True, blank=True)
    updated_on = models.DateTimeField(editable=False, blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=CustomizableItem.STATUS_CHOICES,
        default=CustomizableItem.SUBMITTED,
        help_text="processing status"
    )
    additional_status_info = models.TextField(
        help_text="Additional information about the status",
        blank=True
    )

    class Meta:
        verbose_name_plural = "batches"

    def __str__(self):
        return "id: {0.id}, order: {0.order.id}".format(self)

    def save(self, *args, **kwargs):
        """Save batch instance into the database.

        This method reimplements django's default model.save() behaviour in
        order to update the batch's order status.

        """

        super(Batch, self).save(*args, **kwargs)
        if self.status not in (CustomizableItem.ACCEPTED,
                               CustomizableItem.CANCELLED,
                               CustomizableItem.SUBMITTED,
                               CustomizableItem.SUSPENDED):
            self.update_order_status()

    def update_order_status(self):
        if self.order.order_type == Order.PRODUCT_ORDER:
            new_status = self.status
        elif self.order.order_type == Order.MASSIVE_ORDER:
            new_status = self._get_massive_order_status()
        elif self.order.order_type == Order.SUBSCRIPTION_ORDER:
            new_status = self._get_subscription_order_status()
        else:  # tasking order
            raise NotImplementedError
        previous_status = self.order.status
        if previous_status != new_status:
            logger.debug(
                "Updating batch's order status to {!r}".format(new_status)
            )
            now = dt.datetime.now(pytz.utc)
            self.order.status_changed_on = now
            self.order.status = new_status
            self.order.additional_status_info = ""
            if new_status in (CustomizableItem.COMPLETED,
                              CustomizableItem.FAILED):
                self.order.completed_on = now
            self.order.save()

    def _get_massive_order_status(self):
        existing_batch_statuses = self.order.batches.values_list(
            "status", flat=True).distinct()
        if CustomizableItem.IN_PRODUCTION in existing_batch_statuses:
            new_status = CustomizableItem.IN_PRODUCTION
        else:  # check if we need to create any more batches
            processor = utilities.get_item_processor(self.order.order_type)
            item_spec = self.order.item_specifications.get()
            start, end = processor.get_order_duration(item_spec)
            total_batches = processor.estimate_number_massive_order_batches(
                collection=item_spec.collection,
                start=start,
                end=end
            )
            if self.order.batches.count() == total_batches:
                logger.debug("All batches have been created")
                if CustomizableItem.FAILED in existing_batch_statuses:
                    new_status = CustomizableItem.FAILED
                else:
                    new_status = CustomizableItem.COMPLETED
            else:
                new_status = CustomizableItem.SUSPENDED
        return new_status

    def _get_subscription_order_status(self):
        if self.status == CustomizableItem.IN_PRODUCTION:
            new_status = CustomizableItem.IN_PRODUCTION
        else:
            new_status = CustomizableItem.SUSPENDED
        return new_status

