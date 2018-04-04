from rest_framework import serializers

from processlib.flow import get_flow
from .models import Process


class ProcessSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        flow_label = validated_data.pop('flow_label')
        flow = get_flow(flow_label)
        activity = flow.get_start_activity(**validated_data)
        activity.start()
        activity.finish()
        return activity.process

    class Meta:
        model = Process

