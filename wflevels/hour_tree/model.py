"""Clock readings for the Hour Tree, independent of rendering."""


def reading(hour, minute):
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError('invalid local time')
    return {'completed_branches': hour % 12,
            'growing_branch': (hour % 12) + 1,
            'leaves': minute // 5,
            'buds': minute % 5}
