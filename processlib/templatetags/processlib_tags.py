from django import template

from processlib.services import get_user_processes

register = template.Library()


@register.simple_tag
def get_user_process_count(user):
    return len(get_user_processes(user))
