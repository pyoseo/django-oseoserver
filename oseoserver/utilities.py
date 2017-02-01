# Copyright 2016 Ricardo Garcia Silva
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
Some utility functions for pyoseo
"""

import importlib
import logging

#from celery.utils import mail
#from pygments import highlight
#from pygments.lexers import PythonLexer
#from pygments.formatters import HtmlFormatter

from . import settings
from . import constants
from . import errors

logger = logging.getLogger(__name__)


def import_class(python_path, *instance_args, **instance_kwargs):
    """
    """

    module_path, sep, class_name = python_path.rpartition('.')
    try:
        the_module = importlib.import_module(module_path)
        the_class = getattr(the_module, class_name)
        instance = the_class(*instance_args, **instance_kwargs)
    except ImportError as err:
        raise errors.ServerError(
            "Invalid configuration: {0}".format(python_path))
    else:
        return instance


def get_generic_order_config(order_type):
    """Get the generic configuration for the input order type.

    Parameters
    ----------
    order_type: oseoserver.constants.OrderType
        The enumeration of the order type

    Returns
    -------
    dict
        The configuration parameters that are defined in the settings
        for the selected order_type

    """

    setting = getattr(settings, "get_{}".format(order_type.value.lower()))
    return setting()


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
            order_type.value.lower(), {})
        is_enabled = type_specific_config.get("enabled", False)
        if is_collection and is_enabled:
            result = type_specific_config
            break
    else:
        if order_type in (constants.OrderType.PRODUCT_ORDER,
                          constants.OrderType.MASSIVE_ORDER):
            raise errors.ProductOrderingNotSupportedError()
        elif order_type == constants.OrderType.SUBSCRIPTION_ORDER:
            raise errors.SubscriptionNotSupportedError()
        elif order_type == constants.OrderType.TASKING_ORDER:
            raise errors.FutureProductNotSupportedError()
        else:
            raise errors.OseoServerError(
                "Unable to get order configuration")
    return result


def get_option_configuration(option_name):
    for option in settings.get_processing_options():
        if option["name"] == option_name:
            return option
    else:
        raise errors.OseoServerError("Invalid option {!r}".format(option_name))



def validate_collection_id(collection_id):
    for collection_config in settings.get_collections():
        if collection_config.get("collection_identifier") == collection_id:
            result = collection_config
            break
    else:
        raise errors.InvalidParameterValueError("collectionId")
    return result


def validate_processing_option(name, value, order_type, collection_name):
    """Validate the input arguments against the configured options"""

    # 1. can this option be used with the current collection and order_type?
    collection_config = get_order_configuration(order_type, collection_name)
    if name not in collection_config.get("options", []):
        raise errors.InvalidParameterValueError("option", value=name)

    # 2. Lets get the parsed value for the option using the external
    #    item_processor
    item_processor_class_path = get_generic_order_config(
        order_type)["item_processor"]
    try:
        item_processor = import_class(item_processor_class_path)
        parsed_value = item_processor.parse_option(name, value)
    except AttributeError:
        raise errors.OseoServerError(
            "Incorrectly configured "
            "item_processor: {}".format(item_processor_class_path)
        )
    except IndexError:
        raise errors.InvalidParameterValueError(locator="option", value=name)
    # 3. is the parsed value legal?
    for option in settings.get_processing_options():
        if option.get("name") == name:
            choices = option.get("choices", [])
            if parsed_value not in choices and len(choices) > 0:
                raise errors.InvalidParameterValueError("option",
                                                        value=parsed_value)
            break
    else:
        raise errors.InvalidParameterValueError("option", value=parsed_value)
    return parsed_value


def get_item_processor(order_type):
    generic_order_settings = get_generic_order_config(order_type)
    item_processor_class_path = generic_order_settings["item_processor"]
    processor = import_class(item_processor_class_path)
    return processor


def _c(value):
    """
    Convert between a None and an empty string.

    This function translates pyxb's empty elements, which are stored as
    None into django's empty values, which are stored as an empty string.
    """

    return '' if value is None else str(value)

def _n(value):
    """
    Convert between an empty string and a None

    This function is translates django's empty elements, which are stored
    as empty strings into pyxb empty elements, which are stored as None.
    """

    return None if value == '' else value


#class OseoCeleryErrorMail(mail.ErrorMail):
#
#    def format_body(self, context):
#        template = "order_item_failed.html"
#        context["highlighted_exc"] = highlight(
#            context["exc"], PythonLexer(), HtmlFormatter())
#        context["highlighted_traceback"] = highlight(
#            context["traceback"], PythonLexer(), HtmlFormatter())
#        msg = render_to_string(template, context)
#        return msg
#
#    def format_subject(self, context):
#        subject = "Copernicus Global Land Service - Task error"
#        return subject
#
#    def send(self, context, exc, fail_silently=True):
#        if self.should_send(context, exc):
#            UserModel = get_user_model()
#            send_email(
#                self.format_subject(context),
#                self.format_body(context),
#                UserModel.objects.filter(is_staff=True).exclude(email=""),
#                html=True
#            )
