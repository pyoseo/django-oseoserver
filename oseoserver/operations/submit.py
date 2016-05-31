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
                self.validate_order_item(order_item, order_type, user)
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

    def get_collection_id(self, item_id):
        """Determine the collection identifier for the specified item.

        This method is used when the requested order item does not provide the
        optional 'collectionId' element. It searched all of the defined
        catalogue endpoints and determines the collection for the
        specified item.

        Parameters
        ----------
        item_id: str
            The identifier of the requested order item

        Returns
        -------

        """

        request_headers = {"Content-Type": "application/xml"}
        ns = {"gmd": gmd.Namespace.uri(), "gco": gco.Namespace.uri(),}
        req = csw.GetRecordById(
            service="CSW",
            version="2.0.2",
            ElementSetName="summary",
            outputSchema=ns["gmd"],
            Id=[BIND(item_id)]
        )
        query_path = ("gmd:MD_Metadata/gmd:parentIdentifier/"
                      "gco:CharacterString/text()")
        for collection in settings.OSEOSERVER_COLLECTIONS:
            response = requests.post(
                collection["catalogue_endpoint"],
                data=req.toxml(),
                headers=request_headers
            )
            if response.status_code == 200:
                r = etree.fromstring(response.text.encode(OseoServer.ENCODING))
                id_container = r.xpath(query_path, namespaces=ns)
                if any(id_container):
                    collection_id = id_container[0]
                    break
        else:
            raise errors.OseoServerError("Could not retrieve collection "
                                         "id for item {!r}".format(item_id))
        return collection_id

    def validate_order_item(self, requested_item, order_type, user):
        """Validate an order item.

        Parameters
        ----------
        requested_item: pyxb.bundles.opengis.oseo_1_0.Order
            The requested order item
        order_type: oseoserver.constants.OrderType
            The enumeration value of the requested order type
        user: django.contrib.auth.User
            The django user that made the request

        Returns
        -------

        """

        item = {
            "item_id": requested_item.itemId,
            "product_order_options_id": _c(
                requested_item.productOrderOptionsId),
            "order_item_remark": _c(requested_item.orderItemRemark)
        }
        if order_type in (OrderType.PRODUCT_ORDER, OrderType.MASSIVE_ORDER):
            identifier, collection = self._validate_product_order_item(
                requested_item, user)
            item["identifier"] = identifier
        elif order_type == OrderType.SUBSCRIPTION_ORDER:
            collection = self._validate_subscription_order_item(
                requested_item, user)
        else:  # TASKING_ORDER
            tasking_id, collection = self._validate_tasking_order_item(
                requested_item, user)
            item["tasking_id"] = tasking_id
        item["collection"] = collection
        order_config = self._get_order_configuration(collection, order_type)
        generic_order_config = utilities.get_generic_order_config(order_type)
        item["option"] = self._validate_requested_options(
            requested_item,
            generic_order_config,
            order_config
        )
        item["delivery_options"] = self._validate_delivery_options(
            requested_item, order_config)
        item["scene_selection"] = dict()  # not implemented yet
        item["payment"] = None  # not implemented yet
        # extensions to the CommonOrderItemType are not implemented yet
        return item

    def _validate_product_order_item(self, requested_item, user):
        identifier = _c(requested_item.productId.identifier)
        col_id = requested_item.productId.collectionId
        if col_id is None:
            col_id = self.get_collection_id(identifier)
        collection = self._validate_collection_id(col_id,
                                                  user.oseo_group)
        return identifier, collection

    def _validate_subscription_order_item(self, requested_item, user):
        col_id = requested_item.subscriptionId.collectionId
        collection = self._validate_collection_id(col_id,
                                                  user.oseo_group)
        return collection

    def _validate_tasking_order_item(self, requested_item, user):
        tasking_id = requested_item.taskingRequestId
        # TODO: find a way to retrieve the collection
        # TODO: validate the tasking_id
        collection = None
        return tasking_id, collection

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

        for collection_config in settings.OSEOSERVER_COLLECTIONS:
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

    def _validate_collection_id(self, collection_id):
        for collection_config in settings.OSEOSERVER_COLLECTIONS:
            if collection_config.get("collection_identifier") == collection_id:
                result = collection_config
                break
        else:
            raise errors.InvalidParameterValueError("collectionId")
        return result

    def _validate_requested_options(self, requested_item,
                                    generic_order_configuration,
                                    order_config):
        """

        Parameters
        ----------
        requested_item:
            The requested item
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
        for option in requested_item.option:
            values = option.ParameterData.values
            encoding = option.ParameterData.encoding
            # since values is an xsd:anyType, we will not do schema
            # validation on it
            values_tree = etree.fromstring(values.toxml(OseoServer.ENCODING))
            for value in values_tree:
                option_name = etree.QName(value).localname
                option_value = self._validate_selected_option(
                    option_name, value, generic_order_configuration,
                    order_config
                )
                option_model = order_config.options.get(name=option_name)
                if option_model.multiple_entries:
                    if valid_options.has_key(option_name):
                        valid_options[option_name] = " ".join(
                            (valid_options[option_name], option_value))
                    else:
                        valid_options[option_name] = option_value
                else:
                    valid_options[option_name] = option_value
        return valid_options

    def _validate_global_options(self, requested_order_spec,
                                 order_type,
                                 ordered_order_configs):
        for order_config in ordered_order_configs:
            options = self._validate_requested_options(requested_order_spec,
                                                       order_type,
                                                       order_config)
        return options

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

        """

        # * first we check if the provided option name is legal, according
        #   to the order_config settings
        # * next we check if the provided option value is legal:
        #   we try to parse it using the item processor specified in the
        #   generic_order_configuration settings and after that we try to
        #   check if the parsed value is legal according to the
        #   OSEOSERVER_OPTIONS settings

        if name in order_config.get("options", []):
            try:
                class_path = generic_order_configuration.get("item_processor",
                                                             None)
                item_processor = utilities.import_class(class_path)
                item_processor.parse
            except AttributeError:
                raise errors.OseoServerError(
                    "Incorrectly configured "
                    "item_processor: {}".format(class_path)
                )
            pass  # the option name is legal
        else:
            raise errors.InvalidParameterValueError(locator="option",
                                                    value=name)


        try:
            option_config = [opt for opt in settings.OSEOSERVER_OPTIONS
                             if opt["name"] == name][0]
            if name not in order_config["options"]:
                raise errors.InvalidParameterValueError(locator="option",
                                                        value=name)
            choices = option_config.get("choices", [])
            if len(choices) > 0:
                if value.text in choices:
                    result = value.text
                else:
                    handler = utilities.import_class(ProcessingClass)
                    parsed_value = handler.parse_option(name, value)
                    if parsed_value in choices:
                        result = parsed_value
                    else:
                        raise errors.InvalidParameterValueError(
                            "option", value=parsed_value)
            else:
                handler = utilities.import_class(ProcessingClass)
                result = handler.parse_option(name, value)
        except KeyError:
            raise errors.InvalidParameterValueError(locator="option",
                                                    value=name)
        except Exception as e:
            logger.error(e)
            raise errors.ServerError(*e.args)
        return result

    def _validate_delivery_options(self, requested_item, order_config):
        """Validate the requested delivery options for an item.

        The input requested_item can be an order or an order item

        Parameters
        ----------
        requested_item: oseo.OrderSpecification
            The order or order item to validate
        order_config: dict
            A configuration dictionary that holds information on the types
            of orders accepted

        Returns
        -------
        dict
            The requested delivery options, alraedy validated

        Raises
        ------
        oseoserver.errors.InvalidParameterValueError
            When some parameter has an invalid value

        """

        delivery = None
        dop = requested_item.deliveryOptions
        if dop is not None:
            delivery = dict()
            try:
                if dop.onlineDataAccess is not None:
                    protocol = dop.onlineDataAccess.protocol
                    delivery["type"] = order_config.delivery_options.get(
                        onlinedataaccess__protocol=protocol)
                    delivery["type"] = DeliveryOption.ONLINE_DATA_ACCESS
                elif dop.onlineDataDelivery is not None:
                    protocol = dop.onlineDataAccess.protocol
                    delivery["type"] = order_config.delivery_options.get(
                        onlinedatadelivery__protocol=protocol)
                else:
                    protocol = dop.mediaDelivery.packageMedium,
                    s = dop.mediaDelivery.shippingInstructions,
                    delivery["type"] = order_config.delivery_options.get(
                        mediadelivery__package_medium=protocol,
                        mediadelivery__shipping_instructions=s)
            except models.DeliveryOption.DoesNotExist:
                raise errors.InvalidParameterValueError("deliveryOptions")
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


    def validate_order_type(self, order_type):
        """Assert that the input order type is allowed

        Parameters
        ----------
        order_type: oseoserver.constants.OrderType
            Enumeration value

        """

        generic_config = utilities.get_generic_order_config(order_type)
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

    def _validate_packaging(self, requested_packaging):
        packaging = _c(requested_packaging)
        choices = [c[0] for c in models.Order.PACKAGING_CHOICES]
        if packaging != "" and packaging not in choices:
            raise errors.InvalidParameterValueError("packaging")
        return packaging
