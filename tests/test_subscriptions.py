"""Тесты helpers статусов подписок."""

import pytest

from donor_base.constants import SubscriptionStatuses
from donor_base.subscriptions import (
    get_capitalized_by_group_id,
    get_group_by_capitalized,
)


def test_subscription_helpers_return_values_and_raise_for_unknown_group():
    """Кэшированные словари подписок работают для валидных и неизвестных id."""
    assert get_capitalized_by_group_id(
        SubscriptionStatuses.ACTIVE.group_id
    ) == SubscriptionStatuses.ACTIVE.capitalized
    assert get_group_by_capitalized(
        SubscriptionStatuses.LOST.capitalized
    ) == SubscriptionStatuses.LOST.group_id

    with pytest.raises(ValueError, match="Не удалось найти значение"):
        get_capitalized_by_group_id("unknown")
