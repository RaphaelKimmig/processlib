from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from activity import ViewActivity
from .activity import StartActivity, EndActivity, Wait
from .assignment import inherit, nobody
from .flow import Flow
from .services import (get_user_processes, cancel_process, get_user_current_processes,
                       get_current_activities_in_process)

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


user_processes_test_flow = Flow(
    "user_processes_test_flow",
).start_with(
    'start', StartActivity,
).and_then(
    'view', ViewActivity,
    assign_to=nobody,
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


