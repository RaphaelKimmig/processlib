from django.urls import re_path

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
    re_path(r"^process/$", ProcessListView.as_view(), name="process-list"),
    re_path(
        r"^process/user-current/$",
        UserCurrentProcessListView.as_view(),
        name="process-list-user-current",
    ),
    re_path(r"^process/user/$", UserProcessListView.as_view(), name="process-list-user"),
    re_path(
        r"^process/start/(?P<flow_label>.*)/$",
        ProcessStartView.as_view(),
        name="process-start",
    ),
    re_path(
        r"^process/activity/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ProcessActivityView.as_view(),
        name="process-activity",
    ),
    re_path(
        r"^process/undo/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ActivityUndoView.as_view(),
        name="activity-undo",
    ),
    re_path(
        r"^process/cancel/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ActivityCancelView.as_view(),
        name="activity-cancel",
    ),
    re_path(
        r"^process/retry/(?P<flow_label>[^/]+)/(?P<activity_id>.*)/$",
        ActivityRetryView.as_view(),
        name="activity-retry",
    ),
    re_path(r"^process/(?P<pk>.*)/$", ProcessDetailView.as_view(), name="process-detail"),
    re_path(
        r"^process/(?P<pk>.*)/cancel$",
        ProcessCancelView.as_view(),
        name="process-cancel",
    ),
]
