from django.utils.module_loading import autodiscover_modules


def autodiscover_flows():
    autodiscover_modules("flows")


__all__ = ["autodiscover_flows"]
