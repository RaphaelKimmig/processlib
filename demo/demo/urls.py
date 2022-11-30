from django.urls import path, include
from rest_framework import routers

from crm_inbox.flows import *  # noqa
from processlib.views import (ProcessViewSet)


router = routers.DefaultRouter()
router.register('process', ProcessViewSet)


urlpatterns = [
    path('process/', include('processlib.urls', namespace='processlib')),
    path('api/', include(router.urls)),
]
