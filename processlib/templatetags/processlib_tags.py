from django import template

from processlib import services

register = template.Library()


@register.simple_tag
def get_user_current_process_count(user):
    return len(services.get_user_current_processes(user))


@register.filter
def get_current_activities_in_process(process):
    return services.get_current_activities_in_process(process)


@register.simple_tag
def get_activities_to_do(user, process):
    return services.get_activities_to_do(user, process)
