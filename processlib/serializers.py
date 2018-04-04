from rest_framework import serializers

from processlib.flow import get_flow
from .models import Process


class ProcessSerializer(serializers.ModelSerializer):
    process_data = serializers.DictField(write_only=True, required=False)
    activity_data = serializers.DictField(write_only=True, required=False)

    def create(self, validated_data):
        flow_label = validated_data.pop('flow_label')
        flow = get_flow(flow_label)
        activity = flow.get_start_activity(**validated_data.get('process_data', {}))
        activity.instantiate()
        activity.start(**validated_data.get('activity_data', {}))
        activity.finish(**validated_data.get('activity_data', {}))
        return activity.process

    class Meta:
        model = Process

