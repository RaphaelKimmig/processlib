from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase, RequestFactory

from .activity import StartActivity, EndActivity, ViewActivity, Wait, StartViewActivity
from .assignment import inherit, nobody, request_user
from .flow import Flow
from .services import (get_user_processes, get_user_current_processes,
                       get_current_activities_in_process)
from .services import user_has_activity_perm, user_has_any_process_perm
from .views import (ProcessUpdateView, ProcessDetailView, ProcessCancelView,
                    ProcessStartView, ProcessActivityView, ActivityUndoView, ActivityRetryView,
                    ActivityCancelView, ProcessViewSet)

User = get_user_model()


class FlowTest(TestCase):
    def test_never_wait_for_conditional(self):
        flow = Flow(
            "flow_name",
        ).start_with(
            'optional', StartActivity, skip_if=lambda: True
        )

        with self.assertRaises(ValueError):
            flow.and_then('wait', Wait, wait_for=['optional'])

    def test_assignment_inheritance(self):
        user = User.objects.create(username='assigned')
        flow = Flow(
            "assign_inherit_flow",
        ).start_with(
            'start', StartActivity,
        ).and_then(
            'end', EndActivity,
            assign_to=inherit,
        )
        start = flow.get_start_activity(activity_instance_kwargs={
            'assigned_user': user,
        })
        process = start.process

        start.start()
        start.finish()

        self.assertEqual(process.activity_instances.get(activity_name='start').assigned_user, user)
        self.assertEqual(process.activity_instances.get(activity_name='end').assigned_user, user)

    def test_clear_assignment(self):
        user = User.objects.create(username='assigned')
        flow = Flow(
            "assign_clear_flow",
        ).start_with(
            'start', StartActivity,
        ).and_then(
            'end', EndActivity,
            assign_to=nobody,
        )
        start = flow.get_start_activity(activity_instance_kwargs={
            'assigned_user': user,
        })
        process = start.process

        start.start()
        start.finish()

        self.assertEqual(process.activity_instances.get(activity_name='start').assigned_user, user)
        self.assertEqual(process.activity_instances.get(activity_name='end').assigned_user, None)

    def test_request_user_assignment(self):
        user = User.objects.create(username='request_user')
        flow = Flow(
            "assign_request_user_flow",
        ).start_with(
            'start', StartViewActivity,
            view=ProcessUpdateView.as_view(fields=[]),
            assign_to=request_user,
        ).and_then(
            'end', EndActivity,
        )

        factory = RequestFactory()
        request = factory.post('/')
        request.user = user

        start = flow.get_start_activity(request=request)
        process = start.process

        start.dispatch(request)

        self.assertEqual(process.activity_instances.get(activity_name='start').assigned_user, user)


user_processes_test_flow = Flow(
    "user_processes_test_flow",
).start_with(
    'start', StartActivity,
).and_then(
    'view', ViewActivity,
    assign_to=nobody,
    view=ProcessUpdateView.as_view(),
).and_then(
    'end', EndActivity,
)


class UserProcessesTest(TestCase):
    def setUp(self):
        self.user_1 = User.objects.create(username='user_1')
        self.user_2 = User.objects.create(username='user_2')

        self.group_1 = Group.objects.create(name='group_1')
        self.group_both = Group.objects.create(name='group_both')

        self.user_1.groups.add(self.group_1)
        self.user_1.groups.add(self.group_both)
        self.user_2.groups.add(self.group_both)

    def test_get_processes_assigned_to_user(self):
        start = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={
                'assigned_user': self.user_1,
            }
        )
        start.start()
        start.finish()

        self.assertSequenceEqual([start.process], get_user_processes(self.user_1))
        self.assertSequenceEqual([], get_user_processes(self.user_2))

    def test_get_processes_assigned_to_user_group(self):
        start_1 = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={
                'assigned_group': self.group_1,
            }
        )
        start_1.start()
        start_1.finish()

        start_both = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={
                'assigned_group': self.group_both,
            }
        )
        start_both.start()
        start_both.finish()

        self.assertSequenceEqual([start_1.process, start_both.process],
                                 get_user_processes(self.user_1))
        self.assertSequenceEqual([start_both.process], get_user_processes(self.user_2))

    def test_assignment_to_multiple_users(self):
        start = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={
                'assigned_user': self.user_1,
            }
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
            activity_instance_kwargs={
                'assigned_user': self.user_1,
            }
        )
        start.start()
        start.finish()

        next_activity = next(get_current_activities_in_process(start.process))
        next_activity.start()
        next_activity.finish()

        process = start.process
        process.refresh_from_db()

        self.assertEqual(start.process.status, start.process.STATUS_FINISHED)
        self.assertSequenceEqual([], get_user_current_processes(self.user_1))

    def test_get_current_processes_assigned_to_user_excludes_finished_activities(self):
        start = user_processes_test_flow.get_start_activity(
            activity_instance_kwargs={
                'assigned_user': self.user_1,
            }
        )
        start.start()
        start.finish()
        process = start.process
        process.refresh_from_db()

        self.assertEqual(start.instance.assigned_user, self.user_1)
        self.assertNotEqual(process.status, process.STATUS_FINISHED)

        self.assertSequenceEqual([], get_user_current_processes(self.user_1))


no_permissions_test_flow = Flow(
    "no_permissions_test_flow",
).start_with(
    'start', StartActivity,
).and_then(
    'end', EndActivity,
)

flow_permissions_test_flow = Flow(
    "flow_permissions_test_flow",
    permission='processlib.flow_permission',
).start_with(
    'start', StartActivity,
).and_then(
    'view', ViewActivity, view=ProcessUpdateView.as_view(),
).and_then(
    'end', EndActivity,
)

activity_permissions_test_flow = Flow(
    "activity_permissions_test_flow",
).start_with(
    'start', StartActivity,
    permission='processlib.activity_permission'
).and_then(
    'view', ViewActivity, view=ProcessUpdateView.as_view(),
).and_then(
    'end', EndActivity,
)

combined_permissions_test_flow = Flow(
    "combined_permissions_test_flow",
    permission='processlib.flow_permission',
).start_with(
    'start', StartActivity,
    permission='processlib.activity_permission'
).and_then(
    'view', ViewActivity, view=ProcessUpdateView.as_view(fields=[]),
).and_then(
    'end', EndActivity,
)


class ActivityPermissionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='user')

    def test_no_permissions_flow_requires_no_permissions(self):
        start = no_permissions_test_flow.get_start_activity()
        self.assertTrue(user_has_activity_perm(self.user, start))

    def test_activity_perms_default_to_flow_perms(self):
        start = flow_permissions_test_flow.get_start_activity()
        self.assertFalse(user_has_activity_perm(self.user, start))
        self.user.user_permissions.add(Permission.objects.get(codename='flow_permission'))
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user_has_activity_perm(self.user, start))

    def test_activity_perms_work(self):
        start = activity_permissions_test_flow.get_start_activity()
        self.assertFalse(user_has_activity_perm(self.user, start))
        self.user.user_permissions.add(Permission.objects.get(codename='activity_permission'))
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

        self.user.user_permissions.add(Permission.objects.get(codename='flow_permission'))
        self.user = User.objects.get(pk=self.user.pk)

        self.assertFalse(user_has_activity_perm(self.user, start))

        self.user.user_permissions.add(Permission.objects.get(codename='activity_permission'))
        self.user = User.objects.get(pk=self.user.pk)

        self.assertTrue(user_has_activity_perm(self.user, start))


class ProcessPermissionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='user')

    def test_having_flow_perms_is_sufficient_for_having_any_perm(self):
        start = flow_permissions_test_flow.get_start_activity()
        start.start()
        start.finish()
        process = start.process

        self.assertFalse(user_has_any_process_perm(self.user, process))
        self.user.user_permissions.add(Permission.objects.get(codename='flow_permission'))
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user_has_any_process_perm(self.user, process))

    def test_having_activity_perms_is_sufficient_for_having_any_perm(self):
        start = activity_permissions_test_flow.get_start_activity()
        start.start()
        start.finish()
        process = start.process

        self.assertFalse(user_has_any_process_perm(self.user, process))
        self.user.user_permissions.add(Permission.objects.get(codename='activity_permission'))
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user_has_any_process_perm(self.user, process))

    def test_no_permissions_flow_does_not_require_any_perms(self):
        start = no_permissions_test_flow.get_start_activity()
        self.assertTrue(user_has_activity_perm(self.user, start))


class ProcesslibViewPermissionTest(TestCase):
    def setUp(self):
        self.user_without_perms = User.objects.create(username='user_perms')
        self.user_with_perms = User.objects.create(username='user_no_perms')
        self.user_with_perms.user_permissions.add(
            Permission.objects.get(codename='activity_permission'))
        self.user_with_perms.user_permissions.add(
            Permission.objects.get(codename='flow_permission'))
        self.start = combined_permissions_test_flow.get_start_activity()
        self.start.start()
        self.start.finish()
        self.process = self.start.process

        self.get_no_permissions = RequestFactory().get('/')
        self.get_no_permissions.user = self.user_without_perms

        self.get_with_permissions = RequestFactory().get('/')
        self.get_with_permissions.user = self.user_with_perms

        self.post_no_permissions = RequestFactory().post('/')
        self.post_no_permissions.user = self.user_without_perms

        self.post_with_permissions = RequestFactory().post('/')
        self.post_with_permissions.user = self.user_with_perms

    def test_process_detail_view_raises_permission_denied_with_missing_permissions(self):
        with self.assertRaises(PermissionDenied):
            ProcessDetailView.as_view()(self.get_no_permissions, pk=self.process.pk)
        response = ProcessDetailView.as_view()(self.get_with_permissions, pk=self.process.pk)
        self.assertEqual(response.status_code, 200)

    def test_process_cancel_view_raises_permission_denied_with_missing_permissions(self):
        with self.assertRaises(PermissionDenied):
            ProcessCancelView.as_view()(self.get_no_permissions, pk=self.process.pk)

        response = ProcessCancelView.as_view()(self.get_with_permissions, pk=self.process.pk)
        self.assertEqual(response.status_code, 200)

    def test_process_start_view_raises_permission_denied_with_missing_permissions(self):
        with self.assertRaises(PermissionDenied):
            ProcessStartView.as_view()(self.post_no_permissions,
                                       flow_label=self.process.flow_label)
        response = ProcessStartView.as_view()(self.post_with_permissions,
                                              flow_label=self.process.flow_label)
        self.assertEqual(response.status_code, 302)

    def test_process_activity_view_raises_permission_denied_with_missing_permissions(self):
        next_activity = next(get_current_activities_in_process(self.process))

        with self.assertRaises(PermissionDenied):
            ProcessActivityView.as_view()(self.get_no_permissions,
                                          flow_label=self.process.flow_label,
                                          activity_id=next_activity.instance.pk)
        response = ProcessActivityView.as_view()(self.get_with_permissions,
                                                 flow_label=self.process.flow_label,
                                                 activity_id=next_activity.instance.pk)
        self.assertEqual(response.status_code, 200)

    def test_undo_activity_view_raises_permission_denied_with_missing_permissions(self):
        with self.assertRaises(PermissionDenied):
            ActivityUndoView.as_view()(self.post_no_permissions,
                                       flow_label=self.process.flow_label,
                                       activity_id=self.start.instance.pk)
        response = ActivityUndoView.as_view()(self.post_with_permissions,
                                              flow_label=self.process.flow_label,
                                              activity_id=self.start.instance.pk)
        self.assertEqual(response.status_code, 302)

    def test_retry_activity_view_raises_permission_denied_with_missing_permissions(self):
        with self.assertRaises(PermissionDenied):
            ActivityRetryView.as_view()(self.post_no_permissions,
                                        flow_label=self.process.flow_label,
                                        activity_id=self.start.instance.pk)
        response = ActivityRetryView.as_view()(self.post_with_permissions,
                                               flow_label=self.process.flow_label,
                                               activity_id=self.start.instance.pk)
        self.assertEqual(response.status_code, 302)

    def test_cancel_activity_view_raises_permission_denied_with_missing_permissions(self):
        next_activity = next(get_current_activities_in_process(self.process))
        with self.assertRaises(PermissionDenied):
            ActivityCancelView.as_view()(self.post_no_permissions,
                                         flow_label=self.process.flow_label,
                                         activity_id=next_activity.instance.pk)
        response = ActivityCancelView.as_view()(self.post_with_permissions,
                                                flow_label=self.process.flow_label,
                                                activity_id=next_activity.instance.pk)
        self.assertEqual(response.status_code, 302)

    def test_process_viewset_requires_permission_to_start_flow(self):
        data = {'flow_label': self.process.flow_label}

        post_with_permissions = RequestFactory().post('/', data=data)
        post_with_permissions.user = self.user_with_perms
        post_with_permissions._dont_enforce_csrf_checks = True

        post_without_permissions = RequestFactory().post('/', data=data)
        post_without_permissions.user = self.user_without_perms
        post_without_permissions._dont_enforce_csrf_checks = True

        response = ProcessViewSet.as_view({'post': 'create'})(post_without_permissions)
        self.assertEqual(response.status_code, 403)

        response = ProcessViewSet.as_view({'post': 'create'})(post_with_permissions)
        self.assertEqual(response.status_code, 201)
