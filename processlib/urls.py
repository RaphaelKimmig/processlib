from django.conf.urls import url

from processlib.views import (
    ProcessListView,
    ProcessDetailView,
    ProcessStartView,
    ProcessActivityView,
    UserCurrentProcessListView,
    UserProcessListView,
    ActivityUndoView,
    ActivityCancelView,
    ActivityRetryView,
    ProcessCancelView,
)

urlpatterns = [
    url(r"^process/$", ProcessListView.as_view(), name="process-list"),
    url(
        r"^process/user-current/$",
        UserCurrentProcessListView.as_view(),
        name="process-list-user-current",
    ),
    url(r"^process/user/$", UserProcessListView.as_view(), name="process-list-user"),
    url(
        r"^process/start/(?P<flow_label>.*)/$",
        ProcessStartView.as_view(),
        name="process-start",
    ),
    url(
        r"^process/activity/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ProcessActivityView.as_view(),
        name="process-activity",
    ),
    url(
        r"^process/undo/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ActivityUndoView.as_view(),
        name="activity-undo",
    ),
    url(
        r"^process/cancel/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ActivityCancelView.as_view(),
        name="activity-cancel",
    ),
    url(
        r"^process/retry/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ActivityRetryView.as_view(),
        name="activity-retry",
    ),
    url(r"^process/(?P<pk>.*)/$", ProcessDetailView.as_view(), name="process-detail"),
    url(
        r"^process/(?P<pk>.*)/cancel$",
        ProcessCancelView.as_view(),
        name="process-cancel",
    ),
]
