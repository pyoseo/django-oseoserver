from collections import namedtuple

import dateutil.parser
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from . import models
from . import settings


class SubscriptionOrderSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Order
        fields = (
            "id",
            "status",
            "additional_status_info",
            "completed_on",
            "status_changed_on",
            "remark",
        )
        read_only_fields =(
            "id",
            "status",
            "additional_status_info",
            "completed_on",
            "status_changed_on",
        )

    def create(self, validated_data):
        return models.Order.objects.create(
            order_type=models.Order.SUBSCRIPTION_ORDER,
            **validated_data
        )


class SubscriptionProcessTimeslotSerializer(serializers.BaseSerializer):

    def to_internal_value(self, data):
        try:
            timeslot = dateutil.parser.parse(data.get("timeslot"))
        except ValueError:
            raise ValidationError({"timeslot": "Invalid timeslot format"})
        except TypeError:
            raise ValidationError({"timeslot": "This field is required"})
        collection = data.get("collection")
        if collection is None:
            raise ValidationError({"collection": "This field is required"})
        elif collection not in (c["name"] for c in settings.get_collections()):
            raise ValidationError({"collection": "Invalid collection"})
        force_creation = data.get("force_creation", False)
        return {
            "timeslot": timeslot,
            "collection": collection,
            "force_creation": force_creation,
        }


class SubscriptionBatchSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Batch
        fields = (
            "id",
            "order",
            "completed_on",
            "updated_on",
            "status",
            "additional_status_info",
        )
        read_only_fields = (
            "id",
            "completed_on",
            "updated_on",
            "status",
            "additional_status_info",
        )
