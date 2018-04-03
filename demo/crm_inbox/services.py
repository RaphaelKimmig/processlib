

def transmit_order_to_erp(erp_order_process):
    # FIXME - submit order to erp
    erp_order_process.erp_order_id = '1337'
    erp_order_process.save()


def update_campaign_step(campaign_process):
    # FIXME get campaign participation for the organisation/person and update to target values
    pass


def create_event_entry_for_process(process):
    person, organisation = process.person, process.organisation
    process.event_id = '12321'
    # FIXME we should have some kind of template / this info should come with the


def create_task_for_process(process):
    event = process.event
    task.create(event=event, group=process.task_group_id)

    # FIXME we should have some kind of template / this info should come with the
