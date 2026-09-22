from donor_base.constants import SubscriptionStatuses

_group_id2name_map: dict[str, SubscriptionStatuses] = {}
_capitalized2group_id: dict[str, SubscriptionStatuses] = {}


def get_capitalized_by_group_id(group_id: str):
    """Словарь с кэшем для получения capitalized значения по id группы."""
    if not _group_id2name_map:
        _group_id2name_map.update(
            {sub.group_id: sub for sub in SubscriptionStatuses},
        )
    try:
        return _group_id2name_map[group_id].capitalized
    except KeyError as error:
        raise ValueError(
            f"Не удалось найти значение по группе {group_id}",
        ) from error


def get_group_by_capitalized(capitalized: str):
    """Словарь с кэшем для получения id группы значения по capitalized."""
    if not _capitalized2group_id:
        _capitalized2group_id.update(
            {sub.capitalized: sub for sub in SubscriptionStatuses},
        )
    try:
        return _capitalized2group_id[capitalized].group_id
    except KeyError as error:
        raise ValueError(
            f"Не удалось найти значение по capitalized {capitalized}",
        ) from error
