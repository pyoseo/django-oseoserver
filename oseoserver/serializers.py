import dateutil.parser
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from . import models
from . import requestprocessor
from . import settings
from . import utilities


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


class SubscriptionBatchSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Batch
        fields = (
            "order",
            "completed_on",
            "updated_on",
            "status",
            "additional_status_info",
        )
        read_only_fields = (
            "completed_on",
            "updated_on",
            "status",
            "additional_status_info",
        )


class MySubscriptionBatchSerializer(serializers.BaseSerializer):
    # define fields here

    def create(self, validated_data):
        return requestprocessor.create_subscription_batch(
            order=validated_data["order"],
            timeslot=validated_data["timeslot"],
            collection=validated_data["collection"]
        )

    def to_internal_value(self, data):
        try:
            timeslot = dateutil.parser.parse(data.get("timeslot"))
        except ValueError:
            raise ValidationError({"timeslot": "Invalid timeslot format"})
        collection = data.get("collection")
        if collection not in (c["name"] for cin settings.get_collections()):
            raise ValidationError({"collection": "Invalid collection"})
        order_id = data.get("order")
        try:
            order = models.Order.objects.get(pk=order_id)
        except models.Order.DoesNotExist:
            raise ValidationError({"order": "Invalid order identifier"})
        return {
            "timeslot": timeslot,
            "collection": collection,
            "order": order,
        }

    def to_representation(self, instance):
        order = instance.order
        item = instance.order_items.get()
        processor = utilities.get_item_processor(order.order_type)

        parsed_identifier = processor.collection_manager.parse_item_identifier(
            item.identifier)
        collection, timeslot = parsed_identifier
        return {
            "order": order.id,
            "collection": collection,
            "timeslot": timeslot.iso_format(),
        }
