from .constants import SubscriptionStatuses


_group_id2name_map: dict[str, SubscriptionStatuses] = {}


def get_name_by_group_id(group_id: str):
    if not _group_id2name_map:
        _group_id2name_map.update(
            {s.group_id: s for s in SubscriptionStatuses}
        )
    try:
        return _group_id2name_map[group_id]
    except KeyError:
        raise ValueError(f"Не удалось найти значение по группе {group_id}")
