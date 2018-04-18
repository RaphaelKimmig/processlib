from crm_inbox.models import DemoOrderProcess, CampaignParticipationProcess
from crm_inbox.services import (transmit_order_to_erp, update_campaign_step,
                                create_event_entry_for_process, create_task_for_process)
from crm_inbox.views import MatchOrganisationView, MatchPersonView
from processlib.activity import (ViewActivity, AsyncActivity, StartViewActivity, EndActivity,
                                 StartActivity, FunctionActivity, Wait, State)
from processlib.flow import Flow

erp_order_flow = Flow(
    "erp_order_flow",
    process_model=DemoOrderProcess,
    verbose_name='Process an order'
).start_with(
    'receive_order', StartActivity,
).and_then(
    'match_organisation', ViewActivity, view=MatchOrganisationView.as_view(),
    skip_if=lambda a: a.process.organisation is not None,
).and_then(
    'match_organisation_done', State
).add_activity(
    'match_person', ViewActivity, view=MatchPersonView.as_view(),
    after='receive_order',
    skip_if=lambda a: a.process.person is not None,
).and_then(
    'match_person_done', State
).and_then(
    'matching_done', Wait, wait_for=['match_person_done', 'match_organisation_done']
).and_then(
    'transmit_order', AsyncActivity, callback=lambda a: transmit_order_to_erp(a.process),
).and_then(
    'success', EndActivity
)


campaign_flow = Flow(
    'campaign_flow',
    process_model=CampaignParticipationProcess,
).start_with(
    'receive_via_api', StartActivity
).and_then(
    'match_organisation', ViewActivity, view=MatchOrganisationView.as_view(),
    skip_if=lambda a: not a.process.has_organisation_data() or a.process.organisation is not None,
).and_then(
    'match_person', ViewActivity, view=MatchPersonView.as_view(),
    skip_if=lambda a: not a.process.has_person_data() or a.process.person is not None,
).and_then(
    'update_campaign_participation', FunctionActivity,
    callback=lambda a: update_campaign_step(a.process),
    skip_if=lambda a: not a.process.target_campaign_id and a.process.target_step_id,
).and_then(
    'transmit_erp_order', AsyncActivity,
    callback=lambda a: transmit_order_to_erp(a.process),
    skip_if=lambda a: not a.process.has_erp_order()
).and_then(
    'create_event', FunctionActivity,
    callback=lambda a: create_event_entry_for_process(a.process),
    skip_if=lambda a: not a.process.event_title and not a.process.event_text
).and_then(
    'create_task', FunctionActivity,
    callback=lambda a: create_task_for_process(a.process),
    skip_if=lambda a: not a.process.task_group_id
).and_then(
    'success', EndActivity
)

view_start_flow = Flow(
    "view_start_flow",
    verbose_name='A flow with a view'
).start_with(
    'start', StartViewActivity,
).and_then(
    'success', EndActivity
)
