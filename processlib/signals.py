from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import pre_migrate, post_migrate

from flow import get_flows
from processlib import autodiscover_flows


def create_flow_permissions(app_config, **kwargs):
    raise Exception()
    for label, flow in get_flows():
        model = flow.process_model
        content_type = ContentType.objects.get_for_model(model)
        Permission.objects.get_or_create(
            content_type=content_type,
            name=str(flow),
            codename=''

        )




pre_migrate.connect(lambda *args, **kwargs: autodiscover_flows(),
                    dispatch_uid="processlib.signals.autodiscover_flows")
