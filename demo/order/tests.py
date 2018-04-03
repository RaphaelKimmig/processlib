from django.urls import reverse
from django_webtest import WebTest

from order.models import OrderConfig, OrderProcess


class OrderTest(WebTest):
    def test_view_order_process_first_step_is_visible(self):
        config = OrderConfig.objects.create(
            available_articles='12345,67890', ask_for_token=True, require_token=False,
        )
        response = self.app.get(reverse('order-process', kwargs={'config_id': config.pk}))
        self.assertContains(response, 'You can find your token on the print thing.')

    def test_passing_first_step_stores_state(self):
        config = OrderConfig.objects.create(
            available_articles='12345,67890', ask_for_token=True, require_token=False,
        )
        response = self.app.get(reverse('order-process', kwargs={'config_id': config.pk}))

        form = response.form
        form['token'] = 'DEADBEEF'
        next_step = form.submit()

        process = OrderProcess.objects.get()

        self.assertContains(next_step.follow(), process.id)
        self.assertEqual(process.token, 'DEADBEEF')
        self.assertTrue(OrderProcess.objects.filter(token='DEADBEEF').exists())

    def test_require_token_enforces_token_required(self):
        config = OrderConfig.objects.create(
            available_articles='12345,67890', ask_for_token=True, require_token=True,
        )
        response = self.app.get(reverse('order-process', kwargs={'config_id': config.pk}))

        form = response.form
        form['token'] = ''
        response = form.submit()

        self.assertFormError(response, 'form', 'token', ['This field is required.'])

    def test_require_token_allows_no_token(self):
        config = OrderConfig.objects.create(
            available_articles='12345,67890', ask_for_token=True, require_token=False,
        )
        response = self.app.get(reverse('order-process', kwargs={'config_id': config.pk}))

        form = response.form
        form['token'] = ''
        response = form.submit()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(OrderProcess.objects.filter(token='').exists())
