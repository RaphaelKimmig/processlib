from django.test import TestCase
from django.urls import reverse
from django_webtest import WebTest

from crm_inbox.flows import erp_order_flow
from crm_inbox.models import Person, Organisation, EinfachpackenOrderProcess
from processlib.services import get_current_activities_in_process


class FlowTest(TestCase):
    def test_parallel_activities_allowed(self):
        start = erp_order_flow.get_start_activity()
        start.start()
        start.finish()
        up_next = {a.name for a in get_current_activities_in_process(start.process)}
        self.assertSetEqual(up_next, {'match_person', 'match_organisation'})

    def test_skip_person_waits_for_organisation(self):
        person = Person.objects.create()

        start = erp_order_flow.get_start_activity(
            person=person
        )
        start.start()
        start.finish()

        process = EinfachpackenOrderProcess.objects.get()

        up_next = list(get_current_activities_in_process(process))

        self.assertSetEqual({a.name for a in up_next}, {'match_organisation', 'matching_done'})

    def test_start_process_with_attributes(self):
        person = Person.objects.create()
        organisation = Organisation.objects.create()

        start = erp_order_flow.get_start_activity(
            organisation=organisation,
            person=person,
        )

        start.start()
        start.finish()

        process = EinfachpackenOrderProcess.objects.get()

        self.assertEqual(process.person, person)
        self.assertEqual(process.organisation, organisation)

    def test_skip_organisation(self):
        organisation = Organisation.objects.create()

        start = erp_order_flow.get_start_activity(
            organisation=organisation,
        )
        start.start()
        start.finish()

        process = EinfachpackenOrderProcess.objects.get()

        up_next = list(get_current_activities_in_process(process))

        self.assertSetEqual({a.name for a in up_next}, {'match_person', 'matching_done'})

    def test_skip_organisation_and_person(self):
        organisation = Organisation.objects.create()
        person = Person.objects.create()

        start = erp_order_flow.get_start_activity(
            organisation=organisation,
            person=person,
        )
        start.start()
        start.finish()

        process = EinfachpackenOrderProcess.objects.get()

        self.assertTrue(process.activity_instances.filter(activity_name='transmit_order').exists())

    def test_transmit_order(self):
        organisation = Organisation.objects.create()
        person = Person.objects.create()

        start = erp_order_flow.get_start_activity()
        start.start()
        start.finish()
        process = start.process

        match_organisation = next(get_current_activities_in_process(process))
        match_organisation.start()
        process.organisation = organisation
        process.save()
        match_organisation.finish()

        match_person = next(get_current_activities_in_process(process))
        match_person.start()
        process.person = person
        process.save()
        match_person.finish()

        process.refresh_from_db()

        self.assertIsNotNone(
            process.activity_instances.get(activity_name='transmit_order').finished_at
        )
        self.assertEqual(process.erp_order_id, '1337')

    def test_undo_organisation(self):
        organisation = Organisation.objects.create()

        start = erp_order_flow.get_start_activity()
        start.start()
        start.finish()

        process = EinfachpackenOrderProcess.objects.get()
        match_organisation = next(get_current_activities_in_process(process))

        match_organisation.start()
        match_organisation.process.organisation = organisation
        match_organisation.finish()

        self.assertEqual(next(get_current_activities_in_process(process)).name, 'match_person')

        next(get_current_activities_in_process(process)).cancel()
        match_organisation.undo()

        self.assertEqual(next(get_current_activities_in_process(process)).name, 'match_organisation')


class SimpleViewTest(WebTest):
    def setUp(self):
        start = erp_order_flow.get_start_activity()
        start.start()
        start.finish()
        self.process_1 = start.process

        start = erp_order_flow.get_start_activity()
        start.start()
        start.finish()
        self.process_2 = start.process

    def test_process_list_contains_processes(self):
        process_list = self.app.get(reverse('process-list'))
        self.assertContains(process_list, self.process_1.id)
        self.assertContains(process_list, self.process_2.id)

    def test_process_list_links_detail(self):
        process_list = self.app.get(reverse('process-list'))
        detail_page = process_list.click(str(self.process_1.id))
        self.assertContains(detail_page, self.process_1.id)
        self.assertNotContains(detail_page, self.process_2.id)

    def test_detail_view_shows_id(self):
        process_detail = self.app.get(reverse('process-detail', args=(self.process_1.id, )))
        self.assertContains(process_detail, self.process_1.id)

    def test_list_view_allows_creating(self):
        process_list = self.app.get(reverse('process-list'))
        for form in process_list.forms.values():
            if "Start Process an order" in str(form.html):
                response = form.submit()
                break
        else:
            raise Exception("Form with start button not found")

        process = EinfachpackenOrderProcess.objects.latest('started_at')
        self.assertContains(response.follow(), process)


