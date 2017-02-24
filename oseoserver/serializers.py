from rest_framework import serializers

from . import models


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