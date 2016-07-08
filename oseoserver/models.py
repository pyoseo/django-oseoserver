# Copyright 2014 Ricardo Garcia Silva
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
Database models for pyoseo
"""

from __future__ import absolute_import
import datetime as dt
from decimal import Decimal
import sys
import traceback
import logging

from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings as django_settings
import pytz
from pyxb import BIND
import pyxb.bundles.opengis.oseo_1_0 as oseo

from . import errors
from . import settings
from . import utilities
from .constants import DeliveryOption
from .constants import MASSIVE_ORDER_REFERENCE
from .constants import OrderStatus
from .constants import OrderType
from .constants import Packaging
from .constants import Presentation
from .constants import Priority
from .constants import StatusNotification
from .utilities import _n


logger = logging.getLogger(__name__)

COLLECTION_CHOICES = [
    (c["name"], c["name"]) for c in settings.get_collections()]

STATUS_CHOICES = [
    (status.value, status.value) for status in OrderStatus]


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


class Batch(models.Model):
    # subFunction values for DescribeResultAccess operation
    ALL_READY = "allReady"
    NEXT_READY = "nextReady"

    order = models.ForeignKey("Order", null=True, related_name="batches")
    created_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True, blank=True)
    updated_on = models.DateTimeField(editable=False, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES,
                              default=OrderStatus.SUBMITTED.value,
                              help_text="initial status")

    def update_status(self):
        """Update a batch's status

        This method is called whenever an order item is saved.
        """

        done_items = 0
        for item in self.order_items.all():
            item_status = OrderStatus(item.status)
            if item_status in (OrderStatus.COMPLETED, OrderStatus.DOWNLOADED):
                done_items += 1
            else:
                new_status = item_status
                break
        else:
            if done_items == self.order_items.count():
                new_status = OrderStatus.COMPLETED
            else:
                new_status = OrderStatus.IN_PRODUCTION
        now = dt.datetime.now(pytz.utc)
        self.status = new_status.value
        self.updated_on = now
        if new_status in (OrderStatus.COMPLETED, OrderStatus.TERMINATED,
                          OrderStatus.FAILED):
            self.completed_on = now
        elif new_status == OrderStatus.DOWNLOADED:
            pass
        else:
            self.completed_on = None
        self.save()

    def save(self, *args, **kwargs):
        """Reimplment save() method in order to update the batch's order."""
        super(Batch, self).save(*args, **kwargs)
        self.order.update_status()

    def price(self):
        total = Decimal(0)
        return total

    def create_order_item(self, status, additional_status_info,
                          order_item_spec):
        item = OrderItem(
            batch=self,
            status=status,
            additional_status_info=additional_status_info,
            remark=order_item_spec["order_item_remark"],
            collection=order_item_spec["collection"],
            identifier=order_item_spec.get("identifier", ""),
            item_id=order_item_spec["item_id"]
        )
        item.save()
        for name, value in order_item_spec["option"].items():
            # assuming that the option has already been validated
            selected_option = SelectedOption(option=name, value=value,
                                             customizable_item=item)
            selected_option.save()
        for name, value in order_item_spec["scene_selection"].items():
            item.selected_scene_selection_options.add(
                SelectedSceneSelectionOption(option=name, value=value))
        delivery = order_item_spec["delivery_options"]
        if delivery is not None:
            copies = 1 if delivery["copies"] is None else delivery["copies"]
            sdo = SelectedDeliveryOption(
                customizable_item=item,

                delivery_type=None,
                delivery_details=None,

                annotation=delivery["annotation"],
                copies=copies,
                special_instructions=delivery["special_instructions"],
                option=delivery["type"]
            )
            sdo.save()
        if order_item_spec["payment"] is not None:
            item.selected_payment_option = SelectedPaymentOption(
                option=order_item_spec["payment"])
        item.save()
        return item

    def create_oseo_items_status(self):
        items_status = []
        for i in self.order_items.all():
            items_status.append(i.create_oseo_status_item_type())
        return items_status

    def get_completed_files(self, behaviour):
        last_time = self.order.last_describe_result_access_request
        order_delivery = self.order.selected_delivery_option.option
        completed = []
        if self.status() != OrderStatus.COMPLETED.value:
            # batch is either still being processed,
            # failed or already downloaded, so we don't care for it
            pass
        else:
            batch_complete_items = []
            order_items = self.order_items.all()
            for oi in order_items:
                try:
                    delivery = oi.selected_delivery_option.option
                except SelectedDeliveryOption.DoesNotExist:
                    delivery = order_delivery
                if delivery != DeliveryOption.ONLINE_DATA_ACCESS.value:
                    # getStatus only applies to items with onlinedataaccess
                    continue
                if oi.status == OrderStatus.COMPLETED.value:
                    if (last_time is None or behaviour == self.ALL_READY) or \
                            (behaviour == self.NEXT_READY and
                                     oi.completed_on >= last_time):
                        for f in oi.files.filter(available=True):
                            batch_complete_items.append((f, delivery))
            if self.order.packaging == Packaging.ZIP.value:
                if len(batch_complete_items) == len(order_items):
                    # the zip is ready, lets get only a single file
                    # because they all point to the same URL
                    completed.append(batch_complete_items[0])
                else:  # the zip is not ready yet
                    pass
            else:  # lets get each file that is complete
                completed = batch_complete_items
        return completed

    class Meta:
        verbose_name_plural = "batches"

    def __unicode__(self):
        return str("{}({})".format(self.__class__.__name__, self.id))


class CustomizableItem(models.Model):
    status = models.CharField(max_length=50, choices=STATUS_CHOICES,
                              default=OrderStatus.SUBMITTED.value,
                              help_text="initial status")
    additional_status_info = models.TextField(help_text="Additional "
                                              "information about the status",
                                              blank=True)
    mission_specific_status_info = models.TextField(help_text="Additional "
                                                    "information about the "
                                                    "status that is specific "
                                                    "to the mission",
                                                    blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True, blank=True)
    status_changed_on = models.DateTimeField(editable=False, blank=True,
                                             null=True)
    remark = models.TextField(help_text="Some specific remark about the item",
                              blank=True)

    def __unicode__(self):
        try:
            instance = Order.objects.get(id=self.id)
        except ObjectDoesNotExist:
            instance = OrderItem.objects.get(id=self.id)
        return instance.__unicode__()

    def create_oseo_delivery_options(self):
        """Create an OSEO DeliveryOptionsType"""

        try:
            do = self.selected_delivery_option
        except SelectedDeliveryOption.DoesNotExist:
            dot = None
        else:
            dot = oseo.DeliveryOptionsType()
            if do.delivery_type == DeliveryOption.ONLINE_DATA_ACCESS.value:
                dot.onlineDataAccess = BIND(protocol=do.delivery_details)
            elif do.delivery_type == DeliveryOption.ONLINE_DATA_DELIVERY.value:
                dot.onlineDataDelivery = BIND(
                    protocol=do.delivery_details)
            elif do.delivery_type == DeliveryOption.MEDIA_DELIVERY.value:
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


class Extension(models.Model):

    item = models.ForeignKey(CustomizableItem)
    text = models.CharField(
        max_length=255, blank=True,
        help_text="Custom extensions to the OSEO standard"
    )

    def __unicode__(self):
        return self.text


class DeliveryInformation(AbstractDeliveryAddress):
    order = models.OneToOneField("Order", related_name="delivery_information")

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


class InvoiceAddress(AbstractDeliveryAddress):
    order = models.OneToOneField("Order", null=True,
                                 related_name="invoice_address")

    class Meta:
        verbose_name_plural = "invoice addresses"


class OnlineAddress(models.Model):
    FTP = 'ftp'
    SFTP = 'sftp'
    FTPS = 'ftps'
    PROTOCOL_CHOICES = (
        (FTP, FTP),
        (SFTP, SFTP),
        (FTPS, FTPS),
    )
    delivery_information = models.ForeignKey('DeliveryInformation')
    protocol = models.CharField(max_length=20, default=FTP,
                                choices=PROTOCOL_CHOICES)
    server_address = models.CharField(max_length=255)
    user_name = models.CharField(max_length=50, blank=True)
    user_password = models.CharField(max_length=50, blank=True)
    path = models.CharField(max_length=1024, blank=True)

    class Meta:
        verbose_name_plural = 'online addresses'


class Order(CustomizableItem):
    PACKAGING_CHOICES = [(v.value, v.value) for v in Packaging]
    ORDER_TYPE_CHOICES = [(t.value, t.value) for t in OrderType]

    user = models.ForeignKey(django_settings.AUTH_USER_MODEL,
                             related_name="orders")
    order_type = models.CharField(
        max_length=30,
        default=OrderType.PRODUCT_ORDER.value,
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
        choices=[(p.value, p.value) for p in Priority],
        blank=True
    )
    status_notification = models.CharField(
        max_length=10,
        default=StatusNotification.NONE.value,
        choices=[(n.value, n.value) for n in StatusNotification]
    )

    def show_batches(self):
        return ', '.join([str(b.id) for b in self.batches.all()])
    show_batches.short_description = 'available batches'

    def create_batch(self, item_status, additional_status_info,
                     *order_items_spec):
        batch = Batch(order=self, status=self.status)
        batch.save()
        for item_spec in order_items_spec:
            batch.create_order_item(item_status, additional_status_info,
                                    item_spec)
        self.batches.add(batch)
        return batch

    def create_oseo_order_monitor(
            self, presentation=Presentation.BRIEF.value):
        om = oseo.CommonOrderMonitorSpecification()
        if self.order_type == OrderType.MASSIVE_ORDER.value:
            om.orderType = OrderType.PRODUCT_ORDER.value
            om.orderReference = MASSIVE_ORDER_REFERENCE
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
        if presentation == Presentation.FULL.value:
            if self.order_type == OrderType.PRODUCT_ORDER.value:
                batch = self.batches.get()
                sits = batch.create_oseo_items_status()
                om.orderItem.extend(sits)
            elif self.order_type == OrderType.SUBSCRIPTION_ORDER.value:
                for batch in self.batches.all()[1:]:
                    sits = batch.create_oseo_items_status()
                    om.orderItem.extend(sits)
            else:
                raise NotImplementedError
        return om

    def update_status(self):
        try:
            self.productorder.update_status()
        except ProductOrder.DoesNotExist:
            self.derivedorder.update_sattus()

    def __unicode__(self):
        return '{}'.format(self.id)


class OrderPendingModerationManager(models.Manager):

    def get_queryset(self):
        return super(OrderPendingModerationManager,
                     self).get_queryset().filter(
            status=OrderStatus.SUBMITTED.value)


class OrderPendingModeration(Order):
    objects = OrderPendingModerationManager()

    class Meta:
        proxy = True
        verbose_name_plural = "orders pending moderation"


class ProductOrder(Order):

    def update_status(self):
        # product orders have only one batch
        batch = self.batches.get()
        self.status = batch.status
        additional_info = ""
        for item in batch.order_items.all():
            additional_info += ("Item {0.item_id} - "
                                "{0.additional_status_info} \n\n".format(item))
        self.additional_status_info = additional_info
        self.save()

    def __unicode__(self):
        return "{}({})".format(self.__class__.__name__, self.id)


# TODO - Remove this model
class DerivedOrder(Order):

    def update_status(self):
        try:
            self.massiveorder.update_status()
        except MassiveOrder.DoesNotExist:
            try:
                self.subscriptionorder.update_status()
            except SubscriptionOrder.DoesNotExist:
                self.taskingorder.update_status()


class MassiveOrder(DerivedOrder):

    def __unicode__(self):
        return "{}({})".format(self.__class__.__name__, self.id)


class SubscriptionOrder(DerivedOrder):
    begin_on = models.DateTimeField(help_text="Date and time for when the "
                                              "subscription should become "
                                              "active.")
    end_on = models.DateTimeField(help_text="Date and time for when the "
                                            "subscription should terminate.")

    def create_batch(self, item_status, additional_status_info,
                     *order_item_spec, **kwargs):
        """
        Create a batch for a subscription order.

        Subscription orders are different from normal product orders because
        the user is not supposed to be able to ask for the same collection
        twice.

        :param item_status:
        :param additional_status_info:
        :param order_item_spec:
        :return:
        """

        batch = Batch()
        batch.save()
        for oi in order_item_spec:
            collection = oi["collection"]
            previous_collections = [oi.collection for oi in
                                    batch.order_items.all()]
            if collection not in previous_collections:
                batch.create_order_item(item_status, additional_status_info,
                                        oi)
            else:
                raise errors.ServerError("Repeated collection: "
                                         "{}".format(collection))
        self.batches.add(batch)
        return batch

    def update_status(self):
        #most_recent = [b for b in self.batches.order_by("-completed_on")][0]
        raise NotImplementedError

    def __unicode__(self):
        return "{}({})".format(self.__class__.__name__, self.id)


class TaskingOrder(DerivedOrder):

    def __unicode__(self):
        return "{}({})".format(self.__class__.__name__, self.id)


class OrderItem(CustomizableItem):
    batch = models.ForeignKey("Batch", related_name="order_items")
    collection = models.CharField(
        max_length=255,
        choices=COLLECTION_CHOICES
    )
    identifier = models.CharField(
        max_length=255,
        blank=True,
        help_text="identifier for this order item. It is the product Id in "
                  "the catalog"
    )
    item_id = models.CharField(
        max_length=80,
        help_text="Id for the item in the order request"
    )
    url = models.CharField(
        max_length=255,
        help_text="URL where this item is available",
        blank=True
    )
    expires_on = models.DateTimeField(null=True, blank=True)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    available = models.BooleanField(default=False)
    downloads = models.SmallIntegerField(
        default=0,
        help_text="Number of times this order item has been downloaded."
    )

    def export_options(self):
        valid_options = dict()
        for order_option in self.batch.order.selected_options.all():
            valid_options[order_option.name] = order_option.value
        for item_option in self.selected_options.all():
            valid_options[item_option.value] = item_option.value
        return valid_options

    def export_delivery_options(self):
        delivery = getattr(self, "selected_delivery_option", None)
        if delivery is None:
            delivery = getattr(self.batch.order, "selected_delivery_option")
        valid_delivery = {
            "copies": delivery.copies,
            "annotation": delivery.annotation,
            "special_instructions": delivery.special_instructions,
            "delivery_type": delivery.delivery_type,
            #"delivery_fee": delivery.option.delivery_fee,
        }
        if delivery.delivery_type == DeliveryOption.ONLINE_DATA_ACCESS.value:
            protocol = delivery.delivery_details
            allowed_options = settings.get_online_data_access_options()
            fee = [opt.get("fee", 0) for opt in allowed_options if opt["protocol"] == protocol][0]
            valid_delivery["protocol"] = protocol

        elif delivery.delivery_type == DeliveryOption.ONLINE_DATA_DELIVERY.value:
            pass


        elif delivery.delivery_type == DeliveryOption.MEDIA_DELIVERY.value:
            valid_delivery["medium"] = delivery.delivery_details
        return valid_delivery

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

    def process(self):
        """Process the item

        This method will call the external item_processor object's
        `process_item_online_access` method

        """

        self.status = OrderStatus.IN_PRODUCTION.value
        self.additional_status_info = "Item is being processed"
        self.save()
        order = self.batch.order
        item_processor = utilities.get_item_processor(self)
        options = self.export_options()
        delivery_options = self.export_delivery_options()
        processor_options = options.copy()
        processor_options.update(delivery_options)
        logger.debug("processor_options: {}".format(processor_options))
        try:
            url, output_path = item_processor.process_item_online_access(
                identifier=self.identifier,
                item_id=self.item_id,
                order_id=order.id,
                user_name=order.user.username,
                packaging=order.packaging,
                **processor_options
            )
        except Exception:
            formatted_tb = traceback.format_exception(*sys.exc_info())
            error_message = (
                "Could not process order item {!r}. The error "
                "was: {}".format(self, formatted_tb)
            )
            self.status = OrderStatus.FAILED.value
            self.additional_status_info = error_message
            raise errors.OseoServerError(error_message)
        else:
            self.status = OrderStatus.COMPLETED.value
            self.additional_status_info = "Item processed"
            now = dt.datetime.now(pytz.utc)
            self.url = url
            self.completed_on = now
            self.available = True
            self.expires_on = self._create_expiry_date()
        finally:
            self.save()
        return url, output_path

    def can_be_deleted(self):
        result = False
        now = dt.datetime.now(pytz.utc)
        if self.expires_on < now:
            result = True
        else:
            user = self.order_item.batch.order.user
            if self.downloads > 0 and user.delete_downloaded_files:
                result = True
        return result

    def save(self, *args, **kwargs):
        """Reimplementation of model.save() to update status on batch"""
        super(OrderItem, self).save(*args, **kwargs)
        self.batch.update_status()

    def _create_expiry_date(self):
        now = dt.datetime.now(pytz.utc)
        order_type = OrderType(self.batch.order.order_type)
        generic_order_config = utilities.get_generic_order_config(order_type)
        expiry_date = now + dt.timedelta(
            days=generic_order_config.get("item_availability_days",1))
        return expiry_date

    def __unicode__(self):
        return ("id={0.id!r}, batch={1.id!r}, "
                "order={2.id!r}, item_id={0.item_id!r}".format(
            self, self.batch, self.batch.order)
        )



#class OseoFile(models.Model):
#    order_item = models.ForeignKey("OrderItem", related_name="files")
#    created_on = models.DateTimeField(auto_now_add=True)
#    url = models.CharField(max_length=255, help_text="URL where this file "
#                                                     "is available")
#    expires_on = models.DateTimeField(null=True, blank=True)
#    last_downloaded_at = models.DateTimeField(null=True, blank=True)
#    available = models.BooleanField(default=False)
#    downloads = models.SmallIntegerField(default=0,
#                                         help_text="Number of times this "
#                                                   "order item has been "
#                                                   "downloaded.")
#
#    def can_be_deleted(self):
#        result = False
#        now = dt.datetime.now(pytz.utc)
#        if self.expires_on < now:
#            result = True
#        else:
#            user = self.order_item.batch.order.user
#            if self.downloads > 0 and user.delete_downloaded_files:
#                result = True
#        return result
#
#    def __unicode__(self):
#        return self.url


class SelectedOption(models.Model):
    customizable_item = models.ForeignKey('CustomizableItem',
                                          related_name='selected_options')
    option = models.CharField(max_length=255)
    value = models.CharField(max_length=255, help_text='Value for this option')

    def __unicode__(self):
        return self.value


class SelectedPaymentOption(models.Model):
    order_item = models.OneToOneField('OrderItem',
                                      related_name='selected_payment_option',
                                      null=True,
                                      blank=True)
    option = models.CharField(max_length=255)

    def __unicode__(self):
        return self.option.name


class SelectedSceneSelectionOption(models.Model):
    order_item = models.ForeignKey(
        'OrderItem',
        related_name='selected_scene_selection_options'
    )
    option = models.CharField(max_length=255)
    value = models.CharField(max_length=255,
                             help_text='Value for this option')

    def __unicode__(self):
        return self.value


class SelectedDeliveryOption(models.Model):
    DELIVERY_CHOICES = [(v.value, v.value) for v in DeliveryOption]

    customizable_item = models.OneToOneField(
        'CustomizableItem',
        related_name='selected_delivery_option',
        blank=True,
        null=True
    )
    delivery_type = models.CharField(
        max_length=30,
        choices=DELIVERY_CHOICES,
        default=DeliveryOption.ONLINE_DATA_ACCESS.value,
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

    def __unicode__(self):
        return "{0.delivery_type}, {0.delivery_details}".format(self)


class SubscriptionBatch(Batch):
    timeslot = models.DateTimeField()
    collection = models.CharField(
        max_length=255,
        choices=COLLECTION_CHOICES
    )

    class Meta:
        verbose_name_plural = "subscription batches"

    def __unicode__(self):
        return str("{}({})".format(self.__class__.__name__, self.id))
