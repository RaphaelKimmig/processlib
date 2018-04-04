import warnings

try:
    from celery import shared_task
except ImportError:
    warnings.warn("Celery is requried for running shared tasks")
    def shared_task(**kwargs):
        def wrap(f):
            setattr(f, 'delay', f)
            return f
        return wrap


from processlib.services import get_activity_for_flow


@shared_task(name='run_async_activity')
def run_async_activity(flow_label, activity_instance_id):
    activity = get_activity_for_flow(flow_label, activity_instance_id=activity_instance_id)
    activity.start()
    activity.finish()

