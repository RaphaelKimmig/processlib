from rest_framework import serializers

from processlib.flow import get_flow
from .models import Process


class ProcessSerializer(serializers.ModelSerializer):
    activity_data = serializers.DictField(write_only=True, required=False)

    def create(self, validated_data):
        flow_label = validated_data.pop('flow_label')
        activity_data = validated_data.pop('activity_data', {})
        flow = get_flow(flow_label)
        activity = flow.get_start_activity(**validated_data)
        activity.start(**activity_data)
        activity.finish(**activity_data)
        return activity.process

    class Meta:
        model = Process

