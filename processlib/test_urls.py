from django.urls import re_path, include

urlpatterns = [
    re_path(r'^process/', include(('processlib.urls', "processlib"), namespace="processlib")),
]
