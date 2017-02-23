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
from decimal import Decimal
import sys
import traceback
import logging

import celery
from django.db import models
from django.conf import settings as django_settings
from django.utils.encoding import python_2_unicode_compatible
import pytz
from pyxb import BIND
import pyxb.bundles.opengis.oseo_1_0 as oseo

from . import utilities
from .utilities import _n

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

    def create_oseo_delivery_address(self):
        delivery_address = oseo.DeliveryAddressType()
        delivery_address.firstName = _n(self.first_name)
        delivery_address.lastName = _n(self.last_name)
        delivery_address.companyRef = _n(self.company_ref)
        delivery_address.postalAddress = BIND()
        delivery_address.postalAddress.streetAddress = _n(self.street_address)
        delivery_address.postalAddress.city = _n(self.city)
        delivery_address.postalAddress.state = _n(self.state)
        delivery_address.postalAddress.postalCode = _n(self.postal_code)
        delivery_address.postalAddress.country = _n(self.country)
        delivery_address.postalAddress.postBox = _n(self.post_box)
        delivery_address.telephoneNumber = _n(self.telephone)
        delivery_address.facsimileTelephoneNumber = _n(self.fax)
        return delivery_address


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

    def create_oseo_delivery_options(self):
        """Create an OSEO DeliveryOptionsType"""

        try:
            do = self.selected_delivery_option
        except SelectedDeliveryOption.DoesNotExist:
            dot = None
        else:
            dot = oseo.DeliveryOptionsType()
            if do.delivery_type == SelectedDeliveryOption.ONLINE_DATA_ACCESS:
                dot.onlineDataAccess = BIND(protocol=do.delivery_details)
            elif do.delivery_type == SelectedDeliveryOption.ONLINE_DATA_DELIVERY:
                dot.onlineDataDelivery = BIND(
                    protocol=do.delivery_details)
            elif do.delivery_type == SelectedDeliveryOption.MEDIA_DELIVERY:
                medium, _, shipping = do.delivery_details.partition(",")
                dot.mediaDelivery = BIND(
                    packageMedium=medium,
                    shippingInstructions=_n(shipping)
                )
            else:
                raise ValueError("Invalid delivery_type: "
                                 "{}".format(do.delivery_type))
            dot.numberOfCopies = _n(do.copies)
            dot.productAnnotation = _n(do.annotation)
            dot.specialInstructions = _n(do.special_instructions)
        return dot


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

    def create_oseo_delivery_information(self):
        """Create an OSEO DeliveryInformationType"""
        del_info = oseo.DeliveryInformationType()
        optional_attrs = [self.first_name, self.last_name, self.company_ref,
                          self.street_address, self.city, self.state,
                          self.postal_code, self.country, self.post_box,
                          self.telephone, self.fax]
        if any(optional_attrs):
            del_info.mailAddress = oseo.DeliveryAddressType()
            del_info.mailAddress.firstName = _n(self.first_name)
            del_info.mailAddress.lastName = _n(self.last_name)
            del_info.mailAddress.companyRef = _n(self.company_ref)
            del_info.mailAddress.postalAddress = BIND()
            del_info.mailAddress.postalAddress.streetAddress = _n(
                self.street_address)
            del_info.mailAddress.postalAddress.city = _n(self.city)
            del_info.mailAddress.postalAddress.state = _n(self.state)
            del_info.mailAddress.postalAddress.postalCode = _n(
                self.postal_code)
            del_info.mailAddress.postalAddress.country = _n(self.country)
            del_info.mailAddress.postalAddress.postBox = _n(self.post_box)
            del_info.mailAddress.telephoneNumber = _n(self.telephone)
            del_info.mailAddress.facsimileTelephoneNumber = _n(self.fax)
        for oa in self.onlineaddress_set.all():
            del_info.onlineAddress.append(oseo.OnlineAddressType())
            del_info.onlineAddress[-1].protocol = oa.protocol
            del_info.onlineAddress[-1].serverAddress = oa.server_address
            del_info.onlineAddress[-1].userName = _n(oa.user_name)
            del_info.onlineAddress[-1].userPassword = _n(oa.user_password)
            del_info.onlineAddress[-1].path = _n(oa.path)
        return del_info


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

    def create_oseo_order_monitor(
            self, presentation="brief"):
        om = oseo.CommonOrderMonitorSpecification()
        if self.order_type == self.MASSIVE_ORDER:
            om.orderType = self.PRODUCT_ORDER
            om.orderReference = self.MASSIVE_ORDER_REFERENCE
        else:
            om.orderType = self.order_type
            om.orderReference = _n(self.reference)
        om.orderId = str(self.id)
        om.orderStatusInfo = oseo.StatusType(
            status=self.status,
            additionalStatusInfo=_n(self.additional_status_info),
            missionSpecificStatusInfo=_n(self.mission_specific_status_info)
        )
        om.orderDateTime = self.status_changed_on
        om.orderRemark = _n(self.remark)
        try:
            d = self.delivery_information.create_oseo_delivery_information()
            om.deliveryInformation = d
        except DeliveryInformation.DoesNotExist:
            pass
        try:
            om.invoiceAddress = \
                self.invoice_address.create_oseo_delivery_address()
        except InvoiceAddress.DoesNotExist:
            pass
        om.packaging = _n(self.packaging)
        # add any 'option' elements
        om.deliveryOptions = self.create_oseo_delivery_options()
        om.priority = _n(self.priority)
        if presentation == "full":
            if self.order_type == self.PRODUCT_ORDER:
                batch = self.batches.get()
                sits = batch.create_oseo_items_status()
                om.orderItem.extend(sits)
            elif self.order_type == self.SUBSCRIPTION_ORDER:
                for batch in self.batches.all()[1:]:
                    sits = batch.create_oseo_items_status()
                    om.orderItem.extend(sits)
            else:
                raise NotImplementedError
        return om


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

    def create_oseo_status_item_type(self):
        """Create a CommonOrderStatusItemType element"""
        sit = oseo.CommonOrderStatusItemType()
        # TODO - add the other optional elements
        sit.itemId = str(self.item_id)
        # oi.identifier is guaranteed to be non empty for
        # normal product orders and for subscription batches
        sit.productId = self.identifier
        sit.productOrderOptionsId = "Options for {} {}".format(
            self.collection, self.batch.order.order_type)
        sit.orderItemRemark = _n(self.remark)
        collection_settings = utilities.get_collection_settings(
            self.collection)
        sit.collectionId = _n(collection_settings["collection_identifier"])
        # add any 'option' elements that may be present
        # add any 'sceneSelection' elements that may be present
        sit.deliveryOptions = self.create_oseo_delivery_options()
        # add any 'payment' elements that may be present
        # add any 'extension' elements that may be present
        sit.orderItemStatusInfo = oseo.StatusType()
        sit.orderItemStatusInfo.status = self.status
        sit.orderItemStatusInfo.additionalStatusInfo = \
            _n(self.additional_status_info)
        sit.orderItemStatusInfo.missionSpecificStatusInfo= \
            _n(self.mission_specific_status_info)
        return sit

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

        self.status = self.IN_PRODUCTION
        self.additional_status_info = "Item is being processed"
        self.save()
        item_processor = utilities.get_item_processor(
            order_type=self.batch.order.order_type)
        options = self.export_options()
        delivery_options = self.export_delivery_options()
        try:
            result = item_processor.process_item(
                identifier=self.identifier,
                item_id=self.item_specification.item_id,
                order_id=self.batch.order.id,
                user_name=self.batch.order.user.username,
                delivery_type=delivery_options["delivery_type"],
                protocol=delivery_options["protocol"],
                packaging=self.batch.order.packaging,
                annotation=delivery_options["annotation"],
                copies=delivery_options["copies"],
                special_instructions=delivery_options["special_instructions"],
                options=options
            )
            url, output_path = result
            self.url = url
        except Exception:
            formatted_tb = traceback.format_exception(*sys.exc_info())
            error_message = (
                "Could not process order item {!r}. The error "
                "was: {}".format(self, formatted_tb)
            )
            self.status = self.FAILED
            logger.error(error_message)
            self.additional_status_info = error_message
            raise
        else:
            self.status = self.COMPLETED
            self.additional_status_info = "Item processed successfully"
            self.completed_on = dt.datetime.now(pytz.utc)
            self.available = True
            self.expires_on = self._create_expiry_date()
        finally:
            self.save()
        return processing_result

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

    def create_oseo_items_status(self):
        items_status = []
        for i in self.order_items.all():
            items_status.append(i.create_oseo_status_item_type())
        return items_status

    def get_completed_items(self, behaviour):
        last_time = self.order.last_describe_result_access_request
        order_delivery = self.order.selected_delivery_option.delivery_type
        completed = []
        if self.status != CustomizableItem.COMPLETED:
            # batch is either still being processed,
            # failed or already downloaded, so we don't care for it
            pass
        else:
            batch_complete_items = []
            order_items = self.order_items.all()
            for oi in order_items:
                try:
                    delivery = oi.selected_delivery_option.delivery_type
                except SelectedDeliveryOption.DoesNotExist:
                    delivery = order_delivery
                if delivery != SelectedDeliveryOption.ONLINE_DATA_ACCESS:
                    # getStatus only applies to items with onlinedataaccess
                    continue
                if oi.status == CustomizableItem.COMPLETED:
                    if (last_time is None or behaviour == self.ALL_READY) or \
                            (behaviour == self.NEXT_READY and
                                     oi.completed_on >= last_time):
                        batch_complete_items.append(oi)
            if self.order.packaging == Order.ZIP:
                if len(batch_complete_items) == len(order_items):
                    # the zip is ready, lets get only a single file
                    # because they all point to the same URL
                    completed.append(batch_complete_items[0])
                else:  # the zip is not ready yet
                    pass
            else:  # lets get each file that is complete
                completed = batch_complete_items
        return completed

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

