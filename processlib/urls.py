from django.conf.urls import url

from processlib.views import (ProcessListView, ProcessDetailView, ProcessStartView,
                              ProcessActivityView,
                              ActivityUndoView, ActivityCancelView)

urlpatterns = [
    url(r'^process/$', ProcessListView.as_view(), name='process-list'),
    url(r'^process/start/(?P<flow_label>.*)/$', ProcessStartView.as_view(), name='process-start'),
    url(r'^process/activity/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$',
        ProcessActivityView.as_view(), name='process-activity'),
    url(r'^process/undo/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$', ActivityUndoView.as_view(),
        name='activity-undo'),
    url(r'^process/cancel/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$',
        ActivityCancelView.as_view(), name='activity-cancel'),
    url(r'^process/(?P<pk>.*)/$', ProcessDetailView.as_view(), name='process-detail'),
]
