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
from datetime import datetime, timedelta
import pytz

from django.db import transaction
from pyxb import BIND
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pyxb.bundles.opengis.csw_2_0_2 as csw
import pyxb.bundles.opengis.iso19139.v20070417.gmd as gmd
import pyxb.bundles.opengis.iso19139.v20070417.gco as gco
from lxml import etree
import requests

from .. import models
from .. import errors
from .. import utilities
from .. import settings
from ..utilities import _n, _c
from ..server import OseoServer
from ..constants import ENCODING
from ..constants import DeliveryOption
from ..constants import OrderType
from ..constants import MASSIVE_ORDER_REFERENCE
from ..constants import StatusNotification
from .base import OseoOperation

logger = logging.getLogger(__name__)


class Submit(OseoOperation):

    @transaction.atomic
    def __call__(self, request, user):
        """Implements the OSEO Submit operation.

        :arg request: The instance with the request parameters
        :type request: pyxb.bundles.opengis.raw.oseo.GetStatusRequestType
        :arg user: User making the request
        :type user: oseoserver.models.OseoUser
        :return: The XML response object
        :rtype: str
        """

        status_notification = self.validate_status_notification(request)
        if request.orderSpecification is not None:
            requested_spec = request.orderSpecification
            if len(requested_spec.orderItem) > models.Order.MAX_ORDER_ITEMS:
                raise errors.OseoError("NoApplicableCode",
                                       "Code not applicable")
            order_spec = self.process_order_specification(
                request.orderSpecification, user)
        else:
            raise errors.ServerError("Submit with quotationId is not "
                                     "implemented")
        # TODO - raise an error if there are no delivery options on the
        # order_specification either at the order or order item levels
        default_status = models.Order.SUBMITTED
        additional_status_info = ("Order is awaiting approval")
        item_additional_status_info = ""
        if order_spec["order_type"].automatic_approval:
            default_status = models.Order.ACCEPTED
            additional_status_info = ("Order is placed in processing queue")
            item_additional_status_info = ("Order item has been placed in the "
                                           "processing queue")
        order = self.create_order(order_spec, user, status_notification,
                                  default_status, additional_status_info,
                                  item_additional_status_info)
        response = oseo.SubmitAck(status='success')
        response.orderId = str(order.id)
        response.orderReference = _n(order.reference)
        return response, order

    def create_order(self, order_spec, user, status_notification, status,
                     additional_status_info, item_additional_status_info=""):
        """Persist the order specification in the database.

        :param order_spec:
        :param user:
        :param status_notification:
        :param status:
        :return:
        """

        general_params = {
            "order_type": order_spec["order_type"],
            "status": status,
            "additional_status_info": additional_status_info,
            "remark": order_spec["order_remark"],
            "user": user,
            "reference": order_spec["order_reference"],
            "packaging": order_spec["packaging"],
            "priority": order_spec["priority"],
            "status_notification": status_notification,
        }
        if order_spec["order_type"].name == models.Order.PRODUCT_ORDER:
            order = models.ProductOrder(**general_params)
        elif order_spec["order_type"].name == models.Order.MASSIVE_ORDER:
            order = models.MassiveOrder(**general_params)
        elif order_spec["order_type"].name == models.Order.SUBSCRIPTION_ORDER:
            order = models.SubscriptionOrder(**general_params)
            processor, params = utilities.get_processor(
                order.order_type,
                models.ItemProcessor.PROCESSING_PROCESS_ITEM,
                logger_type="pyoseo"
            )
            begin, end = processor.get_subscription_duration(order_spec)
            now = datetime.now(pytz.utc)
            order.begin_on = begin or now
            order.end_on = end or now + timedelta(days=365 * 10)  # ten years
        else:
            order = models.TaskingOrder(**general_params)
        order.save()
        if order_spec["invoice_address"] is not None:
            invoice = models.InvoiceAddress()
            order.invoice_address = invoice
        # TODO Implement the code for when orders do have invoice address
        if order_spec["delivery_information"] is not None:
            delivery_info = models.DeliveryInformation()
            order.delivery_information = delivery_info
        # TODO Implement the code for when orders do have delivery information
        for k, v in order_spec["option"].iteritems():
            option = models.Option.objects.get(name=k)
            order.selected_options.add(models.SelectedOption(option=option,
                                                             value=v))
        delivery = order_spec["delivery_options"]
        if delivery is not None:
            copies = 1 if delivery["copies"] is None else delivery["copies"]
            sdo = models.SelectedDeliveryOption(
                customizable_item=order,
                annotation=delivery["annotation"],
                copies=copies,
                special_instructions=delivery["special_instructions"],
                option=delivery["type"]
            )
            sdo.save()
        order.save()
        batch = order.create_batch(
            order.status,
            item_additional_status_info,
            *order_spec["order_item"]
        )
        for ext in order_spec["extension"]:
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
                        "protocol": _c(online_address.protocol),
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

    def process_order_specification(self, order_specification, user):
        """Validate and extract the order specification from the request

        Parameters
        ----------
        order_specification: pyxb.Order
            The input order specification
        user: django.contrib.auth.User
            The django user that made the request

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
        spec["requested_order_configurations"] = []
        for collection in set([i["collection"] for i in spec["order_item"]]):
            order_config = self._get_order_configuration(
                collection, order_type)
            spec["requested_order_configurations"].append(order_config)
        spec["order_reference"] = _c(order_specification.orderReference)
        spec["order_remark"] = _c(order_specification.orderRemark)
        spec["packaging"] = self._validate_packaging(
            order_specification.packaging)
        spec["priority"] = _c(order_specification.priority)
        spec["delivery_information"] = self.get_delivery_information(
            order_specification.deliveryInformation)
        spec["invoice_address"] = self.get_invoice_address(
            order_specification.invoiceAddress)
        spec["option"] = self._validate_global_options(
            order_specification,
            order_type,
            spec["requested_order_configurations"]
        )
        spec["delivery_options"] = self._validate_global_delivery_options(
            order_specification, spec["requested_order_configurations"])
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
            generic_order_config,
            specific_order_config
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
        return request.statusNotification

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

    def _get_order_configuration(self, collection, order_type):
        """Get the configuration for the requested order type and collection.

        Parameters
        ----------
        collection: str
            The requested collection
        order_type: oseoserver.constants.OrderType
            The requested order type

        Returns
        -------
        dict
            A dictionary with the configuration of the requested collection

        """
        for collection_config in settings.get_collections():
            is_collection = collection_config.get("name") == collection
            is_enabled = collection_config.get(order_type.value.lower(),
                                               {}).get("enabled", False)
            if is_collection and is_enabled:
                result = collection_config
                break
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
                delivery["protocol"] = dop.onlineDataAccess.protocol
            elif dop.onlineDataDelivery is not None:
                delivery["type"] = DeliveryOption.ONLINE_DATA_DELIVERY
                delivery["protocol"] = dop.onlineDataDelivery.protocol
            else:
                delivery["type"] = DeliveryOption.MEDIA_DELIVERY
                delivery["medium"] = dop.mediaDelivery.packageMedium
                delivery["shipping_instructions"] = (
                    dop.mediaDelivery.shippingInstructions)
            copies = dop.numberOfCopies
            delivery["copies"] = int(copies) if copies is not None else copies
            delivery["annotation"] = _c(dop.productAnnotation)
            delivery["special_instructions"] = _c(dop.specialInstructions)
        return delivery

    def _validate_global_delivery_options(self, requested_order_spec,
                                          ordered_order_configs):
        """Validate global order delivery options.

        Oseoserver only accepts global options that are valid for each of the
        order items contained in the order. As such, the requested delivery
        options must be valid according to all of order configurations of the
        ordered collections.

        :param requested_order_spec:
        :param ordered_order_configs:
        :return:
        """

        for order_config in ordered_order_configs:
            delivery_options = self._validate_delivery_options(
                requested_order_spec, order_config)
        return delivery_options

    def _validate_global_options(self, requested_order_spec,
                                 order_type,
                                 ordered_order_configs):
        for order_config in ordered_order_configs:
            options = self._validate_requested_options(requested_order_spec,
                                                       order_type,
                                                       order_config)
        return options

    def _validate_packaging(self, requested_packaging):
        packaging = _c(requested_packaging)
        choices = [c[0] for c in models.Order.PACKAGING_CHOICES]
        if packaging != "" and packaging not in choices:
            raise errors.InvalidParameterValueError("packaging")
        return packaging

    def _validate_requested_options(self, requested_options,
                                    generic_order_configuration,
                                    order_config):
        """

        Parameters
        ----------
        requested_options:
            The requested item's processing options
        generic_order_configuration: dict
            The general configuration parameters of the requested order type
        order_config: dict
            Configuration parameters for the requested order type and the
            current collection

        Returns
        -------
        dict
            The validated options

        """

        valid_options = dict()
        for option in requested_options:
            values = option.ParameterData.values
            encoding = option.ParameterData.encoding
            # since values is an xsd:anyType, we will not do schema
            # validation on it
            values_tree = etree.fromstring(values.toxml(ENCODING))
            for value in values_tree:
                option_name = etree.QName(value).localname
                option_value = self._validate_selected_option(
                    option_name, value, generic_order_configuration,
                    order_config
                )
                option_config = utilities.get_option_configuration(option_name)
                if option_config.get("multiple_entries", False):
                    if valid_options.has_key(option_name):
                        valid_options[option_name] = " ".join(
                            (valid_options[option_name], option_value))
                    else:
                        valid_options[option_name] = option_value
                else:
                    valid_options[option_name] = option_value
        return valid_options

    def _validate_selected_option(self, name, value,
                                  generic_order_configuration, order_config):
        """Validate a selected option choice.

        The validation process first tries to extract the option's value as
        a simple text and matches it with the available choices for the
        option. If a match cannot be made, the collection's custom processing
        class is instantiated and used to parse the option into a text based
        format. This parsed value is again matched against the available
        choices.

        Parameters
        ----------
        name: str
            The name of the option
        value: lxml.etree.Element
            The XML element with the custom schema
        generic_order_configuration: dict
            The general configuration parameters of the requested order type
        order_config: dict
            Configuration parameters for the requested order type and the
            current collection

        Returns
        -------
        str
            The validated option value

        """

        if name in order_config.get("options", []):
            parsed_value = value
            class_path = generic_order_configuration.get("item_processor",
                                                         None)
            try:
                item_processor = utilities.import_class(class_path)
                parsed_value = item_processor.parse_option(name, value)
                utilities.validate_processing_option(name, parsed_value)
            except AttributeError:
                raise errors.OseoServerError(
                    "Incorrectly configured "
                    "item_processor: {}".format(class_path)
                )
            except ValueError:
                raise errors.InvalidParameterValueError("option",
                                                        value=parsed_value)
        else:
            raise errors.InvalidParameterValueError(locator="option",
                                                    value=name)
        return parsed_value
