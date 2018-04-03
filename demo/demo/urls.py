from django.conf.urls import url

from processlib.views import (ProcessListView, ProcessDetailView, ProcessStartView, ProcessActivityView,
                              ActivityUndoView, ActivityCancelView)
from order.views import OrderViewForm


from crm_inbox.flows import *  # noqa
from order.flows import *  # noqa


urlpatterns = [
    url(r'^process/$', ProcessListView.as_view(), name='process-list'),
    url(r'^process/start/(?P<flow_label>.*)/$', ProcessStartView.as_view(), name='process-start'),
    url(r'^process/activity/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$', ProcessActivityView.as_view(), name='process-activity'),
    url(r'^process/undo/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$', ActivityUndoView.as_view(), name='activity-undo'),
    url(r'^process/cancel/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$', ActivityCancelView.as_view(), name='activity-cancel'),
    url(r'^process/(?P<pk>.*)/$', ProcessDetailView.as_view(), name='process-detail'),

    url(r'^order/(?P<config_id>\d+)/$', OrderViewForm.as_view(), name='order-process'),
    url(r'^order/(?P<config_id>\d+)/(?P<process_id>.*)/$', OrderViewForm.as_view(), name='order-process'),
]
