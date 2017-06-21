# Copyright 2017 Ricardo Garcia Silva
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
import datetime as dt
import logging

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from lxml import etree
import pyxb.bundles.opengis.oseo_1_0 as oseo
import pytz

from .. import models
from .. import errors
from .. import utilities
from .. import settings
from ..utilities import _n, _c
from ..utilities import get_etree_parser
from ..constants import ENCODING
from ..models import CustomizableItem
from ..models import Order
from ..models import BaseDeliveryOption

logger = logging.getLogger(__name__)


def check_collection_enabled(collection_id, order_type):
    collection_settings = utilities.get_collection_settings(collection_id)
    try:
        enabled = collection_settings[order_type.lower()]["enabled"]
    except KeyError:
        enabled = False
    if not enabled:
        if order_type in (Order.PRODUCT_ORDER,
                          Order.MASSIVE_ORDER):
            raise errors.ProductOrderingNotSupportedError()
        elif order_type == Order.SUBSCRIPTION_ORDER:
            raise errors.SubscriptionNotSupportedError()
        else:  # Order.TASKING_ORDER
            raise errors.FutureProductNotSupportedError()
    else:
        return collection_settings["name"]


def check_delivery_protocol(protocol, delivery_type, order_type, collection):
    """Ensure the provided protocol is enabled in the settings.

    Parameters
    ----------
    protocol: str
        The delivery protocol being evaluated
    delivery_type: str
        The type of delivery being requested

    """

    collection_config = get_order_configuration(order_type, collection)
    config_key = {
        BaseDeliveryOption.ONLINE_DATA_ACCESS: (
            "online_data_access_options"),
        BaseDeliveryOption.ONLINE_DATA_DELIVERY: (
            "online_data_delivery_options"),
        BaseDeliveryOption.MEDIA_DELIVERY: (
            "media_delivery_options"),
    }[delivery_type]
    allowed_protocols = collection_config[config_key]
    if protocol not in allowed_protocols:
        raise errors.InvalidParameterValueError(locator="protocol")


def check_order_type_enabled(order_type):
    """Assert that the input order type is enabled in the settings

    Parameters
    ----------
    order_type: oseoserver.constants.OrderType
        Enumeration value

    """

    generic_config = utilities.get_generic_order_config(order_type)
    if not generic_config.get("enabled", False):
        logger.debug("Orders of type {0} are not enabled".format(order_type))
        if order_type in (Order.PRODUCT_ORDER,
                          Order.MASSIVE_ORDER):
            raise errors.ProductOrderingNotSupportedError()
        elif order_type == Order.SUBSCRIPTION_ORDER:
            raise errors.SubscriptionNotSupportedError()
        else:  # Order.TASKING_ORDER
            raise errors.FutureProductNotSupportedError()


def create_delivery_option(oseo_delivery, collection, order_type,
                           customizable_item):
    """Create a delivery option for an order or order item

    Parameters
    ----------
    oseo_delivery: pyxb.bundles.opengis.raw.oseo_1_0.DeliveryOptionsType
        The requested delivery options
    collection: str
        Name of the collection
    order_type: str
        Type of order
    customizable_item: models.Order or models.OrderItem
        The type of model that is to have this option created for

    """

    if oseo_delivery.mediaDelivery is not None:
        details = ", ".join((
            oseo_delivery.mediaDelivery.packageMedium,
            _c(oseo_delivery.mediaDelivery.shippingInstructions)
        ))
        delivery_type = models.BaseDeliveryOption.MEDIA_DELIVERY
    else:
        if oseo_delivery.onlineDataAccess is not None:
            details = oseo_delivery.onlineDataAccess.protocol
        else:
            details = oseo_delivery.onlineDataDelivery.protocol
        delivery_type = (
            models.BaseDeliveryOption.ONLINE_DATA_ACCESS if
            oseo_delivery.onlineDataAccess is not None else
            models.BaseDeliveryOption.ONLINE_DATA_DELIVERY
        )
        check_delivery_protocol(
            protocol=details,
            delivery_type=delivery_type,
            order_type=order_type,
            collection=collection
        )
    ModelClass = (
        models.OrderDeliveryOption if
        isinstance(customizable_item, models.Order) else
        models.ItemSpecificationDeliveryOption
    )
    delivery_option = ModelClass(
        delivery_type=delivery_type,
        annotation=_c(oseo_delivery.productAnnotation),
        copies=oseo_delivery.numberOfCopies or 1,
        special_instructions=_c(oseo_delivery.specialInstructions),
        delivery_details=details,
    )
    delivery_option.full_clean()
    return delivery_option


def create_item_specification(item, item_processor, order_type):
    """Create an order item specification.

    Parameters
    ----------
    item: pyxb.bundles.opengis.oseo_1_0.CommonOrderItemType
        The requested item specification
    item_processor: oseoserver.itemprocessor
        The custom item_processor class used to process order items

    """
    if order_type in (Order.PRODUCT_ORDER, Order.MASSIVE_ORDER):
        collection_id = (
            item.productId.collectionId or
            item_processor.get_collection_id(item.productId.identifier)
        )
        identifier = _c(item.productId.identifier)
    elif order_type == Order.SUBSCRIPTION_ORDER:
        collection_id = item.subscriptionId.collectionId
        identifier = ""
    else:  # tasking order
        raise NotImplementedError
    collection_name = check_collection_enabled(
        collection_id, order_type=order_type)
    item_specification = models.ItemSpecification(
        remark=_c(item.orderItemRemark),
        collection=collection_name,
        identifier=identifier,
        item_id=item.itemId
    )
    item_specification.full_clean()
    item_specification.save()
    for requested_option in item.option:
        values = requested_option.ParameterData.values
        # since values is an xsd:anyType, we will not do schema
        # validation on it
        values_tree = etree.fromstring(
            values.toxml(ENCODING), parser=get_etree_parser())
        for element in values_tree:
            option = create_option(
                option_element=element,
                order_type=Order.PRODUCT_ORDER,
                collection_name=collection_name,
                customizable_item=item_specification,
                item_processor=item_processor
            )
            option.save()
            item_specification.selected_options.add(option)
    if item.deliveryOptions is not None:
        item_delivery = create_delivery_option(
            oseo_delivery=item.deliveryOptions,
            collection=collection_name,
            order_type=Order.PRODUCT_ORDER,
            customizable_item=item
        )
        item_delivery.item_specification = item_specification
        item_specification.selected_delivery_option = item_delivery
        item_delivery.save()
    # scene selection options are not implemented yet
    # payment is not implemented yet
    # add extensions?
    item_specification.save()
    return item_specification


def create_option(option_element, order_type, collection_name,
                  customizable_item, item_processor):
    """Create an option for an order or order item.

    Parameters
    ----------
    option_element: lxml.etree._Element
        The option to be parsed
    order_type: str
        Type of order being requested.
    collection_name: str
        Name of the collection being requested
    customizable_item: models.Order or models.OrderItem
        The type of model that is to have this option created for
    item_processor:

    """

    option_name = etree.QName(option_element).localname
    logger.debug("Validating option {!r}...".format(option_name))
    # 1. can the option be used with current collection and order_type?
    collection_config = get_order_configuration(order_type, collection_name)
    if option_name not in collection_config.get("options", []):
        raise errors.InvalidParameterValueError(
            "option", value=option_name)
    # 2. Parse the option value using the external item_processor
    try:
        parsed_value = item_processor.parse_option(option_name, option_element)
    except AttributeError:
        raise errors.OseoServerError(
            "Incorrectly configured "
            "item_processor: {}".format(item_processor)
        )
    except IndexError:
        raise errors.InvalidParameterValueError(
            locator="option", value=option_name)
    # 3. is the parsed value legal?
    for allowed_option in settings.get_processing_options():
        if allowed_option["name"] == option_name:
            choices = allowed_option.get("choices", [])
            if parsed_value not in choices and len(choices) > 0:
                raise errors.InvalidParameterValueError(
                    "option", value=parsed_value)
            break
    else:
        raise errors.InvalidParameterValueError(
            "option", value=parsed_value)
    OptionClass = (
        models.SelectedOrderOption if isinstance(
            customizable_item, models.Order) else models.SelectedItemOption
    )
    option = OptionClass(
        option=option_name,
        value=parsed_value
    )
    option.full_clean()
    return option


def create_order_delivery_information(delivery_information):
    """Extract delivery information from a request

    Parameters
    ----------
    delivery_information: oseo.DeliveryInformationType

    Returns
    -------
    oseoserver.models.DeliveryInformation

    """

    if delivery_information.mailAddress is not None:
        address_fields = _get_delivery_address(
            delivery_information.mailAddress)
    else:
        address_fields = {}
    info = models.DeliveryInformation(
        first_name=address_fields.get("first_name", ""),
        last_name =address_fields.get("last_name", ""),
        company_ref =address_fields.get("company_ref", ""),
        street_address =address_fields.get("postal_address", {}).get(
            "street_address", ""),
        city=address_fields.get("postal_address", {}).get("city", ""),
        state=address_fields.get("postal_address", {}).get("state", ""),
        postal_code=address_fields.get("postal_address", {}).get(
            "postal_code", ""),
        country=address_fields.get("postal_address", {}).get("country", ""),
        post_box=address_fields.get("postal_address", {}).get("post_box", ""),
        telephone=address_fields.get("telephone", ""),
        fax=address_fields.get("fax", ""),
    )
    info.full_clean()
    info.save()
    if len(delivery_information.onlineAddress) > 0:
        for item in delivery_information.onlineAddress:
            online_address = models.OnlineAddress(
                delivery_information=info,
                protocol=_c(item.protocol),
                server_address=_c(item.serverAddress),
                user_name=_c(item.userName),
                user_password=_c(item.userPassword),
                path=_c(item.path)
            )
            online_address.full_clean()
            online_address.save()
    return info


def create_order_invoice_address(invoice_address):
    address_fields = _get_delivery_address(invoice_address)
    invoice = models.InvoiceAddress(
        first_name=address_fields["first_name"],
        last_name =address_fields["last_name"],
        company_ref =address_fields["company_ref"],
        street_address =address_fields["postal_address"]["street_address"],
        city=address_fields["postal_address"]["city"],
        state=address_fields["postal_address"]["state"],
        postal_code=address_fields["postal_address"]["postal_code"],
        country=address_fields["postal_address"]["country"],
        post_box=address_fields["postal_address"]["post_box"],
        telephone=address_fields["telephone"],
        fax=address_fields["fax"],
    )
    invoice.full_clean()
    return invoice


def create_order_item(status, item_id, collection,
                      additional_status_info="",
                      option=None, scene_selection=None,
                      order_item_remark="",
                      identifier=None, payment=None):
    """Create order items for a batch.

    Parameters
    ----------
    status: str
        OSEO status for the item to be created
    item_id: str
    collection: str
        Collection where the ordered content belongs
    additional_status_info: str, optional
        Further details concerninc the status
    option: dict, optional
        A mapping with options to be added to the order item
    scene_selection: dict, optional
        A mapping with scene selection options to be added to the
        order item
    order_item_remark: str, optional
        Further comments regarding the item
    identifier: str, optional
    payment: str, optional
        Payment metho for the item

    """

    item = models.OrderItem(
        status=status,
        additional_status_info=additional_status_info,
        remark=order_item_remark,
        collection=collection,
        identifier=identifier or "",
        item_id=item_id
    )
    item.full_clean()
    item.save()
    item_options = option or {}
    for name, value in item_options.items():
        # assuming that the option has already been validated
        selected_option = models.SelectedOption(
            option=name,
            value=value,
            customizable_item=item
        )
        selected_option.full_clean()
        selected_option.save()
    scene_selection_options = scene_selection or {}
    for name, value in scene_selection_options.items():
        scene_option = models.SelectedSceneSelectionOption(
            option=name,
            value=value,
            customizable_item=item
        )
        scene_option.full_clean()
        scene_option.save()
    if payment is not None:
        payment = models.SelectedPaymentOption(
            order_item=item,
            option=payment
        )
        payment.full_clean()
        payment.save()
    item.save()
    return item


def get_order_initial_status(order_type):
    initial_status = _get_initial_status(order_type)
    additional_status_info = {
        CustomizableItem.ACCEPTED: "Order has been placed in processing queue",
        CustomizableItem.SUBMITTED: "Order is awaiting approval",
    }.get(initial_status, "Order has been rejected")
    return initial_status, additional_status_info


def get_order_item_initial_status(order_type):
    initial_status = _get_initial_status(order_type)
    additional_status_info = {
        CustomizableItem.ACCEPTED: "Item has been placed in processing queue",
        CustomizableItem.SUBMITTED: "Order is awaiting approval",
    }.get(initial_status,
          "The Order has been rejected, item won't be processed")
    return initial_status, additional_status_info


def get_order_configuration(order_type, collection):
    """Get the configuration for the input order type and collection.

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
        type_specific_config = collection_config.get(
            order_type.lower(), {})
        is_enabled = type_specific_config.get("enabled", False)
        if is_collection and is_enabled:
            result = type_specific_config
            break
    else:
        if order_type in (Order.PRODUCT_ORDER, Order.MASSIVE_ORDER):
            raise errors.ProductOrderingNotSupportedError()
        elif order_type == Order.SUBSCRIPTION_ORDER:
            raise errors.SubscriptionNotSupportedError()
        elif order_type == Order.TASKING_ORDER:
            raise errors.FutureProductNotSupportedError()
        else:
            raise errors.OseoServerError(
                "Unable to get order configuration")
    return result


def get_order_type(order_specification):
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
    str
        The requested order type

    """

    # no need to validate value of orderType because pyxb has already done that
    order_type = order_specification.orderType
    if order_type == Order.PRODUCT_ORDER:
        reference = _c(order_specification.orderReference)
        if reference == Order.MASSIVE_ORDER_REFERENCE:
            order_type = Order.MASSIVE_ORDER
    return order_type


def process_request_order_specification(order_specification, user,
                                        status_notification):
    """Process an order specification.

    This function is responsible for parsing the input
    ``order_specification`` into a database record and then returning an
    OSEO response to signal that the request has been handled. Further order
    processing is done elsewhere:

    * Order dispatching code is in ``models.Order``
    * Order processing code is in ``tasks.py``

    Parameters
    ----------
    order_specification: oseo.OrderSpecification
        The specification for the order
    user: django.contrib.auth.models.User
        The django user instance associated with the order
    status_notification: str
        The order status notification

    Returns
    -------
    oseo.Ack
        Response to a successfull oseo:Submit order request
    models.Order
        The django instance of the newly created order

    """

    order_type = get_order_type(order_specification)
    logger.debug("Processing specification for {0!r}".format(order_type))
    check_order_type_enabled(order_type)
    if order_specification.packaging is not None:
        logger.critical("Packaging is not implemented")
        raise errors.NoApplicableCodeError()
    order = models.Order(
        status=Order.SUBMITTED,
        additional_status_info="Order is awaiting approval",
        mission_specific_status_info="",  # not implemented yet
        remark=_c(order_specification.orderRemark),
        user=user,
        order_type=order_type,
        reference=_c(order_specification.orderReference),
        packaging=_c(order_specification.packaging),
        priority=_c(order_specification.priority) or models.Order.STANDARD,
        status_notification=status_notification
    )
    order.full_clean()
    order.save()
    logger.debug("Validated general order parameters")
    if order_type == Order.MASSIVE_ORDER and len(
            order_specification.orderItem) > 1:
        raise RuntimeError("Orders of type {!r} must specify a single "
                           "order item".format(order_type))
    if order_specification.deliveryInformation is not None:
        delivery_information = create_order_delivery_information(
            order_specification.deliveryInformation)
        delivery_information.order = order
        delivery_information.save()
    logger.debug("Extracted order delivery information")
    if order_specification.invoiceAddress is not None:
        order.invoice_address = create_order_invoice_address(
            order_specification.invoiceAddress)
    logger.debug("Extracted order invoice address")
    for extension in order_specification.extension:
        models.Extension.objects.create(order=order, text=extension)
    logger.debug("Extracted order extensions")
    item_processor = utilities.get_item_processor(order_type)
    requested_collections = set()
    for oseo_item in order_specification.orderItem:
        item_specification = create_item_specification(
            item=oseo_item,
            item_processor=item_processor,
            order_type=order_type
        )
        order.item_specifications.add(item_specification)
        requested_collections.add(item_specification.collection)
    if order_specification.deliveryOptions is not None:
        for collection in requested_collections:
            delivery_option = create_delivery_option(
                oseo_delivery=order_specification.deliveryOptions,
                collection=collection,
                order_type=order_type,
                customizable_item=order
            )
            try:
                order.selected_delivery_option
            except ObjectDoesNotExist:
                delivery_option.order = order
                delivery_option.save()
                order.selected_delivery_option = delivery_option
                order.save()
                break
    logger.debug("Extracted order delivery options")
    # order options are processed last because we need to know the order
    # items first
    validate_order_delivery_options(order)
    logger.debug("Validated delivery options for order and items")
    for requested_option in order_specification.option:
        values = requested_option.ParameterData.values
        # since values is an xsd:anyType, we will not do schema
        # validation on it
        values_element = etree.fromstring(
            values.toxml(ENCODING), parser=get_etree_parser())
        for element in values_element:
            for collection in requested_collections:
                option = create_option(
                    option_element=element,
                    order_type=order_type,
                    collection_name=collection,
                    customizable_item=order,
                    item_processor=item_processor
                )
                option.save()
                order.selected_options.add(option)
    logger.debug("Extracted order options")
    validate_order_type_specific_constraints(order)
    order.full_clean()
    validate_order_size(order, item_processor)
    logger.debug("Validated order size")
    order.save()
    logger.debug("Saved order specification in the database")
    # create oseo response and return it
    response = oseo.SubmitAck(
        status="success",
        orderId=str(order.id),
        orderReference=_n(order.reference)
    )
    return response, order


def process_request_quotation_id():
    raise NotImplementedError


@transaction.atomic
def submit(request, user):
    """OSEO Submit handler.

    Parameters
    ----------
    request: pyxb.bundles.opengis.oseo_1_0.Submit
        The request to process
    user: django.contrib.auth.models.User
        USer that has placed the request

    Returns
    -------
    response: pyxb.bundles.opengis.oseo_1_0.SubmitAck
        OSEO response to be sent to the client
    order: models.Order
        Order instance

    """

    if request.statusNotification != Order.NONE:
        raise NotImplementedError("Status notifications are not supported")
    if request.orderSpecification:
        response, order = process_request_order_specification(
            request.orderSpecification, user, request.statusNotification)
    else:
        response, order = process_request_quotation_id()
    return response, order


def validate_order_size(order, item_processor):
    item_count = _get_order_item_count(order, item_processor)
    _validate_order_number_of_items(
        order_items=item_count, order_type=order.order_type)
    _validate_active_order_items(
        order_type=order.order_type,
        order_items=item_count,
        user=order.user
    )


def validate_order_delivery_options(order):
    """Assert that an order has delivery options for all of its items.

    The OSEO standard states that an order may have delivery options set at
    the order level or at the item level. either way, a delivery specification
    must always be present.

    Raises
    ------
    models.ItemSpecificationDeliveryOption.DoesNotExist
        If an order item does not have any delivery options defined at the item
        level nor at the order level

    """

    try:
        order.selected_delivery_option
    except models.OrderDeliveryOption.DoesNotExist:
        logger.warning(
            "Order {!r} does not specify any delivery options. Inspecting "
            "individual item specifications...".format(order)
        )
        for item_specification in order.item_specifications.all():
            try:
                item_specification.selected_delivery_option
            except models.ItemSpecificationDeliveryOption.DoesNotExist:
                logger.error(
                    "Item {!r} does not specify delivery options. Cannot "
                    "deliver such an item".format(item_specification)
                )
                raise


def validate_order_type_specific_constraints(order):
    if order.order_type == Order.SUBSCRIPTION_ORDER:
        _validate_subscription_date_range(order)
        _validate_subscription_items(order)


def _create_default_date_range_option(date_range_name, item_processor):
    start = dt.datetime.now(pytz.utc)
    end = start + dt.timedelta(days=365)
    option_element = etree.Element(date_range_name)
    option_element.text = " ".join((
        start.isoformat(),
        end.isoformat()
    ))
    option_value = item_processor.parse_option(
        name=date_range_name,
        value=option_element
    )
    return models.SelectedOrderOption(
        option=date_range_name,
        value=option_value
    )


def _get_delivery_address(delivery_address_type):
    address = {
        "first_name": _c(delivery_address_type.firstName),
        "last_name": _c(delivery_address_type.lastName),
        "company_ref": _c(delivery_address_type.companyRef),
        "telephone": _c(delivery_address_type.telephoneNumber),
        "fax": _c(delivery_address_type.facsimileTelephoneNumber),
        "postal_address": {
            "street_address": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "country": "",
            "post_box": "",
        }
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


def _get_initial_status(order_type):
    general_order_config_getter = getattr(
        settings,
        "get_{order_type}".format(order_type=order_type.lower())
    )
    order_config = general_order_config_getter()
    if order_config.get("enabled", False):
        if order_config.get("automatic_approval", False):
            status = CustomizableItem.ACCEPTED
        else:
            status = CustomizableItem.SUBMITTED
    else:
        status = CustomizableItem.CANCELLED
    return status


def _get_order_item_count(order, item_processor):
    if order.order_type in (Order.PRODUCT_ORDER, Order.SUBSCRIPTION_ORDER):
        item_count = len(order.item_specifications.all())
    elif order.order_type == Order.MASSIVE_ORDER:
        item_count = 0
        for item_specification in order.item_specifications.all():
            collection = item_specification.collection
            start, end = item_processor.get_order_duration(
                item_specification)
            ids = item_processor.get_massive_order_batch_item_identifiers(
                    batch_index=0,
                    collection=collection,
                    start=start,
                    end=end,
                    items_per_batch=settings.get_max_order_items()
                )
            item_count += len(ids)
    else:
        raise NotImplementedError
    return item_count


def _validate_active_order_items(order_type, order_items, user):
    MAXIMUM_ACTIVE_ITEMS = settings.get_max_active_items()
    user_items = models.OrderItem.objects.filter(
        batch__order__user=user
    ).filter(status=CustomizableItem.IN_PRODUCTION).count()
    if (user_items + order_items) > MAXIMUM_ACTIVE_ITEMS:
        error_msg = (
            "User {0.username!r} has too many active order items. Refusing "
            "to accept order at this moment. Try again later".format(user))
        logger.error(error_msg)
        raise errors.NoApplicableCodeError()


def _validate_order_number_of_items(order_items, order_type):
    if order_type == Order.MASSIVE_ORDER:
        MAX_ORDER_ITEMS = settings.get_massive_order_max_size()
    else:
        MAX_ORDER_ITEMS = settings.get_max_order_items()
    if order_items > MAX_ORDER_ITEMS:
        error_msg = (
            "Each order may not request a number of individual items greater "
            "than {}. Either split the request into smaller orders or perform "
            "an order of type {!r}.".format(
                MAX_ORDER_ITEMS, Order.MASSIVE_ORDER)
        )
        logger.error(error_msg)
        raise errors.NoApplicableCodeError


def _validate_subscription_date_range(order):
    """Be sure that the input subscription order has a date range"""
    date_range_name = "DateRange"
    for item_specification in order.item_specifications.all():
        date_range = item_specification.get_option(date_range_name)
        if date_range is None:
            logger.warning(
                "There is at least one item specification without a "
                "{!r} option. Setting a default option in the "
                "order".format(date_range_name)
            )
            default_date_range = _create_default_date_range_option(
                date_range_name=date_range_name,
                item_processor=utilities.get_item_processor(
                    order.order_type)
            )
            default_date_range.order = order
            default_date_range.save()
            break


def _validate_subscription_items(order):
    """Be sure that there is only one order item in the order request.
    
    Currently we do not support more than one item in the request for 
    subscription orders.
    
    """
    item_spec_count = order.item_specifications.count()
    if item_spec_count != 1:
        logger.error(
            "Subscription orders cannot have more than 1 item specification. "
            "Order {!r} has {}".format(order, item_spec_count)
        )
        raise errors.NoApplicableCodeError()
