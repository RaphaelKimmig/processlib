from order.forms import TokenForm, ArticlesForm, RecipientForm, ConfirmationForm
from order.models import OrderProcess
from processlib.activity import StartFormActivity, FormActivity, EndActivity
from processlib.flow import Flow


place_order_flow = Flow(
    name='place_order_flow', process_model=OrderProcess
).start_with(
    'token', StartFormActivity, form_class=TokenForm,
).and_then(
    'recipient', FormActivity, form_class=RecipientForm
).and_then(
    'articles', FormActivity, form_class=ArticlesForm
).and_then(
    'confirmation', FormActivity, form_class=ConfirmationForm
).and_then(
    'end', EndActivity
)

