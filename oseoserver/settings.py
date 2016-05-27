"""Providing custom values for oseoserver's settings."""

from django.conf import settings


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

OSEOSERVER_COLLECTIONS = get_setting(
    "OSEOSERVER_COLLECTIONS",
    [
        {
            "name": "dummy collection",
            "catalogue_endpoint": "http://localhost",
            "collection_identifier": "dummy_collection_id",
            "product_price": 0,
            "generation_frequency": "Once per hour",
            "product_orders": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
            "subscription_orders": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
            "tasking_orders": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
            "massive_orders": {
                "enabled": False,
                "order_processing_fee": 0,
                "options": [],
                "delivery_options": [],
                "payment_options": [],
                "scene_selection_options": [],
            },
        },
    ]
)
