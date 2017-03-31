# Copyright 2017 Ricardo Garcia Silva
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

"""Some utility functions for pyoseo."""

import importlib
import logging
import re


import dateutil.parser
from lxml import etree
import pytz

from . import settings
from . import errors

logger = logging.getLogger(__name__)


def convert_date_range_option(date_range):
    """Convert a DateRange option to datetime objects

    Parameters
    ----------
    date_range: str
        The value of a DateRange option.

    Returns
    -------
    start: datetime.datetime
        The date range's start value
    stop: datetime.datetime
        The date range's stop value

    Examples
    --------

    >>> convert_date_range_option(
    ...     "start: 2017-01-01T00:00:00+00:00 stop: 2017-01-02T00:00:00+00:00")
    (datetime.datetime(2017, 1, 1, 0, 0, tzinfo=tzlocal()),
    (datetime.datetime(2017, 1, 1, 0, 0, tzinfo=tzlocal()),

    """

    re_obj = re.search(
        r"^start: (.*?) stop: (.*?)$",
        date_range
    )
    start, stop = (dateutil.parser.parse(i) for i in re_obj.groups())
    start = start.replace(tzinfo=pytz.utc) if start.tzinfo is None else start
    stop = stop.replace(tzinfo=pytz.utc) if stop.tzinfo is None else stop
    return start, stop


def get_etree_parser():
    return etree.XMLParser(
        encoding="utf-8",
        resolve_entities=False,
        strip_cdata=True,
        dtd_validation=False,
        load_dtd=False,
        no_network=True
    )


def get_generic_order_config(order_type):
    """Get the generic configuration for the input order type.

    Parameters
    ----------
    order_type: str
        One of the allowed order types, as defined in oseoserver.models.Order

    Returns
    -------
    dict
        The configuration parameters that are defined in the settings
        for the selected order_type

    """

    setting = getattr(settings, "get_{}".format(order_type.lower()))
    return setting()


def get_option_configuration(option_name):
    for option in settings.get_processing_options():
        if option["name"] == option_name:
            return option
    else:
        raise errors.OseoServerError("Invalid option {!r}".format(option_name))


def get_subscription_duration(order, collection):
    item_specification = order.item_specifications.filter(
        collection=collection).last()
    date_range = item_specification.get_option("DateRange")
    return convert_date_range_option(date_range.value)


def import_class(python_path, *instance_args, **instance_kwargs):
    """
    """

    module_path, sep, class_name = python_path.rpartition('.')
    try:
        the_module = importlib.import_module(module_path)
        the_class = getattr(the_module, class_name)
        instance = the_class(*instance_args, **instance_kwargs)
    except ImportError:
        raise errors.ServerError(
            "Invalid configuration: {0}".format(python_path))
    else:
        return instance


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
    collection_config = get_collection_settings(
        get_collection_identifier(collection_name))
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


def get_processing_option_settings(option_name):
    processing_options = settings.get_processing_options()
    option_settings = [
        opt for opt in processing_options if opt["name"] == option_name][0]
    return option_settings


def get_collection_settings(collection_id):
    for collection_config in settings.get_collections():
        if collection_config["collection_identifier"] == collection_id:
            result = collection_config
            break
    else:
        raise errors.UnsupportedCollectionError()
    return result


def get_collection_identifier(name):
    all_collections = settings.get_collections()
    try:
        config = [c for c in all_collections if c["name"] == name][0]
        identifier = config["collection_identifier"]
    except IndexError:
        identifier = ""
    return identifier


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
