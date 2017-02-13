"""Unit tests for oseoserver.operations.submit"""

from lxml import etree
import mock
import pytest
from pyxb import BIND
from pyxb.bundles.opengis import oseo_1_0 as oseo

from oseoserver import errors
from oseoserver.operations import submit
from oseoserver import models
from oseoserver.models import Order
from oseoserver.models import CustomizableItem
from oseoserver.models import SelectedDeliveryOption
from oseoserver.utilities import _c

pytestmark = pytest.mark.unit

@pytest.mark.xfail(raises=NotImplementedError)
def test_create_order_item():
    raise NotImplementedError


@pytest.mark.xfail(raises=NotImplementedError)
def test_process_request_order_specification():
    order_spec = oseo.OrderSpecification(
        orderType="PRODUCT_ORDER",
        orderItem=[
            oseo.CommonOrderItemType(
                itemId="my_id",
                productId=oseo.ProductIdType(identifier="my_identifier")
            )
        ]
    )
    raise NotImplementedError


@pytest.mark.django_db
@pytest.mark.parametrize("status_notification", [
    "All",
    "Final",
])
def test_submit_invalid_status_notification(status_notification):
    request = oseo.Submit(
        service="OS",
        version="1.0.0",
        statusNotification=status_notification,
        orderSpecification=oseo.OrderSpecification(
            orderType="PRODUCT_ORDER",
            orderItem=[
                oseo.CommonOrderItemType(
                    itemId="my_id",
                    productId=oseo.ProductIdType(identifier="my_identifier")
                )
            ]
        )
    )
    with pytest.raises(NotImplementedError):
        submit.submit(request, "fake_user")


@pytest.mark.django_db
def test_submit_quotation_id():
    request = oseo.Submit(
        service="OS",
        version="1.0.0",
        statusNotification="None",
        quotationId="1"
    )
    with pytest.raises(NotImplementedError):
        submit.submit(request, "fake_user")


@pytest.mark.django_db
@pytest.mark.parametrize("protocol", [
    "sftp",
    "ftp"
])
def test_create_order_delivery_information(protocol):
    host = "somehost.com"
    user = "john"
    password = "123"
    path = "/my_path/here"
    delivery_info = oseo.DeliveryInformationType(
        mailAddress=None,
        onlineAddress=[
            oseo.OnlineAddressType(
                protocol=protocol,
                serverAddress=host,
                userName=user,
                userPassword=password,
                path=path
            )
        ]
    )
    result = submit.create_order_delivery_information(delivery_info)
    assert isinstance(result, models.DeliveryInformation)


def test_create_order_invoice_address():
    address_fields = {
        "first_name": "phony first",
        "last_name": "phony last",
        "company_ref": "phony company ref",
        "postal_address": {
            "street_address": "fake street",
            "city": "fake city",
            "state": "fake state",
            "postal_code": "fake postal code",
            "country": "fake country",
            "post_box": "fake post box",
        },
        "telephone": "phony telephone",
        "fax": "phony fax",
    }
    with mock.patch.object(submit,
                           "_get_delivery_address") as mock_get_address:
        mock_get_address.return_value = address_fields
        result = submit.create_order_invoice_address("some_fake_stuff")
        assert isinstance(result, models.InvoiceAddress)
        assert result.first_name == address_fields["first_name"]
        assert result.last_name == address_fields["last_name"]
        assert result.company_ref == address_fields["company_ref"]
        assert result.street_address == address_fields["postal_address"][
            "street_address"]
        assert result.city == address_fields["postal_address"]["city"]
        assert result.state == address_fields["postal_address"]["state"]
        assert result.postal_code == address_fields["postal_address"][
            "postal_code"]
        assert result.country == address_fields["postal_address"]["country"]
        assert result.post_box == address_fields["postal_address"]["post_box"]
        assert result.telephone == address_fields["telephone"]
        assert result.fax == address_fields["fax"]


@pytest.mark.parametrize("order_type", [
    Order.PRODUCT_ORDER,
    Order.MASSIVE_ORDER,
    Order.SUBSCRIPTION_ORDER,
    Order.TASKING_ORDER,
])
def test_check_order_type_enabled(settings, order_type):
    setattr(settings, "OSEOSERVER_{0}".format(order_type), {
        "enabled": True
    })
    submit.check_order_type_enabled(order_type)


@pytest.mark.parametrize("order_type, expected_exception", [
    (Order.PRODUCT_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.MASSIVE_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.SUBSCRIPTION_ORDER, errors.SubscriptionNotSupportedError),
    (Order.TASKING_ORDER, errors.FutureProductNotSupportedError),
])
def test_check_order_type_enabled_invalid(settings, order_type,
                                          expected_exception):
    setattr(settings, "OSEOSERVER_{0}".format(order_type), {
        "enabled": False
    })
    with pytest.raises(expected_exception):
        submit.check_order_type_enabled(order_type)


@pytest.mark.parametrize("order_type", [
    Order.PRODUCT_ORDER,
    Order.MASSIVE_ORDER,
    Order.SUBSCRIPTION_ORDER,
    Order.TASKING_ORDER,
])
def test_check_collection_enabled(settings, order_type):
    collection_id = "some_id"
    collection_name = "fake_collection"
    settings.OSEOSERVER_COLLECTIONS = [
        {
            "name": collection_name,
            "collection_identifier": collection_id,
            "product_order": {"enabled": True,},
            "massive_order": {"enabled": True,},
            "subscription_order": {"enabled": True,},
            "tasking_order": {"enabled": True,},
        }
    ]
    result = submit.check_collection_enabled(
        collection_id=collection_id,
        order_type=order_type
    )
    assert result == collection_name


@pytest.mark.parametrize("order_type, expected_exception", [
    (Order.PRODUCT_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.MASSIVE_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.SUBSCRIPTION_ORDER, errors.SubscriptionNotSupportedError),
    (Order.TASKING_ORDER, errors.FutureProductNotSupportedError),
])
def test_check_collection_enabled_fails(settings, order_type,
                                        expected_exception):
    collection_id = "some_id"
    collection_name = "fake_collection"
    settings.OSEOSERVER_COLLECTIONS = [
        {
            "name": collection_name,
            "collection_identifier": collection_id,
            "product_order": {"enabled": False,},
            "massive_order": {"enabled": False,},
            "subscription_order": {"enabled": False,},
            "tasking_order": {"enabled": False,},
        }
    ]
    with pytest.raises(expected_exception):
        submit.check_collection_enabled(
            collection_id=collection_id,
            order_type=order_type
        )


def test_get_collection_settings():
    collection_identifier = "some_id"
    fake_collection_settings = [
        {"collection_identifier": collection_identifier},
    ]
    with mock.patch("oseoserver.operations.submit.settings",
                    autospec=True) as mock_settings:
        mock_settings.get_collections.return_value = fake_collection_settings
        result = submit.get_collection_settings(collection_identifier)
        assert result == fake_collection_settings[0]


def test_get_collection_settings_invalid_collection_identifier():
    with mock.patch("oseoserver.operations.submit.settings",
                    autospec=True) as mock_settings, \
            pytest.raises(errors.OseoServerError):
        mock_settings.get_collections.return_value = []
        submit.get_collection_settings("some_id")


def test_create_option():
    option_name = "dummy"
    option_value = "some_value"
    fake_collection_config = {
        "enabled": True,
        "options": [option_name],
    }
    fake_processing_options = [{"name": option_name}]
    option_el = etree.Element(option_name)
    MockProcessor = mock.MagicMock(
        "oseoserver.orderpreparation.exampleorderprocessor."
        "ExampleOrderProcessor", autospec=True
    )
    mock_processor = MockProcessor.return_value
    mock_processor.parse_option.return_value = option_value
    with mock.patch.object(
            submit, "get_order_configuration") as mock_get_order_config, \
            mock.patch("oseoserver.operations.submit.settings",
                       autospec=True) as mock_settings:
        mock_get_order_config.return_value = fake_collection_config
        mock_settings.get_processing_options.return_value = (
            fake_processing_options)
        result = submit.create_option(
            option_element=option_el,
            order_type="phony",
            collection_name="fake",
            customizable_item=models.Order(),
            item_processor=mock_processor
        )
        assert isinstance(result, models.SelectedOrderOption)
        assert result.option == option_name
        assert result.value == option_value


@pytest.mark.parametrize(
    "available, parseable, legal, choices, expected_exception",
    [
        (False, True, True, True, errors.InvalidParameterValueError),
        (True, False, True, True, errors.OseoServerError),
        (True, True, False, True, errors.InvalidParameterValueError),
        (True, True, True, False, errors.InvalidParameterValueError),
    ]
)
def test_create_option_invalid_option(available, parseable, legal, choices,
                                      expected_exception):
    option_name = "dummy"
    option_value = "some_value"
    bad_choices = ["nothing", "here"]
    fake_collection_config = {
        "enabled": True,
        "options": [option_name] if available else [],
    }
    if legal and choices:
        fake_processing_options = [{"name": option_name}]
    elif legal and not choices:
        fake_processing_options = [
            {"name": option_name, "choices": bad_choices}]
    else:
        fake_processing_options = []
    print("fake_processing_options: {}".format(fake_processing_options))
    option_el = etree.Element(option_name)
    MockProcessor = mock.MagicMock(
        "oseoserver.orderpreparation.exampleorderprocessor."
        "ExampleOrderProcessor", autospec=True
    )
    mock_processor = MockProcessor.return_value
    mock_processor_attrs = {
        "parse_option.side_effect": None if parseable else AttributeError,
        "parse_option.return_value": option_value,
    }
    mock_processor.configure_mock(**mock_processor_attrs)

    with mock.patch.object(
            submit, "get_order_configuration") as mock_get_order_config, \
            mock.patch("oseoserver.operations.submit.settings",
                       autospec=True) as mock_settings, \
            pytest.raises(Exception):
        mock_get_order_config.return_value = fake_collection_config
        mock_settings.get_processing_options.return_value = (
            fake_processing_options)
        submit.create_option(
            option_element=option_el,
            order_type="phony",
            collection_name="fake",
            item_processor=mock_processor
        )


@pytest.mark.parametrize("protocol, delivery_type, order_type", [
    ("phony1", SelectedDeliveryOption.ONLINE_DATA_ACCESS, Order.PRODUCT_ORDER),
    ("phony2", SelectedDeliveryOption.ONLINE_DATA_DELIVERY,
     Order.PRODUCT_ORDER),
    ("phony3", SelectedDeliveryOption.ONLINE_DATA_ACCESS,
     Order.SUBSCRIPTION_ORDER),
    ("phony4", SelectedDeliveryOption.ONLINE_DATA_DELIVERY,
     Order.SUBSCRIPTION_ORDER),
])
def test_check_delivery_protocol_enabled(protocol, delivery_type, order_type):
    fake_collection_config = {
        "product_order": {
            "online_data_access_options": [
                "phony1",
            ],
            "online_data_delivery_options": [
                "phony2",
            ],
        },
        "subscription_order": {
            "online_data_access_options": [
                "phony3",
            ],
            "online_data_delivery_options": [
                "phony4",
            ],
        },
    }
    with mock.patch.object(
            submit, "get_order_configuration") as mock_get_order_configuration:
        mock_get_order_configuration.return_value = (
            fake_collection_config)
        submit.check_delivery_protocol(
            protocol=protocol,
            delivery_type=delivery_type,
            order_type=order_type,
            collection="fake"
        )


@pytest.mark.parametrize("protocol, delivery_type, order_type", [
    ("phony1", SelectedDeliveryOption.ONLINE_DATA_ACCESS, Order.PRODUCT_ORDER),
    ("phony2", SelectedDeliveryOption.ONLINE_DATA_DELIVERY,
     Order.PRODUCT_ORDER),
    ("phony3", SelectedDeliveryOption.ONLINE_DATA_ACCESS,
     Order.SUBSCRIPTION_ORDER),
    ("phony4", SelectedDeliveryOption.ONLINE_DATA_DELIVERY,
     Order.SUBSCRIPTION_ORDER),
])
def test_check_delivery_protocol_disabled(protocol, delivery_type, order_type):
    fake_collection_config = {
        "product_order": {
            "online_data_access_options": [],
            "online_data_delivery_options": [],
        },
        "subscription_order": {
            "online_data_access_options": [],
            "online_data_delivery_options": [],
        },
        "massive_order": {
            "online_data_access_options": [],
            "online_data_delivery_options": [],
        },
    }
    with mock.patch.object(
            submit, "get_order_configuration") as mock_get_order_config, \
            pytest.raises(errors.InvalidParameterValueError):
        mock_get_order_config.return_value = (
            fake_collection_config)
        submit.check_delivery_protocol(
            protocol=protocol,
            delivery_type=delivery_type,
            order_type=order_type,
            collection="fake"
        )


@pytest.mark.parametrize("oseo_delivery, expected", [
    (
        oseo.DeliveryOptionsType(
            mediaDelivery=BIND(
                packageMedium="DVD",
                shippingInstructions="other"
            )
        ),
        models.SelectedDeliveryOption(
            delivery_type=SelectedDeliveryOption.MEDIA_DELIVERY,
            delivery_details="DVD, other",
            copies=1
        )
    ),
    (
            oseo.DeliveryOptionsType(
                onlineDataAccess=BIND(protocol="ftp")
            ),
            models.SelectedDeliveryOption(
                delivery_type=SelectedDeliveryOption.ONLINE_DATA_ACCESS,
                delivery_details="ftp",
                copies=1
            )
    ),
    (
            oseo.DeliveryOptionsType(
                onlineDataDelivery=BIND(protocol="ftp")),
            models.SelectedDeliveryOption(
                delivery_type=SelectedDeliveryOption.ONLINE_DATA_DELIVERY,
                delivery_details="ftp",
                copies=1
            )
    ),
])
def test_create_delivery_option(oseo_delivery, expected):
    with mock.patch.object(submit, "check_delivery_protocol") as mock_check:
        mock_check.return_value = True
        result = submit.create_delivery_option(oseo_delivery, "fake1", "fake2")
        assert result.delivery_type == expected.delivery_type
        assert result.annotation == expected.annotation
        assert result.copies == expected.copies
        assert result.special_instructions == expected.special_instructions
        assert result.delivery_details == expected.delivery_details


@pytest.mark.parametrize("order_specification, expected", [
    (oseo.OrderSpecification(orderType="PRODUCT_ORDER"), Order.PRODUCT_ORDER),
    (
        oseo.OrderSpecification(orderType="SUBSCRIPTION_ORDER"),
        Order.SUBSCRIPTION_ORDER
    ),
    (oseo.OrderSpecification(orderType="TASKING_ORDER"), Order.TASKING_ORDER),
    (
        oseo.OrderSpecification(
            orderType="PRODUCT_ORDER",
            orderReference=Order.MASSIVE_ORDER_REFERENCE
        ),
        Order.MASSIVE_ORDER
    ),
    (
        oseo.OrderSpecification(
            orderType="PRODUCT_ORDER",
            orderReference="dummy"
        ),
        Order.PRODUCT_ORDER
    ),
])
def test_get_order_type(order_specification, expected):
        result = submit.get_order_type(order_specification=order_specification)
        assert result == expected


@pytest.mark.parametrize("order_type, enabled, auto_approved, expected", [
    (Order.PRODUCT_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.MASSIVE_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.SUBSCRIPTION_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.TASKING_ORDER, False, False, CustomizableItem.CANCELLED),
    (Order.PRODUCT_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.MASSIVE_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.SUBSCRIPTION_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.TASKING_ORDER, True, False, CustomizableItem.SUBMITTED),
    (Order.PRODUCT_ORDER, True, True, CustomizableItem.ACCEPTED),
    (Order.MASSIVE_ORDER, True, True, CustomizableItem.ACCEPTED),
    (Order.SUBSCRIPTION_ORDER, True, True, CustomizableItem.ACCEPTED),
    (Order.TASKING_ORDER, True, True, CustomizableItem.ACCEPTED),
])
def test_get_initial_status(settings, order_type, enabled,
                            auto_approved, expected):
    setattr(settings, "OSEOSERVER_{}".format(order_type), {
        "enabled": enabled,
        "automatic_approval": auto_approved,
    })
    result = submit._get_initial_status(order_type)
    assert result == expected


@pytest.mark.parametrize("status, expected_details", [
    (CustomizableItem.SUBMITTED, "Order is awaiting approval"),
    (CustomizableItem.ACCEPTED,
     "Order has been placed in the processing queue"),
    (CustomizableItem.IN_PRODUCTION, "Order has been rejected"),
    (CustomizableItem.SUSPENDED, "Order has been rejected"),
    (CustomizableItem.CANCELLED, "Order has been rejected"),
    (CustomizableItem.COMPLETED, "Order has been rejected"),
    (CustomizableItem.FAILED, "Order has been rejected"),
    (CustomizableItem.TERMINATED, "Order has been rejected"),
    (CustomizableItem.DOWNLOADED, "Order has been rejected"),
])
def test_get_order_initial_status(status, expected_details):
    with mock.patch.object(submit, "_get_initial_status") as mock_initial:
        mock_initial.return_value = status
        result = submit.get_order_initial_status("phony")
        assert result == (status, expected_details)


@pytest.mark.parametrize("status, expected_details", [
    (CustomizableItem.SUBMITTED, "Order is awaiting approval"),
    (CustomizableItem.ACCEPTED,
     "Item has been placed in the processing queue"),
    (CustomizableItem.IN_PRODUCTION,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.SUSPENDED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.CANCELLED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.COMPLETED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.FAILED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.TERMINATED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.DOWNLOADED,
     "The Order has been rejected, item won't be processed"),
])
def test_get_order_item_initial_status(status, expected_details):
    with mock.patch.object(submit, "_get_initial_status") as mock_initial:
        mock_initial.return_value = status
        result = submit.get_order_item_initial_status("phony")
        assert result == (status, expected_details)


@pytest.mark.parametrize("order_type, expected", [
    (Order.PRODUCT_ORDER, {"enabled": True}),
    (Order.MASSIVE_ORDER, {"enabled": True}),
    (Order.SUBSCRIPTION_ORDER, {"enabled": True}),
    (Order.TASKING_ORDER, {"enabled": True}),
])
def test_get_order_configuration_enabled(settings, order_type, expected):
    collection_name = "collection1"
    settings.OSEOSERVER_COLLECTIONS = [
        {
            "name": collection_name,
            "product_order": {"enabled": True},
            "massive_order": {"enabled": True},
            "subscription_order": {"enabled": True},
            "tasking_order": {"enabled": True},
        },
    ]
    result = submit.get_order_configuration(
        order_type=order_type,
        collection=collection_name
    )
    assert result == expected


@pytest.mark.parametrize("order_type, expected_exception", [
    (Order.PRODUCT_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.MASSIVE_ORDER, errors.ProductOrderingNotSupportedError),
    (Order.SUBSCRIPTION_ORDER, errors.SubscriptionNotSupportedError),
    (Order.TASKING_ORDER, errors.FutureProductNotSupportedError),
])
def test_get_order_configuration_disabled(settings, order_type,
                                          expected_exception):
    collection_name = "collection1"
    settings.OSEOSERVER_COLLECTIONS = [
        {
            "name": collection_name,
            "product_order": {"enabled": False},
            "massive_order": {"enabled": False},
            "subscription_order": {"enabled": False},
            "tasking_order": {"enabled": False},
        },
    ]
    with pytest.raises(expected_exception):
        submit.get_order_configuration(
            order_type=order_type,
            collection=collection_name
        )


@pytest.mark.parametrize("first, last, company, tel, fax", [
    ("dummy", "phony", "fake", "11111", "22222"),
    (None, None, None, None, None),
])
def test_get_delivery_address_no_postal_address(first, last, company,
                                                tel, fax):
    delivery_address_type = oseo.DeliveryAddressType(
        firstName=first,
        lastName=last,
        companyRef=company,
        telephoneNumber=tel,
        facsimileTelephoneNumber=fax,
    )
    result = submit._get_delivery_address(delivery_address_type)
    assert result["first_name"] == _c(first)
    assert result["last_name"] == _c(last)
    assert result["company_ref"] == _c(company)
    assert result["telephone"] == _c(tel)
    assert result["fax"] == _c(fax)


@pytest.mark.parametrize("street, city, state, code, country, po", [
    ("Dummy Av.", "phony", "fake", "11111", "none", "22jd"),
    (None, None, None, None, None, None),
])
def test_get_delivery_address_postal_address(street, city, state, code,
                                             country, po):
    delivery_address_type = oseo.DeliveryAddressType(
        postalAddress=BIND(
            streetAddress=street,
            city=city,
            state=state,
            postalCode=code,
            country=country,
            postBox=po
        )
    )
    result = submit._get_delivery_address(delivery_address_type)
    assert result["postal_address"]["street_address"] == _c(street)
    assert result["postal_address"]["city"] == _c(city)
    assert result["postal_address"]["state"] == _c(state)
    assert result["postal_address"]["postal_code"] == _c(code)
    assert result["postal_address"]["country"] == _c(country)
    assert result["postal_address"]["post_box"] == _c(po)


@pytest.mark.parametrize("status, expected_details", [
    (CustomizableItem.SUBMITTED, "Order is awaiting approval"),
    (CustomizableItem.ACCEPTED, "Order has been placed in processing queue"),
    (CustomizableItem.IN_PRODUCTION, "Order has been rejected"),
    (CustomizableItem.SUSPENDED, "Order has been rejected"),
    (CustomizableItem.CANCELLED, "Order has been rejected"),
    (CustomizableItem.COMPLETED, "Order has been rejected"),
    (CustomizableItem.FAILED, "Order has been rejected"),
    (CustomizableItem.TERMINATED, "Order has been rejected"),
    (CustomizableItem.DOWNLOADED, "Order has been rejected"),
])
def test_get_order_initial_status(status, expected_details):
    with mock.patch.object(submit, "_get_initial_status") as mock_get_initial:
        mock_get_initial.return_value = status
        result = submit.get_order_initial_status(None)
        result_status, result_details = result
        assert result_details == expected_details


@pytest.mark.parametrize("status, expected_details", [
    (CustomizableItem.SUBMITTED, "Order is awaiting approval"),
    (CustomizableItem.ACCEPTED, "Item has been placed in processing queue"),
    (CustomizableItem.IN_PRODUCTION,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.SUSPENDED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.CANCELLED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.COMPLETED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.FAILED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.TERMINATED,
     "The Order has been rejected, item won't be processed"),
    (CustomizableItem.DOWNLOADED,
     "The Order has been rejected, item won't be processed"),
])
def test_get_order_item_initial_status(status, expected_details):
    with mock.patch.object(submit, "_get_initial_status") as mock_get_initial:
        mock_get_initial.return_value = status
        result = submit.get_order_item_initial_status(None)
        result_status, result_details = result
        assert result_details == expected_details


