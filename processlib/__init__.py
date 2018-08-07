from django.utils.module_loading import autodiscover_modules


def autodiscover_flows():
    autodiscover_modules("flows")


default_app_config = "processlib.apps.ProcesslibAppConfig"


__all__ = ["autodiscover_flows", "default_app_config"]
