"""Ledger tests: key handling, reserve/settle idempotency, concurrency, insufficient balance."""

from __future__ import annotations

import threading

import pytest

from merlin_cli.proxy.metering import ModelPrice, Usage
from merlin_cli.proxy.tenants import LedgerStore, Meter

PRICE = ModelPrice(in_micros_per_m=1_000_000, out_micros_per_m=2_000_000)


@pytest.fixture()
def store(tmp_path):
    with LedgerStore(tmp_path / "ledger.db") as s:
        s.set_price("test-model", PRICE.in_micros_per_m, PRICE.out_micros_per_m)
        yield s


def _tenant(store: LedgerStore, name: str = "acme", micros: int = 10_000) -> tuple[str, str]:
    tenant_id = store.create_tenant(name, initial_micros=micros)
    return tenant_id, store.issue_key(tenant_id, label="default")


def _key(store: LedgerStore, token: str):
    record = store.resolve(token)
    assert record is not None, "key should resolve"
    return record


def test_issue_and_resolve_key(store: LedgerStore) -> None:
    tenant_id, token = _tenant(store)
    assert token.startswith("mk_")
    rec = store.resolve(token)
    assert rec is not None and rec.tenant_id == tenant_id
    assert store.resolve("mk_not-a-real-key") is None
    assert store.resolve("") is None


def test_revoked_key_stops_resolving(store: LedgerStore) -> None:
    _, token = _tenant(store)
    assert store.revoke_key(token) is True
    assert store.resolve(token) is None
    assert store.revoke_key(token) is False


def test_settle_charges_exact_cost_and_releases_hold(store: LedgerStore) -> None:
    tenant_id, token = _tenant(store)
    key = _key(store, token)
    hold = store.reserve(key, "test-model", "req_1", 5_000)
    assert hold is not None
    assert store.available(tenant_id) == 5_000  # 10_000 - 5_000 held

    result = store.settle(hold, Usage(prompt_tokens=100, completion_tokens=50), PRICE)
    assert result.duplicate is False
    assert result.cost_micros == 100 * 1 + 50 * 2  # 200 micros
    assert store.balance(tenant_id) == 10_000 - 200
    assert store.available(tenant_id) == 10_000 - 200  # reservation released


def test_settle_is_idempotent_per_request_id(store: LedgerStore) -> None:
    tenant_id, token = _tenant(store)
    key = _key(store, token)
    hold = store.reserve(key, "test-model", "req_dup", 5_000)
    assert hold is not None
    first = store.settle(hold, Usage(prompt_tokens=100, completion_tokens=50), PRICE)
    balance_after_first = store.balance(tenant_id)

    # A client retry re-holds under the same request id and settles again.
    retry_hold = store.reserve(key, "test-model", "req_dup", 5_000)
    assert retry_hold is not None
    second = store.settle(retry_hold, Usage(prompt_tokens=100, completion_tokens=50), PRICE)

    assert first.cost_micros == 200
    assert second.duplicate is True
    assert second.cost_micros == 0
    assert store.balance(tenant_id) == balance_after_first
    assert len(store.recent_usage(tenant_id)) == 1


def test_reserve_refuses_when_balance_too_small(store: LedgerStore) -> None:
    tenant_id, token = _tenant(store, micros=100)
    key = _key(store, token)
    assert store.reserve(key, "test-model", "req_broke", 101) is None
    assert store.available(tenant_id) == 100


def test_release_refunds_the_hold(store: LedgerStore) -> None:
    tenant_id, token = _tenant(store)
    key = _key(store, token)
    hold = store.reserve(key, "test-model", "req_rel", 4_000)
    assert hold is not None
    assert store.release(hold) is True
    assert store.release(hold) is False  # already gone
    assert store.available(tenant_id) == 10_000


def test_concurrent_reserves_never_oversell(store: LedgerStore) -> None:
    """10 threads racing for 1_000 micros each against a 5_000 balance: exactly 5 win."""
    tenant_id, token = _tenant(store, micros=5_000)
    key = _key(store, token)
    results: list[bool] = []
    lock = threading.Lock()

    def attempt(i: int) -> None:
        got = store.reserve(key, "test-model", f"req_race_{i}", 1_000) is not None
        with lock:
            results.append(got)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == 5
    assert store.available(tenant_id) == 0


def test_topup_appears_in_ledger_entries(store: LedgerStore) -> None:
    tenant_id, _ = _tenant(store, micros=0)
    assert store.balance(tenant_id) == 0
    store.credit(tenant_id, 50_000, reason="topup")
    entries = store.entries(tenant_id)
    assert entries[0]["reason"] == "topup"
    assert entries[0]["delta_micros"] == 50_000


def test_meter_uses_default_price_for_unlisted_model(store: LedgerStore) -> None:
    tenant_id = store.create_tenant("fallback", initial_micros=1_000)
    token = store.issue_key(tenant_id)
    meter = Meter(store, default_price=ModelPrice(500_000, 1_000_000))
    key = meter.authenticate(token)
    assert key is not None
    hold = meter.hold(key, "unlisted-model", "req_fb", Usage(prompt_tokens=100, completion_tokens=0))
    assert hold is not None
    assert hold.micros == 50  # 100 tokens @ $0.50/M
    assert meter.settle(hold, Usage(prompt_tokens=100, completion_tokens=0)).cost_micros == 50
