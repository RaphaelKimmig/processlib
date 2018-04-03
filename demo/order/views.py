from django.urls import reverse

from order.models import OrderConfig
from processlib.views import LinearFormFlowView
from .flows import place_order_flow


class OrderViewForm(LinearFormFlowView):
    config_id = None
    flow = place_order_flow
    view_name = 'order-process'

    def get_config(self):
        return OrderConfig.objects.get(pk=self.kwargs['config_id'])

    def get_next_activity(self, **kwargs):
        kwargs['config'] = self.get_config()
        return super(OrderViewForm, self).get_next_activity(**kwargs)

    def get_next_url(self, control):
        return reverse(self.view_name, kwargs={
            'process_id': control.process.id,
            'config_id': control.process.config_id
        })
