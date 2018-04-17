def nobody(user=None, predecessor=None):
    return None, None


def inherit(user=None, predecessor=None):
    if predecessor:
        return predecessor.instance.assigned_user, predecessor.instance.assigned_group
    return None, None
