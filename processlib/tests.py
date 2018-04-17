from django.contrib.auth import get_user_model
from django.test import TestCase


from .activity import StartActivity, EndActivity, Wait
from .assignment import inherit, nobody
from .flow import Flow


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
        user = get_user_model().objects.create(username='assigned')
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
        user = get_user_model().objects.create(username='assigned')
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
