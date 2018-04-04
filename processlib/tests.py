from django.test import TestCase

from .activity import StartActivity, Wait
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
