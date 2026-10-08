"""Тесты helpers статусов подписок."""

import pytest

from donor_base.constants import SubscriptionStatuses
from donor_base.subscriptions import (
    get_capitalized_by_group_id,
    get_group_by_capitalized,
)


@pytest.mark.parametrize(
    "subscription",
    list(SubscriptionStatuses),
)
def test_subscription_helpers_map_known_values(
    subscription: SubscriptionStatuses,
) -> None:
    """Преобразования статуса и group ID взаимно обратны."""
    assert (
        get_capitalized_by_group_id(subscription.group_id)
        == subscription.capitalized
    )
    assert (
        get_group_by_capitalized(subscription.capitalized)
        == subscription.group_id
    )


def test_subscription_helpers_raise_for_unknown_values() -> None:
    """Оба helper-а отклоняют неизвестные значения."""
    with pytest.raises(ValueError, match="Не удалось найти значение"):
        get_capitalized_by_group_id("unknown")

    with pytest.raises(ValueError, match="Не удалось найти значение"):
        get_group_by_capitalized("unknown")
