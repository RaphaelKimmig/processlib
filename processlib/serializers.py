from rest_framework import serializers

from processlib.flow import get_flow
from .models import Process, ActivityInstance


class ActivityInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityInstance
        fields = ('assigned_user', 'assigned_group', )


class ProcessSerializer(serializers.ModelSerializer):
    activity_instance = ActivityInstanceSerializer(write_only=True, required=False)
    activity_data = serializers.DictField(write_only=True, required=False)

    def create(self, validated_data):
        flow_label = validated_data.pop('flow_label')
        activity_instance = validated_data.pop('activity_instance', {})
        activity_data = validated_data.pop('activity_data', {})
        flow = get_flow(flow_label)
        activity = flow.get_start_activity(process_kwargs=validated_data,
                                           activity_instance_kwargs=activity_instance)
        activity.start(**activity_data)
        activity.finish(**activity_data)
        return activity.process

    class Meta:
        model = Process

