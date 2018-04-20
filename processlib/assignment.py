def nobody(request_user=None, predecessor=None):
    return None, None


def inherit(request_user=None, predecessor=None):
    if predecessor:
        return predecessor.instance.assigned_user, predecessor.instance.assigned_group
    return None, None


def request_user(request_user=None, predecessor=None):
    return request_user, None
