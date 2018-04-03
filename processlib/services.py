from processlib.flow import get_flow
from processlib.models import ActivityInstance, Process


def get_process_for_flow(flow_label, process_id):
    flow = get_flow(flow_label)
    process = flow.process_model._default_manager.get(pk=process_id)
    return process


def get_activity_for_flow(flow_label, activity_instance_id):
    flow = get_flow(flow_label)
    instance = flow.activity_model._default_manager.get(pk=activity_instance_id)
    return flow.get_activity_by_instance(instance)


def get_current_activities_in_process(process):
    instances = process.flow.activity_model._default_manager.filter(process_id=process.pk)
    return (
        instance.activity for instance in instances.exclude(
        status__in=(ActivityInstance.STATUS_FINISHED, ActivityInstance.STATUS_CANCELED))
    )


def get_finished_activities_in_process(process):
    instances = process.flow.activity_model._default_manager.filter(process_id=process.pk)
    return (
        instance.activity for instance in instances.filter(status=ActivityInstance.STATUS_FINISHED)
    )


def get_user_processes(user):
    return Process.objects.all()
