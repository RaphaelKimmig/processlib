from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import TestCase, TransactionTestCase, RequestFactory
from django.urls import reverse

from .activity import (
    Activity,
    StartActivity,
    EndActivity,
    ViewActivity,
    Wait,
    StartViewActivity,
)
from .activity import FunctionActivity, AsyncActivity
from .assignment import inherit, nobody, request_user
from .flow import Flow
from .forms import ProcessCancelForm
from .models import ActivityInstance, Process, validate_flow_label, is_format_string
from .services import (
    get_user_processes,
    get_user_current_processes,
    get_current_activities_in_process,
    get_process_for_flow,
    get_activity_for_flow,
    get_activities_to_do,
    get_finished_activities_in_process,
    cancel_process,
    cancel_and_undo_predecessors,
)
from .services import user_has_activity_perm, user_has_any_process_perm
from .templatetags import processlib_tags
from .views import (
    ProcessUpdateView,
    ProcessDetailView,
    ProcessListView,
    UserProcessListView,
    UserCurrentProcessListView,
    ProcessCancelView,
    ProcessStartView,
    ProcessActivityView,
    ActivityUndoView,
    ActivityRetryView,
    ActivityCancelView,
    ProcessViewSet,
)

User = get_user_model()


class FlowTest(TestCase):
    def test_never_wait_for_conditional(self):
        flow = Flow("flow_name").start_with(
            "optional", StartActivity, skip_if=lambda: True
        )

        with self.assertRaises(ValueError):
            flow.and_then("wait", Wait, wait_for=["optional"])

    def test_assignment_inheritance(self):
        user = User.objects.create(username="assigned")
        flow = (
            Flow("assign_inherit_flow")
            .start_with("start", StartActivity)
            .and_then("end", EndActivity, assign_to=inherit)
        )
        start = flow.get_start_activity(
            activity_instance_kwargs={"assigned_user": user}
        )
        process = start.process

        start.start()
        start.finish()

        self.assertEqual(
            process.activity_instances.get(activity_name="start").assigned_user, user
        )
        self.assertEqual(
            process.activity_instances.get(activity_name="end").assigned_user, user
        )

    def test_clear_assignment(self):
        user = User.objects.create(username="assigned")
        flow = (
            Flow("assign_clear_flow")
            .start_with("start", StartActivity)
            .and_then("end", EndActivity, assign_to=nobody)
        )
        start = flow.get_start_activity(
            activity_instance_kwargs={"assigned_user": user}
        )
        process = start.process

        start.start()
        start.finish()

        self.assertEqual(
            process.activity_instances.get(activity_name="start").assigned_user, user
        )
        self.assertEqual(
            process.activity_instances.get(activity_name="end").assigned_user, None
        )

    def test_request_user_assignment(self):
        user = User.objects.create(username="request_user")
        flow = (
            Flow("assign_request_user_flow")
            .start_with(
                "start",
                StartViewActivity,
                view=ProcessUpdateView.as_view(fields=[]),
                assign_to=request_user,
            )
            .and_then("end", EndActivity)
        )

        factory = RequestFactory()
        request = factory.post("/", {"_finish": True})
        request.user = user

        start = flow.get_start_activity(request=request)
        process = start.process

        start.dispatch(request)

        self.assertEqual(
            process.activity_instances.get(activity_name="start").assigned_user, user
        )


user_processes_test_flow = (
    Flow("user_processes_test_flow")
    .start_with(
        "start",
        StartActivity,
        assign_to=lambda **kwargs: (User.objects.get(username="user_default"), None),
    )
    .and_then(
        "view",
        ViewActivity,
        view=ProcessUpdateView.as_view(),
        assign_to=lambda **kwargs: (User.objects.get(username="user_default"), None),
    )
    .and_then("end", EndActivity)
)


class UserProcessesTest(TestCase):
    def setUp(self):
        self.user_1 = User.objects.create(username="user_1")
        self.user_2 = User.objects.create(username="user_2")
        self.user_default = User.objects.create(username="user_default")

        self.group_1 = Group.objects.create(name="group_1")
        self.group_both = Group.objects.create(name="group_both")

        self.user_1.groups.add(self.group_1)
        self.user_1.groups.add(self.group_both)
        self.user_2.groups.add(self.group_both)

    def test_processes_default_assignment(self):
        start = user_processes_test_flow.get_start_activity()
        start.start()
        start.finish()

        self.assertSequenceEqual([], get_user_processes(self.user_1))
        self.assertSequenceEqual([], get_user_processes(self.user_2))
        self.assertSequenceEqual([start.process], get_user_processes(self.user_default))

    def test_get_processes_assigned_to_user(self):
        start = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={"assigned_user": self.user_1}
        )
        start.start()
        start.finish()

        self.assertSequenceEqual([start.process], get_user_processes(self.user_1))
        self.assertSequenceEqual([], get_user_processes(self.user_2))

    def test_get_processes_assigned_to_user_group(self):
        start_1 = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={"assigned_group": self.group_1}
        )
        start_1.start()
        start_1.finish()

        start_both = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={"assigned_group": self.group_both}
        )
        start_both.start()
        start_both.finish()

        self.assertSequenceEqual(
            [start_both.process, start_1.process], get_user_processes(self.user_1)
        )
        self.assertSequenceEqual([start_both.process], get_user_processes(self.user_2))

    def test_assignment_to_multiple_users(self):
        start = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={"assigned_user": self.user_1}
        )
        start.start()
        start.finish()

        next_activity = next(get_current_activities_in_process(start.process))
        next_activity.assign_to(self.user_2, None)

        self.assertSequenceEqual([start.process], get_user_processes(self.user_1))
        self.assertSequenceEqual([start.process], get_user_processes(self.user_2))

    def test_get_processes_excludes_canceled_activities(self):
        start = user_processes_test_flow.get_start_activity()
        start.start()
        start.finish()

        next_activity = next(get_current_activities_in_process(start.process))
        next_activity.assign_to(self.user_1, None)

        self.assertSequenceEqual([start.process], get_user_processes(self.user_1))
        next_activity.cancel()
        self.assertSequenceEqual([], get_user_processes(self.user_1))

    def test_get_current_processes_assigned_to_user_excludes_finished_processes(self):
        start = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={"assigned_user": self.user_1}
        )
        start.start()
        start.finish()

        next_activity = next(get_current_activities_in_process(start.process))
        next_activity.start()
        next_activity.finish()

        process = start.process
        process.refresh_from_db()

        self.assertEqual(start.process.status, start.process.STATUS_DONE)
        self.assertSequenceEqual([], get_user_current_processes(self.user_1))

    def test_get_current_processes_assigned_to_user_excludes_finished_activities(self):
        start = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={"assigned_user": self.user_1}
        )
        start.start()
        start.finish()
        process = start.process
        process.refresh_from_db()

        self.assertEqual(start.instance.assigned_user, self.user_1)
        self.assertNotEqual(process.status, process.STATUS_DONE)

        self.assertSequenceEqual([], get_user_current_processes(self.user_1))


class ServicesTest(TestCase):
    def test_get_process_for_flow(self):
        Flow("test_get_process_flow").start_with("start", StartActivity)
        process = Process.objects.create(flow_label="test_get_process_flow")

        self.assertEqual(
            get_process_for_flow("test_get_process_flow", process.pk), process
        )

    def test_get_activity_for_flow(self):
        flow = Flow("test_get_activity_flow").start_with("start", StartActivity)
        start_activity = flow.get_start_activity()
        start_activity.start()
        start_activity.finish()

        self.assertEqual(
            get_activity_for_flow(
                "test_get_activity_flow", start_activity.instance.pk
            ).instance,
            start_activity.instance,
        )

    def test_get_activities_to_do(self):
        user = User.objects.create(username="todo_user")
        flow = (
            Flow("test_todo_flow")
            .start_with("start", StartActivity)
            .and_then("view", ViewActivity, view=lambda x: x)
        )
        start_activity = flow.get_start_activity()
        start_activity.start()
        start_activity.finish()

        process = start_activity.process
        self.assertEqual(len(get_activities_to_do(user, process)), 1)

        process.status = Process.STATUS_DONE
        process.save()
        self.assertEqual(get_activities_to_do(user, process), [])

    def test_get_finished_activities_in_process(self):
        flow = Flow("test_finished_flow").start_with("start", StartActivity)
        start_activity = flow.get_start_activity()
        start_activity.start()
        start_activity.finish()

        finished = list(get_finished_activities_in_process(start_activity.process))
        self.assertEqual(len(finished), 1)
        self.assertEqual(finished[0].instance, start_activity.instance)

    def test_cancel_process(self):
        user = User.objects.create(username="cancel_user")
        flow = (
            Flow("test_cancel_flow")
            .start_with("start", StartActivity)
            .and_then("view", ViewActivity, view=lambda x: x)
        )
        start_activity = flow.get_start_activity()
        start_activity.start()
        start_activity.finish()

        process = start_activity.process
        cancel_process(process, user)
        process.refresh_from_db()
        self.assertEqual(process.status, Process.STATUS_CANCELED)

    def test_cancel_and_undo_predecessors(self):
        flow = (
            Flow("test_undo_flow")
            .start_with("start", StartActivity)
            .and_then("view", ViewActivity, view=lambda x: x)
        )
        start_activity = flow.get_start_activity()
        start_activity.start()
        start_activity.finish()

        view_activity = next(get_current_activities_in_process(start_activity.process))
        cancel_and_undo_predecessors(view_activity)

        view_activity.instance.refresh_from_db()
        start_activity.instance.refresh_from_db()

        self.assertEqual(view_activity.instance.status, ActivityInstance.STATUS_CANCELED)
        self.assertEqual(
            start_activity.instance.status, ActivityInstance.STATUS_INSTANTIATED
        )

    def test_get_user_processes_unauthenticated(self):
        from django.contrib.auth.models import AnonymousUser

        user = AnonymousUser()
        self.assertSequenceEqual(get_user_processes(user), [])
        self.assertSequenceEqual(get_user_current_processes(user), [])

    def test_get_activities_to_do_permission_denied(self):
        user = User.objects.create(username="no_perm_user")
        flow = (
            Flow("test_perm_todo_flow")
            .start_with("start", StartActivity)
            .and_then(
                "view", ViewActivity, view=lambda x: x, permission="processlib.some_perm"
            )
        )
        start_activity = flow.get_start_activity()
        start_activity.start()
        start_activity.finish()

        process = start_activity.process
        self.assertEqual(get_activities_to_do(user, process), [])


no_permissions_test_flow = (
    Flow("no_permissions_test_flow")
    .start_with("start", StartActivity)
    .and_then("end", EndActivity)
)

flow_permissions_test_flow = (
    Flow("flow_permissions_test_flow", permission="processlib.flow_permission")
    .start_with("start", StartActivity)
    .and_then("view", ViewActivity, view=ProcessUpdateView.as_view())
    .and_then("end", EndActivity)
)

activity_permissions_test_flow = (
    Flow("activity_permissions_test_flow")
    .start_with("start", StartActivity, permission="processlib.activity_permission")
    .and_then("view", ViewActivity, view=ProcessUpdateView.as_view())
    .and_then("end", EndActivity)
)

combined_permissions_test_flow = (
    Flow("combined_permissions_test_flow", permission="processlib.flow_permission")
    .start_with("start", StartActivity, permission="processlib.activity_permission")
    .and_then("view", ViewActivity, view=ProcessUpdateView.as_view(fields=[]))
    .and_then("end", EndActivity)
)


class ActivityPermissionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="user")

    def test_no_permissions_flow_requires_no_permissions(self):
        start = no_permissions_test_flow.get_start_activity()
        self.assertTrue(user_has_activity_perm(self.user, start))

    def test_activity_perms_default_to_flow_perms(self):
        start = flow_permissions_test_flow.get_start_activity()
        self.assertFalse(user_has_activity_perm(self.user, start))
        self.user.user_permissions.add(
            Permission.objects.get(codename="flow_permission")
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user_has_activity_perm(self.user, start))

    def test_activity_perms_work(self):
        start = activity_permissions_test_flow.get_start_activity()
        self.assertFalse(user_has_activity_perm(self.user, start))
        self.user.user_permissions.add(
            Permission.objects.get(codename="activity_permission")
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user_has_activity_perm(self.user, start))

    def test_activity_perms_apply_only_to_specified_activity(self):
        start = activity_permissions_test_flow.get_start_activity()

        start.start()
        start.finish()
        view_activity = next(get_current_activities_in_process(start.process))

        self.assertFalse(user_has_activity_perm(self.user, start))
        self.assertTrue(user_has_activity_perm(self.user, view_activity))

    def test_combined_perms_require_both(self):
        start = combined_permissions_test_flow.get_start_activity()

        self.assertFalse(user_has_activity_perm(self.user, start))

        self.user.user_permissions.add(
            Permission.objects.get(codename="flow_permission")
        )
        self.user = User.objects.get(pk=self.user.pk)

        self.assertFalse(user_has_activity_perm(self.user, start))

        self.user.user_permissions.add(
            Permission.objects.get(codename="activity_permission")
        )
        self.user = User.objects.get(pk=self.user.pk)

        self.assertTrue(user_has_activity_perm(self.user, start))

        self.user.user_permissions.remove(
            Permission.objects.get(codename="flow_permission")
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.assertFalse(user_has_activity_perm(self.user, start))


class ProcessPermissionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="user")

    def test_having_flow_perms_is_sufficient_for_having_any_perm(self):
        start = flow_permissions_test_flow.get_start_activity()
        start.start()
        start.finish()
        process = start.process

        self.assertFalse(user_has_any_process_perm(self.user, process))
        self.user.user_permissions.add(
            Permission.objects.get(codename="flow_permission")
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user_has_any_process_perm(self.user, process))

    def test_having_activity_perms_is_sufficient_for_having_any_perm(self):
        start = activity_permissions_test_flow.get_start_activity()
        start.start()
        start.finish()
        process = start.process

        self.assertFalse(user_has_any_process_perm(self.user, process))
        self.user.user_permissions.add(
            Permission.objects.get(codename="activity_permission")
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user_has_any_process_perm(self.user, process))

    def test_no_permissions_flow_does_not_require_any_perms(self):
        start = no_permissions_test_flow.get_start_activity()
        self.assertTrue(user_has_activity_perm(self.user, start))


class ProcesslibViewPermissionTest(TestCase):
    def setUp(self):
        self.user_without_perms = User.objects.create(username="user_perms")
        self.user_with_perms = User.objects.create(username="user_no_perms")
        self.user_with_perms.user_permissions.add(
            Permission.objects.get(codename="activity_permission")
        )
        self.user_with_perms.user_permissions.add(
            Permission.objects.get(codename="flow_permission")
        )
        self.start = combined_permissions_test_flow.get_start_activity()
        self.start.start()
        self.start.finish()
        self.process = self.start.process

        self.get_no_permissions = RequestFactory().get("/")
        self.get_no_permissions.user = self.user_without_perms

        self.get_with_permissions = RequestFactory().get("/")
        self.get_with_permissions.user = self.user_with_perms

        self.post_no_permissions = RequestFactory().post("/")
        self.post_no_permissions.user = self.user_without_perms

        self.post_with_permissions = RequestFactory().post("/")
        self.post_with_permissions.user = self.user_with_perms

    def test_process_list_view_respects_flow_permission(self):
        no_perm_response = ProcessListView.as_view()(
            self.get_no_permissions,
        )
        self.assertNotContains(no_perm_response, self.process.pk)

        perm_response = ProcessListView.as_view()(
            self.get_with_permissions,
        )
        self.assertContains(perm_response, self.process.pk)

    def test_user_process_list_view_respects_flow_permission(self):
        no_perm_response = UserProcessListView.as_view()(
            self.get_no_permissions,
        )
        self.assertNotContains(no_perm_response, self.process.pk)

        perm_response = UserProcessListView.as_view()(
            self.get_with_permissions,
        )
        self.assertContains(perm_response, self.process.pk)

    def test_user_current_process_list_view_respects_flow_permission(self):
        no_perm_response = UserCurrentProcessListView.as_view()(
            self.get_no_permissions,
        )
        self.assertNotContains(no_perm_response, self.process.pk)

        perm_response = UserCurrentProcessListView.as_view()(
            self.get_with_permissions,
        )
        self.assertContains(perm_response, self.process.pk)

    def test_process_detail_view_raises_permission_denied_with_missing_permissions(
        self,
    ):
        with self.assertRaises(PermissionDenied):
            ProcessDetailView.as_view()(self.get_no_permissions, pk=self.process.id)
        response = ProcessDetailView.as_view()(
            self.get_with_permissions, pk=self.process.id
        )
        self.assertEqual(response.status_code, 200)

    def test_process_cancel_view_raises_permission_denied_with_missing_permissions(
        self,
    ):
        with self.assertRaises(PermissionDenied):
            ProcessCancelView.as_view()(self.get_no_permissions, pk=self.process.id)

        response = ProcessCancelView.as_view()(
            self.get_with_permissions, pk=self.process.id
        )
        self.assertEqual(response.status_code, 200)

    def test_process_cancel_shows_error_if_cancel_not_possible(self):
        self.process.status = self.process.STATUS_DONE
        self.process.save()  # can't cancel a done process

        response = ProcessCancelView.as_view()(
            self.post_with_permissions, pk=self.process.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("can not be canceled", response.rendered_content)

    def test_process_start_view_raises_permission_denied_with_missing_permissions(self):
        with self.assertRaises(PermissionDenied):
            ProcessStartView.as_view()(
                self.post_no_permissions, flow_label=self.process.flow_label
            )
        response = ProcessStartView.as_view()(
            self.post_with_permissions, flow_label=self.process.flow_label
        )
        self.assertEqual(response.status_code, 302)

    def test_process_activity_view_raises_permission_denied_with_missing_permissions(
        self,
    ):
        next_activity = next(get_current_activities_in_process(self.process))

        with self.assertRaises(PermissionDenied):
            ProcessActivityView.as_view()(
                self.get_no_permissions,
                flow_label=self.process.flow_label,
                activity_id=next_activity.instance.pk,
            )
        response = ProcessActivityView.as_view()(
            self.get_with_permissions,
            flow_label=self.process.flow_label,
            activity_id=next_activity.instance.pk,
        )
        self.assertEqual(response.status_code, 200)

    def test_undo_activity_view_raises_permission_denied_with_missing_permissions(self):
        with self.assertRaises(PermissionDenied):
            ActivityUndoView.as_view()(
                self.post_no_permissions,
                flow_label=self.process.flow_label,
                activity_id=self.start.instance.pk,
            )
        response = ActivityUndoView.as_view()(
            self.post_with_permissions,
            flow_label=self.process.flow_label,
            activity_id=self.start.instance.pk,
        )
        self.assertEqual(response.status_code, 302)

    def test_retry_activity_view_raises_permission_denied_with_missing_permissions(
        self,
    ):
        with self.assertRaises(PermissionDenied):
            ActivityRetryView.as_view()(
                self.post_no_permissions,
                flow_label=self.process.flow_label,
                activity_id=self.start.instance.pk,
            )
        response = ActivityRetryView.as_view()(
            self.post_with_permissions,
            flow_label=self.process.flow_label,
            activity_id=self.start.instance.pk,
        )
        self.assertEqual(response.status_code, 302)

    def test_cancel_activity_view_raises_permission_denied_with_missing_permissions(
        self,
    ):
        next_activity = next(get_current_activities_in_process(self.process))
        with self.assertRaises(PermissionDenied):
            ActivityCancelView.as_view()(
                self.post_no_permissions,
                flow_label=self.process.flow_label,
                activity_id=next_activity.instance.pk,
            )
        response = ActivityCancelView.as_view()(
            self.post_with_permissions,
            flow_label=self.process.flow_label,
            activity_id=next_activity.instance.pk,
        )
        self.assertEqual(response.status_code, 302)

    def test_process_viewset_requires_permission_to_start_flow(self):
        data = {"flow_label": self.process.flow_label}

        post_with_permissions = RequestFactory().post("/", data=data)
        post_with_permissions.user = self.user_with_perms
        post_with_permissions._dont_enforce_csrf_checks = True

        post_without_permissions = RequestFactory().post("/", data=data)
        post_without_permissions.user = self.user_without_perms
        post_without_permissions._dont_enforce_csrf_checks = True

        response = ProcessViewSet.as_view({"post": "create"})(post_without_permissions)
        self.assertEqual(response.status_code, 403)

        response = ProcessViewSet.as_view({"post": "create"})(post_with_permissions)
        self.assertEqual(response.status_code, 201)


view_test_flow = (
    Flow("view_test_flow")
    .start_with("start", StartActivity)
    .and_then("view_one", ViewActivity, view=ProcessUpdateView.as_view(fields=[]))
    .and_then("view_two", ViewActivity, view=ProcessUpdateView.as_view(fields=[]))
    .and_then("end", EndActivity)
)


class ProcesslibViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.user.set_password("password")
        self.user.save()

        self.start = view_test_flow.get_start_activity()
        self.start.start()
        self.start.finish()
        self.process = self.start.process
        self.next_activity = next(get_current_activities_in_process(self.process))

        self.get = RequestFactory().get("/")
        self.get.user = self.user
        self.client.login(username="testuser", password="password")

    def test_activity_cancel_view_records_modified_by(self):
        activity_instance = self.next_activity.instance
        url = reverse(
            "processlib:activity-cancel",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(activity_instance.modified_by, None)
        activity_instance.refresh_from_db()
        self.assertEqual(activity_instance.modified_by, self.user)

    def test_activity_undo_view_records_modified_by(self):
        activity_instance = self.start.instance
        url = reverse(
            "processlib:activity-undo",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(activity_instance.modified_by, None)
        activity_instance.refresh_from_db()
        self.assertEqual(activity_instance.modified_by, self.user)

    def test_process_start_view_records_modified_by(self):
        url = reverse(
            "processlib:process-start", kwargs={"flow_label": view_test_flow.label}
        )
        self.assertIsNone(
            view_test_flow.activity_model._default_manager.filter(
                modified_by=self.user
            ).first()
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.assertIsNotNone(
            view_test_flow.activity_model._default_manager.filter(
                modified_by=self.user
            ).first()
        )

    def test_process_cancel_form(self):
        form = ProcessCancelForm(data={}, instance=self.process, user=self.user)
        self.assertTrue(form.is_valid())

    def test_process_cancel_form_shows_error_if_can_not_cancel(self):
        self.process.status = self.process.STATUS_DONE
        self.process.save()

        form = ProcessCancelForm(data={}, instance=self.process, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("You can't cancel", form.errors["__all__"][0])

    def test_process_cancel_view_records_modified_by(self):
        url = reverse("processlib:process-cancel", kwargs={"pk": self.process.id})
        self.assertIsNone(
            view_test_flow.activity_model._default_manager.filter(
                modified_by=self.user
            ).first()
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.assertIsNotNone(
            view_test_flow.activity_model._default_manager.filter(
                status=ActivityInstance.STATUS_CANCELED, modified_by=self.user
            ).first()
        )

    def test_activity_mixin_records_modified_by(self):
        activity_instance = self.next_activity.instance
        url = reverse(
            "processlib:process-activity",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        response = self.client.post(url, {"_finish": True})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(activity_instance.modified_by, None)
        activity_instance.refresh_from_db()
        self.assertEqual(activity_instance.modified_by, self.user)

    def test_not_finishing_redirects_to_current_activity(self):
        activity_instance = self.next_activity.instance
        url = reverse(
            "processlib:process-activity",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        response = self.client.post(url)
        self.assertRedirects(response, url)

    def test_finishing_process_works(self):
        activity_instance = self.next_activity.instance
        url = reverse(
            "processlib:process-activity",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        self.client.post(url, {"_finish": True})

        activity_instance = next(
            get_current_activities_in_process(self.process)
        ).instance
        url = reverse(
            "processlib:process-activity",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        self.client.post(url, {"_finish": True})
        self.process.refresh_from_db()
        self.assertEqual(self.process.status, self.process.STATUS_DONE)

    def test_go_to_next(self):
        activity_instance = self.next_activity.instance
        url = reverse(
            "processlib:process-activity",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        response = self.client.post(url, data={"_finish_go_to_next": "true"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse(
                "processlib:process-activity",
                kwargs={
                    "flow_label": self.process.flow_label,
                    "activity_id": next(
                        get_current_activities_in_process(self.process)
                    ).instance.id,
                },
            ),
        )

    def test_process_viewset_create_records_modified_by(self):
        data = {"flow_label": view_test_flow.label}

        post = RequestFactory().post("/", data=data)
        post.user = self.user
        post._dont_enforce_csrf_checks = True

        response = ProcessViewSet.as_view({"post": "create"})(post)
        self.assertEqual(response.status_code, 201)

        self.assertIsNotNone(
            view_test_flow.activity_model._default_manager.filter(
                activity_name="start", modified_by=self.user
            ).first()
        )

    def test_process_list(self):
        url = reverse(
            "processlib:process-list",
        )
        response = self.client.get(url)

        self.assertContains(response, "view_test_flow")
        self.assertContains(response, str(self.process.pk))


end_direct_test_flow = (
    Flow("end_direct_test_flow")
    .start_with("start", StartActivity)
    .and_then(
        "success-view",
        ViewActivity,
        view=ProcessUpdateView.as_view(
            fields=[],
            success_url=lambda a: "/custom/{}".format(a),
        ),
    )
    .and_then("end", EndActivity)
)


class ProcesslibRedirectViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.user.set_password("password")
        self.user.save()

        self.start = end_direct_test_flow.get_start_activity()
        self.start.start()
        self.start.finish()
        self.process = self.start.process
        self.next_activity = next(get_current_activities_in_process(self.process))

        self.get = RequestFactory().get("/")
        self.get.user = self.user
        self.client.login(username="testuser", password="password")

    def test_end_redirect(self):
        activity_instance = self.next_activity.instance
        url = reverse(
            "processlib:process-activity",
            kwargs={
                "flow_label": self.process.flow_label,
                "activity_id": activity_instance.id,
            },
        )
        response = self.client.post(url, {"_finish_go_to_next": True})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/custom/success-view")

        self.process.refresh_from_db()

        self.assertIsNotNone(self.process.finished_at)


class ActivityTest(TestCase):
    def test_function_activity_with_error_records_error(self):
        function_error_flow = (
            Flow("function_error_flow")
            .start_with("start", StartActivity)
            .and_then("function", FunctionActivity, callback=lambda activity: 1 / 0)
            .and_then("end", EndActivity)
        )
        start = function_error_flow.get_start_activity()
        start.start()
        with self.assertLogs("processlib.activity", level="ERROR"):
            start.finish()

        activity_instance = start.process._activity_instances.get(
            activity_name="function"
        )
        self.assertEqual(activity_instance.status, ActivityInstance.STATUS_ERROR)

    def test_function_activity_with_error_retry(self):
        function_error_retry_flow = (
            Flow("function_error_retry_flow")
            .start_with("start", StartActivity)
            .and_then("function", FunctionActivity, callback=lambda activity: 1 / 0)
            .and_then("end", EndActivity)
        )
        start = function_error_retry_flow.get_start_activity()
        start.start()
        with self.assertLogs("processlib.activity", level="ERROR"):
            start.finish()

        activity_instance = start.process._activity_instances.get(
            activity_name="function"
        )

        def working_callback(activity):
            activity.instance.assigned_group = Group.objects.create(name="side-effect")
            activity.instance.save()

        function_error_retry_flow._activity_kwargs["function"]["callback"] = (
            working_callback
        )

        activity_instance.activity.retry()
        activity_instance.refresh_from_db()
        self.assertEqual(activity_instance.status, ActivityInstance.STATUS_DONE)
        self.assertEqual(activity_instance.assigned_group.name, "side-effect")

    def test_has_active_successors(self):
        flow = (
            Flow("test_successors_flow")
            .start_with("start", StartActivity)
            .and_then("next", Activity)
        )
        start_activity = flow.get_start_activity()
        start_instance = start_activity.instance
        start_activity.start()
        start_activity.finish()

        # Successor 'next' is instantiated
        next_instance = start_instance.process._activity_instances.get(activity_name="next")
        self.assertTrue(start_instance.has_active_successors)

        # Test different statuses
        for status in [
            ActivityInstance.STATUS_INSTANTIATED,
            ActivityInstance.STATUS_SCHEDULED,
            ActivityInstance.STATUS_STARTED,
            ActivityInstance.STATUS_DONE,
            ActivityInstance.STATUS_ERROR,
        ]:
            next_instance.status = status
            next_instance.save()
            self.assertTrue(
                start_instance.has_active_successors, f"Failed for status {status}"
            )

        next_instance.status = ActivityInstance.STATUS_CANCELED
        next_instance.save()
        self.assertFalse(start_instance.has_active_successors)

    def test_has_active_successors_empty(self):
        flow = Flow("test_no_successors_flow").start_with("start", StartActivity)
        start_activity = flow.get_start_activity()
        self.assertFalse(start_activity.instance.has_active_successors)

    def test_repr(self):
        flow = Flow("test_repr_flow").start_with("start", StartActivity)
        start_activity = flow.get_start_activity()
        self.assertEqual(
            repr(start_activity.instance), 'ActivityInstance(activity_name="start")'
        )

    def test_save_missing_name(self):
        flow = Flow("test_save_flow").start_with("start", StartActivity)
        with self.assertRaises(ValueError):
            ActivityInstance.objects.create(
                process=Process.objects.create(flow_label="test_save_flow")
            )


class ProcessTest(TestCase):
    def test_str(self):
        flow = Flow("test_str_flow").start_with("start", StartActivity)
        process = Process.objects.create(flow_label="test_str_flow")
        self.assertEqual(str(process), "test_str_flow")

        flow.verbose_name = "My Flow"
        self.assertEqual(str(process), "My Flow")

    def test_description_format(self):
        flow = Flow("test_desc_flow", description="Hello {process.flow_label}")
        flow.start_with("start", StartActivity)
        process = Process.objects.create(flow_label="test_desc_flow")
        self.assertEqual(process.description, f"Hello {process.flow_label}")


class ModelUtilsTest(TestCase):
    def test_validate_flow_label(self):
        Flow("valid_flow").start_with("start", StartActivity)
        validate_flow_label("valid_flow")

        with self.assertRaises(ValidationError):
            validate_flow_label("invalid_flow")

    def test_is_format_string(self):
        self.assertTrue(is_format_string("Hello {name}"))
        self.assertFalse(is_format_string("Hello name"))
        self.assertFalse(is_format_string(123))
        self.assertFalse(is_format_string("Hello }"))


class AsyncActivityTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            from celery import current_app

            current_app.config_from_object("django.conf:settings", namespace="CELERY")
        except ImportError:  # pragma: no cover
            pass

    def test_async_activity_with_error_records_error(self):
        function_error_flow = (
            Flow("async_error_flow")
            .start_with("start", StartActivity)
            .and_then("async", AsyncActivity, callback=lambda activity: 1 / 0)
            .and_then("end", EndActivity)
        )
        start = function_error_flow.get_start_activity()

        with self.assertLogs("processlib.tasks", level="ERROR"), transaction.atomic():
            start.start()
            start.finish()

        activity_instance = start.process._activity_instances.get(activity_name="async")
        self.assertEqual(activity_instance.status, ActivityInstance.STATUS_ERROR)

    def test_async_activity_with_error_retry(self):
        async_error_retry_flow = (
            Flow("async_error_retry_flow")
            .start_with("start", StartActivity)
            .and_then("async", AsyncActivity, callback=lambda activity: 1 / 0)
            .and_then("end", EndActivity)
        )
        start = async_error_retry_flow.get_start_activity()

        with self.assertLogs("processlib.tasks", level="ERROR"), transaction.atomic():
            start.start()
            start.finish()

        activity_instance = start.process._activity_instances.get(activity_name="async")

        def working_callback(activity):
            activity.instance.assigned_group = Group.objects.create(name="side-effect")
            activity.instance.save()

        async_error_retry_flow._activity_kwargs["async"]["callback"] = working_callback

        activity_instance.activity.retry()
        activity_instance.refresh_from_db()
        self.assertEqual(activity_instance.status, ActivityInstance.STATUS_DONE)
        self.assertEqual(activity_instance.assigned_group.name, "side-effect")


class TemplateTagsTest(TestCase):
    def test_get_user_current_process_count(self):
        user = User.objects.create(username="test_tag_user")
        Flow("test_tag_count_flow").start_with("start", StartActivity)
        process = Process.objects.create(flow_label="test_tag_count_flow")
        ActivityInstance.objects.create(
            process=process,
            activity_name="start",
            status=ActivityInstance.STATUS_INSTANTIATED,
            assigned_user=user,
        )

        count = processlib_tags.get_user_current_process_count(user)
        self.assertEqual(count, 1)

    def test_get_current_activities_in_process(self):
        Flow("test_tag_current_flow").start_with("start", StartActivity)
        process = Process.objects.create(flow_label="test_tag_current_flow")
        ActivityInstance.objects.create(
            process=process,
            activity_name="start",
            status=ActivityInstance.STATUS_INSTANTIATED,
        )

        activities = list(processlib_tags.get_current_activities_in_process(process))
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].name, "start")

    def test_get_activities_to_do(self):
        user = User.objects.create(username="test_todo_tag_user")
        flow = Flow("test_tag_todo_flow").start_with(
            "start", StartViewActivity, view=lambda x: x
        )
        process = Process.objects.create(flow_label="test_tag_todo_flow")
        ActivityInstance.objects.create(
            process=process,
            activity_name="start",
            status=ActivityInstance.STATUS_INSTANTIATED,
            assigned_user=user,
        )

        todo = list(processlib_tags.get_activities_to_do(user, process))
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo[0].name, "start")
