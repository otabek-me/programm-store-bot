from types import SimpleNamespace

import pytest

from utils.permissions import AdminOnly, is_admin


def test_admin_ids_are_checked_exactly():
    assert is_admin(123, frozenset({123, 456}))
    assert not is_admin(999, frozenset({123, 456}))
    assert not is_admin(None, frozenset({123, 456}))


@pytest.mark.asyncio
async def test_non_admin_fails_admin_filter():
    guard = AdminOnly(frozenset({123}))
    admin_event = SimpleNamespace(from_user=SimpleNamespace(id=123))
    user_event = SimpleNamespace(from_user=SimpleNamespace(id=456))
    assert await guard(admin_event)
    assert not await guard(user_event)
