from django.conf.urls import url, include
from rest_framework import routers

from crm_inbox.flows import *  # noqa
from processlib.views import (ProcessViewSet)


router = routers.DefaultRouter()
router.register('process', ProcessViewSet)


urlpatterns = [
    url(r'^process/', include('processlib.urls', namespace='processlib')),
    url(r'^api/', include(router.urls)),
]
