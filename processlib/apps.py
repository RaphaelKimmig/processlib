from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ProcesslibAppConfig(AppConfig):
    def ready(self):
        from .signals import create_flow_permissions
        post_migrate.connect(create_flow_permissions,
                             dispatch_uid="processlib.signals.create_flow_permissions",
                             sender=self)
