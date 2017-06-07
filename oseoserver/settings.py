"""Providing custom values for oseoserver's settings."""

from django.conf import settings

from . import constants


def _get_setting(parameter, default_value):
    return getattr(settings, parameter, default_value)


def get_processing_class():
    return _get_setting(
        "OSEOSERVER_PROCESSING_CLASS",
        "oseoserver.orderpreparation.ExampleOrderProcessor"
    )


def get_max_order_items():
    return _get_setting("OSEOSERVER_MAX_ORDER_ITEMS", 200)


def get_max_active_items():
    return _get_setting("OSEOSERVER_MAX_ACTIVE_ITEMS", 400)


def get_massive_order_max_size():
    return _get_setting("OSEOSERVER_MASSIVE_ORDER_MAX_SIZE", 1000)


def get_product_order():
    return _get_setting(
        "OSEOSERVER_PRODUCT_ORDER",
        {
            "enabled": False,
            "automatic_approval": False,
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor",
            "item_availability_days": 10,
            "notifications": {
                "moderation": False,
                "item_availability": False,
                "batch_availability": None,
            }
        }
    )


def get_subscription_order():
    return _get_setting(
        "OSEOSERVER_SUBSCRIPTION_ORDER",
        {
            "enabled": False,
            "automatic_approval": False,
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor",
            "item_availability_days": 10,
            "notifications": {
                "moderation": True,
                "item_availability": False,
                "batch_availability": "daily",
            }
        }
    )


def get_tasking_order():
    return _get_setting(
        "OSEOSERVER_TASKING_ORDER",
        {
            "enabled": False,
            "automatic_approval": False,
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor",
            "item_availability_days": 10,
            "notifications": {
                "moderation": True,
                "item_availability": False,
                "batch_availability": "immediate",
            }
        }
    )


def get_massive_order():
    return _get_setting(
        "OSEOSERVER_MASSIVE_ORDER",
        {
            "enabled": False,
            "automatic_approval": False,
            "item_processor": "oseoserver.orderpreparation."
                              "exampleorderprocessor.ExampleOrderProcessor",
            "item_availability_days": 10,
            "notifications": {
                "moderation": True,
                "item_availability": False,
                "batch_availability": "immediate",
            }
        }
    )


def get_processing_options():
    return _get_setting(
        "OSEOSERVER_PROCESSING_OPTIONS",
        [
            {
                "name": "dummy option",
                "description": "A dummy option",
                "multiple_entries": False,
                "choices": ["first", "second"],
            }
        ]
    )


def get_online_data_access_options():
    return _get_setting(
        "OSEOSERVER_ONLINE_DATA_ACCESS_OPTIONS",
        [
            {
                "protocol": constants.DeliveryOptionProtocol.FTP.value,
                "fee": 0,
            },
            {
                "protocol": constants.DeliveryOptionProtocol.HTTP.value,
                "fee": 0,
            }
        ]
    )


def get_online_data_delivery_options():
    return _get_setting(
        "OSEOSERVER_ONLINE_DATA_DELIVERY_OPTIONS",
        [
            {
                "protocol": constants.DeliveryOptionProtocol.FTP.value,
                "fee": 0,
            },
        ]
    )


def get_media_delivery_options():
    return _get_setting(
        "OSEOSERVER_MEDIA_DELIVERY_OPTIONS",
        {
            "media": [
                {
                    "type": constants.DeliveryMedium.CD_ROM,
                    "fee": 0,
                }
            ],
            "shipping": [
                constants.DeliveryMethod.ALL_READY,
            ]
        }
    )


def get_payment_options():
    return _get_setting(
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


def get_collections():
    return _get_setting(
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
