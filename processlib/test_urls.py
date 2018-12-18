from django.conf.urls import url, include

urlpatterns = [
    url(r'^process/', include('processlib.urls', namespace='processlib')),
]
