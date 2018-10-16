from django.db.models import Q
from django.utils import timezone

from .flow import get_flow
from .models import Process, ActivityInstance


def get_process_for_flow(flow_label, process_id):
    flow = get_flow(flow_label)
    process = flow.process_model._default_manager.get(pk=process_id)
    return process


def get_activity_for_flow(flow_label, activity_instance_id):
    flow = get_flow(flow_label)
    instance = flow.activity_model._default_manager.get(pk=activity_instance_id)
    return flow.get_activity_by_instance(instance)


def get_activities_to_do(user, process):
    if process.status in (process.STATUS_CANCELED, process.STATUS_DONE):
        return []

    instances = process.flow.activity_model._default_manager.filter(
        process_id=process.id
    )
    activities = []
    for instance in instances.exclude(
        status__in=(process.STATUS_DONE, process.STATUS_CANCELED)
    ).order_by("instantiated_at"):
        activity = instance.activity
        if not user_has_activity_perm(user, activity):
            continue

        if activity.has_view() or instance.status == instance.STATUS_ERROR:
            activities.append(activity)
    return activities


def get_current_activities_in_process(process):
    instances = process.flow.activity_model._default_manager.filter(
        process_id=process.id
    )
    return (
        instance.activity
        for instance in instances.exclude(
            status__in=(process.STATUS_DONE, process.STATUS_CANCELED)
        ).order_by("instantiated_at")
    )


def get_finished_activities_in_process(process):
    instances = process.flow.activity_model._default_manager.filter(
        process_id=process.id
    ).order_by("instantiated_at")
    return (
        instance.activity for instance in instances.filter(status=process.STATUS_DONE)
    )


def get_activities_in_process(process):
    instances = process.flow.activity_model._default_manager.filter(
        process_id=process.id
    ).order_by("instantiated_at")
    return (
        instance.activity
        for instance in instances.exclude(status=process.STATUS_CANCELED)
    )


def cancel_and_undo_predecessors(activity):
    activity.cancel()
    for instance in activity.instance.predecessors.all():
        instance.activity.undo()


def cancel_process(process, user):
    assert process.can_cancel()
    activities = get_current_activities_in_process(process)

    for activity in activities:
        activity.cancel(user=user)

    process.status = Process.STATUS_CANCELED
    process.finished_at = timezone.now()
    process.save()


def get_user_processes(user, include_unassigned=True):
    q = Q(_activity_instances__assigned_group__in=user.groups.all()) & ~Q(
        _activity_instances__status=ActivityInstance.STATUS_CANCELED
    ) | Q(_activity_instances__assigned_user=user) & ~Q(
        _activity_instances__status=ActivityInstance.STATUS_CANCELED
    )

    if include_unassigned:
        q |= Q(
            _activity_instances__assigned_user__isnull=True,
            _activity_instances__assigned_group__isnull=True,
        ) & ~Q(_activity_instances__status=ActivityInstance.STATUS_CANCELED)

    return Process.objects.filter(q).distinct()


def get_user_current_processes(user, include_unassigned=True):
    q = Q(
        _activity_instances__assigned_group__in=user.groups.all(),
        _activity_instances__status__in=(
            ActivityInstance.STATUS_INSTANTIATED,
            ActivityInstance.STATUS_ERROR,
        ),
    ) | Q(
        _activity_instances__assigned_user=user,
        _activity_instances__status__in=(
            ActivityInstance.STATUS_INSTANTIATED,
            ActivityInstance.STATUS_ERROR,
        ),
    )

    if include_unassigned:
        q |= Q(
            _activity_instances__assigned_group__isnull=True,
            _activity_instances__assigned_user__isnull=True,
            _activity_instances__status__in=(
                ActivityInstance.STATUS_INSTANTIATED,
                ActivityInstance.STATUS_ERROR,
            ),
        )

    return Process.objects.filter(status=Process.STATUS_STARTED).filter(q).distinct()


def user_has_any_process_perm(user, process):
    # if there are no required permissions we grant access
    if not process.flow.has_any_permissions():
        return True

    if process.flow.permission and user.has_perm(process.flow.permission):
        return True

    for activity in get_activities_in_process(process):
        if activity.permission and user.has_perm(activity.permission):
            return True

    return False


def user_has_activity_perm(user, activity):
    if not activity.permission and not activity.flow.permission:
        # if there are no required permissions we grant access
        return True
    elif activity.permission and activity.flow.permission:
        return user.has_perm(activity.permission) and user.has_perm(activity.permission)
    elif activity.permission:
        return user.has_perm(activity.permission)
    elif activity.flow.permission:
        return user.has_perm(activity.flow.permission)
