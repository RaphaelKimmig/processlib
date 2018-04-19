from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import pre_migrate

from processlib import autodiscover_flows
from .flow import get_flows


def create_flow_permissions(app_config, **kwargs):
    for label, flow in get_flows():
        process_content_type = ContentType.objects.get_for_model(flow.process_model)
        Permission.objects.update_or_create(
            content_type=process_content_type,
            codename='flow_{}'.format(flow.label),
            defaults={'name': "{} (all)".format(str(flow))},
        )
        activity_content_type = ContentType.objects.get_for_model(flow.activity_model)
        for activity_name, activity in flow._activities.items():
            name = flow._activity_kwargs[activity_name].get('verbose_name', '') or activity_name
            Permission.objects.update_or_create(
                content_type=activity_content_type,
                codename='activity_{}_{}'.format(flow.label, activity_name),
                defaults={'name': "{} in {}".format(str(name), str(flow))},
            )


pre_migrate.connect(lambda *args, **kwargs: autodiscover_flows(),
                    dispatch_uid="processlib.signals.autodiscover_flows")
