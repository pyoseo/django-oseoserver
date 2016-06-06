# Copyright 2014 Ricardo Garcia Silva
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

"""Implements the OSEO Submit operation"""

from __future__ import absolute_import
import logging
import datetime as dt
import pytz

from django.db import transaction
import pyxb.bundles.opengis.oseo_1_0 as oseo
from lxml import etree

from .. import models
from .. import errors
from .. import utilities
from .. import settings
from ..utilities import _n, _c
from ..constants import ENCODING
from ..constants import DeliveryOption
from ..constants import DeliveryOptionProtocol
from ..constants import OrderType
from ..constants import OrderStatus
from ..constants import Priority
from ..constants import MASSIVE_ORDER_REFERENCE
from ..constants import StatusNotification
from .base import OseoOperation

logger = logging.getLogger(__name__)


class Submit(OseoOperation):

    @transaction.atomic
    def __call__(self, request, user):
        """Implements the OSEO Submit operation.

        Parameters
        ----------
        request: oseo.Submit
            The incoming request
        user: django.contrib.auth.User
            The django user that placed the request

        Returns
        -------
        str
            The XML response

        """

        status_notification = self.validate_status_notification(request)
        if request.orderSpecification is not None:
            requested_spec = request.orderSpecification
            if len(requested_spec.orderItem) > settings.get_max_order_items():
                raise errors.OseoError("NoApplicableCode",
                                       "Code not applicable")
            order_spec = self.process_order_specification(
                request.orderSpecification)
        else:
            raise errors.ServerError("Submit with quotationId is not "
                                     "implemented")
        # TODO - raise an error if there are no delivery options on the
        # order_specification either at the order or order item levels
        order = self.create_order(
            order_type=order_spec["order_type"],
            delivery_options=order_spec["delivery_options"],
            order_items=order_spec["order_item"],
            user=user,
            status_notification=status_notification,
            priority=order_spec["priority"],
            order_reference=order_spec["order_reference"],
            order_remark=order_spec["order_remark"],
            delivery_information=order_spec["delivery_information"],
            options=order_spec["option"],
            invoice_address=order_spec["invoice_address"],
            packaging=order_spec["packaging"],
            extension=order_spec["extension"]
        )
        response = oseo.SubmitAck(status='success')
        response.orderId = str(order.id)
        response.orderReference = _n(order.reference)
        return response, order

    def create_order(self, order_type, delivery_options, order_items,
                     user, status_notification,
                     priority="", order_reference=None,
                     order_remark=None, delivery_information=None,
                     options=None, invoice_address=None,
                     packaging=None, extension=None):
        """Persist the already parsed order specification in the database.

        Parameters
        ----------
        order_type: constants.OrderType
            Enumeration object with the type of order being created
        delivery_options: dict
            A mapping with the parsed delivery options
        order_items: list
            A list of dictionaries that hold the specification for the parsed
            order items that are being requested in the order
        user: django.contrib.auth.models.User
            The django user that placed the order
        status_notification: constants.StatusNotification
            Enumeration object with the type of status notification to use
        priority: constants.Priority
            Enumeration object with the priority of the order
        order_reference: str
            A textual reference for the order
        order_remark: str
            A textual remark concerning the order
        delivery_information
        options
        invoice_address
        packaging
        extension

        Returns
        -------
        ProductOrder or MassiveOrder or SubscriptionOrder or TaskingOrder
            The corresponding django model class that was created

        """

        generic_order_config = utilities.get_generic_order_config(
            order_type)
        if generic_order_config.get("automatic_approval", False):
            default_status = OrderStatus.ACCEPTED
            additional_status_info = ("Order is placed in processing queue")
            item_additional_status_info = ("Order item has been placed in the "
                                           "processing queue")
        else:
            default_status = OrderStatus.SUBMITTED
            additional_status_info = "Order is awaiting approval"
            item_additional_status_info = ""
        OrderModel = {
            OrderType.PRODUCT_ORDER: models.ProductOrder,
            OrderType.MASSIVE_ORDER: models.MassiveOrder,
            OrderType.SUBSCRIPTION_ORDER: models.SubscriptionOrder,
            OrderType.TASKING_ORDER: models.TaskingOrder,
        }.get(order_type)
        order = OrderModel(
            status=default_status.value,
            additional_status_info=additional_status_info,
            mission_specific_status_info="",
            remark=order_remark,
            user=user,
            order_type=order_type.value,
            reference=order_reference,
            packaging=packaging,
            priority=priority.value,
            status_notification=status_notification.value
        )
        if order_type == OrderType.SUBSCRIPTION_ORDER:
            # get begin and end dates for the subscription
            item_processor = utilities.import_class(
                generic_order_config["item_processor"])
            begin, end = item_processor.get_subscription_duration(options)
            now = dt.datetime.now(pytz.utc)
            order.begin_on = begin or now
            order.end_on = end or now + dt.timedelta(days=365 * 10)  # ten years
        order.save()
        # implement InvoiceAddress
        # implement DeliveryInformation
        for option_name, option_value in options.items():
            order.selected_options.add(
                models.SelectedOption(option=option_name, value=option_value),
                bulk=False
            )

        sdo = models.SelectedDeliveryOption(
            customizable_item=order,
            annotation=delivery_options["annotation"],
            copies=delivery_options["copies"],
            special_instructions=delivery_options["special_instructions"],
            delivery_type=delivery_options["type"].value,
            delivery_details=delivery_options["protocol"].value
        )
        sdo.save()
        order.save()
        order.create_batch(
            order.status,
            item_additional_status_info,
            *order_items
        )
        for ext in extension or []:
            e = models.Extension(item=order, text=ext)
            e.save()
        return order

    def get_collection_id(self, item_id, item_processor_path):
        """Determine the collection identifier for the specified item.

        This method is used when the requested order item does not provide the
        optional 'collectionId' element. It instatiates the external item
        processor class and calls it's `get_collection_id` method, passing the
        inpurt `item_id` as the sole parameter.

        Parameters
        ----------
        item_id: str
            The identifier of the requested order item
        item_processor_path: str
            Python path to the class to be used an an item processor for order
            items

        Returns
        -------
        str
            Identifier of the collection

        Raises
        ------
        oseoserver.errors.OseroServerError
            If the collection identifier cannot be retrieved

        """

        item_processor = utilities.import_class(item_processor_path)
        return item_processor.get_collection_id(item_id)

    def get_delivery_information(self, requested_delivery_info):
        if requested_delivery_info is not None:
            info = dict()
            requested_mail_info = requested_delivery_info.mailAddress
            requested_online_info = requested_delivery_info.onlineAddress
            if requested_mail_info is not None:
                info["mail_address"] = self._get_delivery_address(
                    requested_mail_info)
            if len(requested_online_info) > 0:
                info["online_address"] = []
                for online_address in requested_online_info:
                    info["online_address"].append({
                        "protocol": DeliveryOptionProtocol(
                            _c(online_address.protocol)),
                        "server_address": _c(online_address.serverAddress),
                        "user_name": _c(online_address.userName),
                        "user_password": _c(online_address.userPassword),
                        "path": _c(online_address.path),
                    })
        else:
            info = None
        return info

    def get_invoice_address(self, requested_invoice_address):
        if requested_invoice_address is not None:
            invoice = self._get_delivery_address(requested_invoice_address)
        else:
            invoice = None
        return invoice

    def process_order_specification(self, order_specification):
        """Validate and extract the order specification from the request

        Parameters
        ----------
        order_specification: pyxb.Order
            The input order specification

        Returns
        -------
        dict
            The validate order specification

        """

        order_type = self._get_order_type(order_specification)
        self.validate_order_type(order_type)
        spec = {
            "order_type": order_type,
            "order_item": [],
        }
        for order_item in order_specification.orderItem:
            spec["order_item"].append(
                self.validate_order_item(order_item, order_type)
            )
        spec["order_reference"] = _c(order_specification.orderReference)
        spec["order_remark"] = _c(order_specification.orderRemark)
        spec["packaging"] = self._validate_packaging(
            order_specification.packaging)
        spec["priority"] = Priority(
            _c(order_specification.priority) or Priority.STANDARD.value)
        spec["delivery_information"] = self.get_delivery_information(
            order_specification.deliveryInformation)
        spec["invoice_address"] = self.get_invoice_address(
            order_specification.invoiceAddress)
        requested_collections = [i["collection"] for i in spec["order_item"]]
        spec["option"] = self._validate_global_options(order_specification,
                                                       order_type,
                                                       requested_collections)
        spec["delivery_options"] = self._validate_global_delivery_options(
            order_specification, order_type, requested_collections)
        spec["extension"] = [e for e in order_specification.extension]
        return spec

    def validate_order_item(self, requested_item, order_type):
        """Validate an order item.

        Parameters
        ----------
        requested_item: pyxb.bundles.opengis.oseo_1_0.Order
            The requested order item
        order_type: oseoserver.constants.OrderType
            The enumeration value of the requested order type

        Returns
        -------

        """

        item = {
            "item_id": requested_item.itemId,
            "product_order_options_id": _c(
                requested_item.productOrderOptionsId),
            "order_item_remark": _c(requested_item.orderItemRemark)
        }

        item_identifier = None
        if order_type in (OrderType.PRODUCT_ORDER, OrderType.MASSIVE_ORDER):
            item_identifier = _c(requested_item.productId.identifier)
            item["identifier"] = item_identifier
        elif order_type == OrderType.TASKING_ORDER:
            item["tasking_id"] = None  # TODO: implement this
        generic_order_config = utilities.get_generic_order_config(order_type)
        collection_config = self.validate_requested_collection(
            order_type, generic_order_config, requested_item)
        specific_order_config = collection_config[order_type.value.lower()]
        item["collection"] = collection_config["name"]
        item["option"] = self._validate_requested_options(
            requested_item.option,
            order_type,
            collection_config["name"]
        )
        item["delivery_options"] = self._validate_delivery_options(
            requested_item.deliveryOptions, specific_order_config)
        item["scene_selection"] = dict()  # not implemented yet
        item["payment"] = None  # not implemented yet
        # extensions to the CommonOrderItemType are not implemented yet
        return item

    def validate_requested_collection(self, order_type, generic_order_config,
                                      requested_item):
        if order_type in (OrderType.PRODUCT_ORDER, OrderType.MASSIVE_ORDER):
            collection_id = requested_item.productId.collectionId
            if collection_id is None:
                collection_id = self.get_collection_id(
                    requested_item.productId.identifier,
                    generic_order_config["item_processor"]
                )
        elif order_type == OrderType.SUBSCRIPTION_ORDER:
            collection_id = requested_item.collectionId
        else:  # tasking order
            raise NotImplementedError
        collection_config = utilities.validate_collection_id(collection_id)
        is_enabled = collection_config.get(order_type.value.lower(),
                                           {}).get("enabled", False)
        if is_enabled:
            result = collection_config
        else:
            if order_type in (OrderType.PRODUCT_ORDER,
                              OrderType.MASSIVE_ORDER):
                raise errors.ProductOrderingNotSupportedError()
            elif order_type == OrderType.SUBSCRIPTION_ORDER:
                raise errors.SubscriptionNotSupportedError()
            elif order_type == OrderType.TASKING_ORDER:
                raise errors.FutureProductNotSupportedError()
            else:
                raise errors.OseoServerError(
                    "Unable to get order configuration")
        return result

    def validate_order_type(self, order_type):
        """Assert that the input order type is allowed

        Parameters
        ----------
        order_type: oseoserver.constants.OrderType
            Enumeration value

        """

        generic_config = utilities.get_generic_order_config(order_type)
        print("generic_config: {}".format(generic_config))
        if not generic_config.get("enabled", False):
            if order_type in (OrderType.PRODUCT_ORDER,
                              OrderType.MASSIVE_ORDER):
                raise errors.ProductOrderingNotSupportedError()
            elif order_type == OrderType.SUBSCRIPTION_ORDER:
                raise errors.SubscriptionNotSupportedError()
            elif order_type == OrderType.TASKING_ORDER:
                raise errors.FutureProductNotSupportedError()
            else:
                raise errors.OseoServerError("Invalid order type: "
                                             "{}".format(order_type))


    def validate_status_notification(self, request):
        """
        Check that the requested status notification is supported.

        :param request:
        :return:
        """

        if request.statusNotification != StatusNotification.NONE.value:
            raise NotImplementedError("Status notifications are "
                                      "not supported")
        return StatusNotification(request.statusNotification)

    def _get_delivery_address(self, delivery_address_type):
        address = {
            "first_name": _c(delivery_address_type.firstName),
            "last_name": _c(delivery_address_type.lastName),
            "company_ref": _c(delivery_address_type.companyRef),
            "telephone_number": _c(delivery_address_type.telephoneNumber),
            "facsimile_telephone_number": _c(
                delivery_address_type.facsimileTelephoneNumber),
        }
        postal_address = delivery_address_type.postalAddress
        if postal_address is not None:
            address["postal_address"] = {
                "street_address": _c(postal_address.streetAddress),
                "city": _c(postal_address.city),
                "state": _c(postal_address.state),
                "postal_code": _c(postal_address.postalCode),
                "country": _c(postal_address.country),
                "post_box": _c(postal_address.postBox),
                }
        return address

    def _get_order_type(self, order_specification):
        """Return the order type for the input order specification.

        Usually the order type can be extracted directly from the order
        specification, as the OSEO standard defines only PRODUCT ORDER,
        SUBSCRIPTION ORDER and TASKING ORDER. We are adding a fourth type,
        MASSIVE ORDER, which is based on the existence of a special reference
        on orders of type PRODUCT ORDER.

        Parameters
        ----------
        order_specification: oseo.Submit
            the submitted request

        Returns
        -------
        constants.OrderType
            The enumeration value for the requested order type

        """

        requested = OrderType(order_specification.orderType)
        if requested == OrderType.PRODUCT_ORDER:
            reference = _c(order_specification.orderReference)
            if reference == MASSIVE_ORDER_REFERENCE:
                requested = OrderType.MASSIVE_ORDER
        return requested

    def _validate_collection_id(self, collection_id):
        for collection_config in settings.get_collections():
            if collection_config.get("collection_identifier") == collection_id:
                result = collection_config
                break
        else:
            raise errors.InvalidParameterValueError("collectionId")
        return result

    def _validate_delivery_options(self, requested_delivery_options,
                                   order_config):
        """Validate the requested delivery options for an item.

        The input requested_item can be an order or an order item

        Parameters
        ----------
        requested_delivery_options: oseo.DeliveryOptionsType or None
            The order or order item to validate
        order_config: dict
            Configuration parameters for the requested order type and the
            current collection

        Returns
        -------
        dict
            The requested delivery options, alraedy validated

        """

        delivery = None
        dop = requested_delivery_options
        if dop is not None:
            delivery = dict()
            if dop.onlineDataAccess is not None:
                delivery["type"] = DeliveryOption.ONLINE_DATA_ACCESS
                delivery["protocol"] = DeliveryOptionProtocol(
                    dop.onlineDataAccess.protocol)
            elif dop.onlineDataDelivery is not None:
                delivery["type"] = DeliveryOption.ONLINE_DATA_DELIVERY
                delivery["protocol"] = DeliveryOptionProtocol(
                    dop.onlineDataDelivery.protocol)
            else:
                delivery["type"] = DeliveryOption.MEDIA_DELIVERY
                delivery["medium"] = dop.mediaDelivery.packageMedium
                delivery["shipping_instructions"] = (
                    dop.mediaDelivery.shippingInstructions)
            delivery["copies"] = dop.numberOfCopies or 1
            delivery["annotation"] = _c(dop.productAnnotation)
            delivery["special_instructions"] = _c(dop.specialInstructions)
        return delivery

    def _validate_global_delivery_options(self, order_specification,
                                          order_type, collections):
        """Validate global order delivery options.

        Oseoserver only accepts global options that are valid for each of the
        order items contained in the order. As such, the requested delivery
        options must be valid according to all of order configurations of the
        ordered collections.

        Parameters
        ----------
        order_specification: oseo.OrderSpecification
            The orderSpecification instance of the order being processed
        order_type: constants.OrderType
            Enumeration instance with the order type
        collections: list
            Names of the collections that are being requested throughout the
            order items of the incoming order

        Returns
        -------

        """

        delivery_options = {}
        for collection_name in collections:
            config = utilities.get_order_configuration(order_type,
                                                       collection_name)
            delivery_options.update(
                self._validate_delivery_options(
                    order_specification.deliveryOptions,
                    config
            ))
        return delivery_options

    def _validate_global_options(self, order_specification,
                                 order_type, collections):
        """Validate global order processing options.

        Oseoserver only accepts global options that are valid for each of the
        order items contained in the order. As such, the requested delivery
        options must be valid according to all of order configurations of the
        ordered collections.

        Parameters
        ----------
        order_specification: oseo.OrderSpecification
            The orderSpecification instance of the order being processed
        order_type: constants.OrderType
            Enumeration instance with the order type
        collections: list
            Names of the collections that are being requested throughout the
            order items of the incoming order

        Returns
        -------

        """

        options = {}
        for collection_name in collections:
            options.update(
                self._validate_requested_options(
                order_specification.option,
                order_type, collection_name
            ))
        return options

    def _validate_packaging(self, requested_packaging):
        packaging = _c(requested_packaging)
        choices = [c[0] for c in models.Order.PACKAGING_CHOICES]
        if packaging != "" and packaging not in choices:
            raise errors.InvalidParameterValueError("packaging")
        return packaging

    def _validate_requested_options(self, requested_options, order_type,
                                    collection_name):
        validated_options = {}
        for option in requested_options:
            values = option.ParameterData.values
            # since values is an xsd:anyType, we will not do schema
            # validation on it
            values_tree = etree.fromstring(values.toxml(ENCODING))
            for value in values_tree:
                option_name = etree.QName(value).localname
                parsed_value = utilities.validate_processing_option(
                    option_name, value, order_type, collection_name)
                validated_options[option_name] = parsed_value
        return validated_options
