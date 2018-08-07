from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from processlib.flow import get_flow
from processlib.services import user_has_activity_perm
from .models import Process, ActivityInstance


class ActivityInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityInstance
        fields = ("assigned_user", "assigned_group")


class ProcessSerializer(serializers.ModelSerializer):
    activity_instance = ActivityInstanceSerializer(write_only=True, required=False)
    activity_data = serializers.DictField(write_only=True, required=False)

    def create(self, validated_data):
        request_user = self.context["request"].user
        flow_label = validated_data.pop("flow_label")
        activity_instance = validated_data.pop("activity_instance", {})
        activity_data = validated_data.pop("activity_data", {})

        flow = get_flow(flow_label)
        activity = flow.get_start_activity(
            process_kwargs=validated_data, activity_instance_kwargs=activity_instance
        )

        if not user_has_activity_perm(self.context["request"].user, activity):
            raise PermissionDenied

        if "user" not in activity_data and request_user.is_authenticated:
            activity_data["user"] = request_user

        activity.start(**activity_data)
        activity.finish(**activity_data)

        return activity.process

    class Meta:
        model = Process
