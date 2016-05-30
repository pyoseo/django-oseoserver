"""Providing custom values for oseoserver's settings."""

from django.conf import settings

from . import constants


def get_setting(parameter, default_value):
    return getattr(settings, parameter, default_value)


OSEOSERVER_AUTHENTICATION_CLASS = get_setting(
    "OSEOSERVER_AUTHENTICATION_CLASS", "")

OSEOSERVER_PROCESSING_CLASS = get_setting(
    "OSEOSERVER_PROCESSING_CLASS",
    "oseoserver.orderpreparation.ExampleOrderProcessor"
)

OSEOSERVER_OPTIONS_CLASS = get_setting("OSEOSERVER_OPTIONS_CLASS", "")

OSEOSERVER_SITE_DOMAIN = get_setting("OSEOSERVER_SITE_DOMAIN", "example.com")

OSEOSERVER_MAX_ORDER_ITEMS = get_setting("OSEOSERVER_MAX_ORDER_ITEMS", 200)

OSEOSERVER_PRODUCT_ORDER = get_setting(
    "OSEOSERVER_PRODUCT_ORDER",
    {
        "enabled": False,
        "automatic_approval": False,
        "notify_creation": True,
        "item_processor": "oseoserver.orderpreparation."
                          "exampleorderprocessor.ExampleOrderProcessor",
        "item_availability_days": 10,
    }
)

OSEOSERVER_SUBSCRIPTION_ORDER = get_setting(
    "OSEOSERVER_SUBSCRIPTION_ORDER",
    {
        "enabled": False,
        "automatic_approval": False,
        "notify_creation": True,
        "item_processor": "oseoserver.orderpreparation."
                          "exampleorderprocessor.ExampleOrderProcessor",
        "item_availability_days": 10,
    }
)

OSEOSERVER_TASKING_ORDER = get_setting(
    "OSEOSERVER_TASKING_ORDER",
    {
        "enabled": False,
        "automatic_approval": False,
        "notify_creation": True,
        "item_processor": "oseoserver.orderpreparation."
                          "exampleorderprocessor.ExampleOrderProcessor",
        "item_availability_days": 10,
    }
)

OSEOSERVER_MASSIVE_ORDER = get_setting(
    "OSEOSERVER_MASSIVE_ORDER",
    {
        "enabled": False,
        "automatic_approval": False,
        "notify_creation": True,
        "item_processor": "oseoserver.orderpreparation."
                          "exampleorderprocessor.ExampleOrderProcessor",
        "item_availability_days": 10,
    }
)

OSEOSERVER_OPTIONS = get_setting(
    "OSEOSERVER_OPTIONS",
    [
        {
            "name": "dummy option",
            "description": "A dummy option",
            "multiple_entries": False,
            "choices": ["first", "second"],
        }
    ]
)

OSEOSERVER_ONLINE_DATA_ACCESS_OPTIONS = get_setting(
    "OSEOSERVER_ONLINE_DATA_ACCESS_OPTIONS",
    [
        constants.DeliveryOptionProtocol.FTP.value,
        constants.DeliveryOptionProtocol.HTTP.value,
    ]
)

OSEOSERVER_ONLINE_DATA_DELIVERY_OPTIONS = get_setting(
    "OSEOSERVER_ONLINE_DATA_DELIVERY_OPTIONS",
    [
        constants.DeliveryOptionProtocol.FTP.value,
    ]
)

OSEOSERVER_MEDIA_DELIVERY_OPTIONS = get_setting(
    "OSEOSERVER_MEDIA_DELIVERY_OPTIONS",
    {
        "media": [
            constants.DeliveryMedium.CD_ROM,
        ],
        "shipping": [
            constants.DeliveryMethod.ALL_READY,
        ]
    }
)

OSEOSERVER_PAYMENT_OPTIONS = get_setting(
    "OSEOSERVER_PAYMENT_OPTIONS",
    [
        {
            "name": "dummy payment option",
            "description": "A dummy payment option",
            "multiple_entries": False,
            "choices": None,
        }
    ]
)

OSEOSERVER_COLLECTIONS = get_setting(
    "OSEOSERVER_COLLECTIONS",
    [
        {
            "name": "dummy collection",
            "catalogue_endpoint": "http://localhost",
            "collection_identifier": "dummy_collection_id",
            "product_price": 0,
            "generation_frequency": "Once per hour",
            "product_order": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "online_data_access_options": [],
                "online_data_delivery_options": [],
                "media_delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
            "subscription_order": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "online_data_access_options": [],
                "online_data_delivery_options": [],
                "media_delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
            "tasking_order": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "online_data_access_options": [],
                "online_data_delivery_options": [],
                "media_delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
            "massive_order": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "online_data_access_options": [],
                "online_data_delivery_options": [],
                "media_delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
        },
    ]
)
