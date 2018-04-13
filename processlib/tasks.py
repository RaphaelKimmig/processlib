import warnings
from logging import getLogger

from processlib.services import get_activity_for_flow

logger = getLogger(__name__)


try:
    from celery import shared_task
except ImportError:
    warnings.warn("Celery is requried for running shared tasks")
    def shared_task(**kwargs):
        def wrap(f):
            setattr(f, 'delay', f)
            return f
        return wrap


@shared_task(name='run_async_activity')
def run_async_activity(flow_label, activity_instance_id):
    activity = get_activity_for_flow(flow_label, activity_instance_id=activity_instance_id)
    try:
        activity.start()
        activity.finish()
    except Exception as e:
        logger.exception(e)
        activity.error(exception=e)

