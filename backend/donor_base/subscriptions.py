from .constants import SubscriptionStatuses

_group_id2name_map: dict[str, SubscriptionStatuses] = {}
_capitalized2group_id: dict[str, SubscriptionStatuses] = {}


def get_capitalized_by_group_id(group_id: str):
    """
    Словарь с кэшированием для получения capitalized значения по ид группы.
    """
    if not _group_id2name_map:
        _group_id2name_map.update(
            {s.group_id: s for s in SubscriptionStatuses},
        )
    try:
        return _group_id2name_map[group_id].capitalized
    except KeyError:
        raise ValueError(f"Не удалось найти значение по группе {group_id}")


def get_group_by_capitalized(capitalized: str):
    """
    Словарь с кэшированием для получения ид группы значения по capitalized.
    """
    if not _capitalized2group_id:
        _capitalized2group_id.update(
            {s.capitalized: s for s in SubscriptionStatuses},
        )
    try:
        return _capitalized2group_id[capitalized].group_id
    except KeyError:
        raise ValueError(
            f"Не удалось найти значение по capitalized {capitalized}",
        )
