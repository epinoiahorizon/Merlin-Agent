"""Multi-tenant keys, prepaid balances and a double-entry-ish ledger for the metered proxy.

Design constraints that shaped this module:

* **Money is integer micros** (1e-6 USD) end to end. ``REAL`` balances drift and a relay bills
  thousands of times a day.
* **Reserve, then settle.** The cost of a request is only known after the upstream returns, so a
  hold is taken up front and released at settlement. Without it, N concurrent requests all pass an
  "is the balance positive?" check on the same 1 000 micros and the last N-1 are free.
* **Idempotent by ``request_id``.** Clients retry; proxies retry; SSE connections die and are
  re-opened. ``usage_events.request_id`` is the primary key, so a duplicate settle is a no-op.
* **Holds live in the database, not in memory.** A restart mid-stream must not leak a reservation
  forever.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from merlin_cli.proxy.metering import ModelPrice, Usage, cost_micros

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      INTEGER NOT NULL,
    balance_micros  INTEGER NOT NULL DEFAULT 0,
    reserved_micros INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash   TEXT PRIMARY KEY,
    tenant_id  TEXT NOT NULL,
    label      TEXT NOT NULL DEFAULT '',
    active     INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    model                    TEXT PRIMARY KEY,
    in_micros_per_m          INTEGER NOT NULL,
    out_micros_per_m         INTEGER NOT NULL,
    cache_read_micros_per_m  INTEGER,
    updated_at               INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS price_history (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    model                    TEXT NOT NULL,
    in_micros_per_m          INTEGER NOT NULL,
    out_micros_per_m         INTEGER NOT NULL,
    cache_read_micros_per_m  INTEGER,
    source                   TEXT NOT NULL DEFAULT 'manual',
    effective_from           INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS holds (
    request_id TEXT PRIMARY KEY,
    tenant_id  TEXT NOT NULL,
    key_hash   TEXT NOT NULL,
    model      TEXT NOT NULL,
    micros     INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_events (
    request_id        TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL,
    key_hash          TEXT NOT NULL,
    model             TEXT NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cost_micros       INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'ok',
    estimated         INTEGER NOT NULL DEFAULT 0,
    created_at        INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    TEXT NOT NULL,
    request_id   TEXT,
    delta_micros INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    amount_idr    INTEGER NOT NULL,
    amount_micros INTEGER NOT NULL,
    payload       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    INTEGER NOT NULL,
    expires_at    INTEGER,
    paid_at       INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_pending_amount
    ON invoices (amount_idr) WHERE status = 'pending';
CREATE TABLE IF NOT EXISTS payments (
    id          TEXT PRIMARY KEY,
    received_at INTEGER NOT NULL,
    amount_idr  INTEGER NOT NULL,
    invoice_id  TEXT,
    status      TEXT NOT NULL DEFAULT 'unmatched',
    provider    TEXT NOT NULL DEFAULT '',
    raw         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_tenant_time ON usage_events (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_tenant     ON ledger_entries (tenant_id, id DESC);
"""


def default_ledger_path() -> Path:
    """``MERLIN_PROXY_LEDGER`` wins; otherwise the per-user Merlin home."""
    override = os.environ.get("MERLIN_PROXY_LEDGER")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "merlin" / "proxy_ledger.db"
    return Path.home() / ".merlin" / "proxy_ledger.db"


def hash_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KeyRecord:
    key_hash: str
    tenant_id: str
    label: str


@dataclass(frozen=True)
class Hold:
    request_id: str
    tenant_id: str
    key_hash: str
    model: str
    micros: int


@dataclass(frozen=True)
class Settlement:
    request_id: str
    cost_micros: int
    duplicate: bool


class InsufficientBalance(RuntimeError):
    """Raised when a request cannot be authorised against the tenant's available balance."""


class DuplicateInvoiceAmount(RuntimeError):
    """Raised when a pending invoice already uses that exact nominal."""


# Ledger amounts are integer micros of whatever currency the deployment bills in. If that currency
# is rupiah, 1 IDR = 1 000 000 micros (see the dashboard's top-up flow).
MICROS_PER_UNIT = 1_000_000


class LedgerStore:
    """SQLite-backed tenant/key/price/usage store. Safe for one process, many threads."""

    def __init__(self, path: os.PathLike | str | None = None) -> None:
        self.path = Path(path) if path else default_ledger_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
            self._migrate()

    def _migrate(self) -> None:
        """Add columns that ``CREATE TABLE IF NOT EXISTS`` cannot add to an existing table.

        A deployed ledger predates later schema changes (``expires_at`` arrived with invoice TTLs);
        without this, an upgraded binary crashes on the first statement that touches the new column
        while a fresh install works — the classic "only fails in production" bug.
        """
        wanted = {
            "invoices": {"expires_at": "INTEGER", "paid_at": "INTEGER"},
            "payments": {"provider": "TEXT NOT NULL DEFAULT ''"},
        }
        for table, columns in wanted.items():
            existing = {row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if not existing:
                continue
            for name, declaration in columns.items():
                if name not in existing:
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    # -- lifecycle ---------------------------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "LedgerStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def _tx(self) -> "_Transaction":
        return _Transaction(self._conn, self._lock)

    # -- tenants & keys ----------------------------------------------------------------------
    def create_tenant(self, name: str, initial_micros: int = 0) -> str:
        tenant_id = "tn_" + secrets.token_hex(8)
        now = int(time.time())
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO tenants (id, name, created_at, balance_micros) VALUES (?, ?, ?, ?)",
                (tenant_id, name, now, int(initial_micros)),
            )
            if initial_micros:
                conn.execute(
                    "INSERT INTO ledger_entries (tenant_id, request_id, delta_micros, reason, created_at)"
                    " VALUES (?, NULL, ?, 'opening_balance', ?)",
                    (tenant_id, int(initial_micros), now),
                )
        return tenant_id

    def credit(self, tenant_id: str, micros: int, reason: str = "topup") -> int:
        """Top up (or, with a negative amount, correct) a balance. Returns the new balance."""
        if micros == 0:
            return self.balance(tenant_id)
        now = int(time.time())
        with self._tx() as conn:
            conn.execute(
                "UPDATE tenants SET balance_micros = balance_micros + ? WHERE id = ?", (int(micros), tenant_id)
            )
            conn.execute(
                "INSERT INTO ledger_entries (tenant_id, request_id, delta_micros, reason, created_at)"
                " VALUES (?, NULL, ?, ?, ?)",
                (tenant_id, int(micros), reason, now),
            )
        return self.balance(tenant_id)

    def find_tenant_by_name(self, name: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT id FROM tenants WHERE name = ? ORDER BY created_at LIMIT 1", (name,)
        ).fetchone()
        return str(row["id"]) if row else None

    # -- invoices (top-ups) -------------------------------------------------------------------
    def create_invoice(
        self, tenant_id: str, amount_idr: int, payload: str = "", ttl_s: int = 1800
    ) -> dict:
        """Pending invoice for an exact rupiah amount; raises when that amount is already pending.

        The pending-amount unique index is what makes unique-amount matching safe: two customers can
        never be told to pay the same nominal, so a bank/QRIS notification maps to exactly one
        invoice without needing a reference code inside the transfer.

        ``ttl_s`` bounds how long the nominal stays reserved; expired invoices release it.
        """
        amount_idr = int(amount_idr)
        if amount_idr <= 0:
            raise ValueError("invoice amount must be positive")
        invoice_id = "inv_" + secrets.token_hex(10)
        now = int(time.time())
        expires_at = now + int(ttl_s) if ttl_s and ttl_s > 0 else None
        try:
            with self._tx() as conn:
                conn.execute(
                    "INSERT INTO invoices (id, tenant_id, amount_idr, amount_micros, payload, status,"
                    " created_at, expires_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
                    (invoice_id, tenant_id, amount_idr, amount_idr * MICROS_PER_UNIT, payload, now, expires_at),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateInvoiceAmount(f"amount {amount_idr} already has a pending invoice") from exc
        invoice = self.invoice(invoice_id)
        assert invoice is not None
        return invoice

    def set_invoice_payload(self, invoice_id: str, payload: str) -> None:
        with self._tx() as conn:
            conn.execute("UPDATE invoices SET payload = ? WHERE id = ?", (payload, invoice_id))

    def invoice(self, invoice_id: str) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        return dict(row) if row else None

    def pending_invoices(self, tenant_id: Optional[str] = None) -> list[dict]:
        if tenant_id:
            rows = self._conn.execute(
                "SELECT * FROM invoices WHERE status = 'pending' AND tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM invoices WHERE status = 'pending' ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def pay_invoice(self, invoice_id: str) -> int:
        """Mark an invoice paid and credit its tenant. Idempotent: a second call credits nothing."""
        now = int(time.time())
        credited = 0
        with self._tx() as conn:
            row = conn.execute(
                "SELECT tenant_id, amount_micros, status FROM invoices WHERE id = ?", (invoice_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                return 0
            conn.execute(
                "UPDATE invoices SET status = 'paid', paid_at = ? WHERE id = ? AND status = 'pending'",
                (now, invoice_id),
            )
            conn.execute(
                "UPDATE tenants SET balance_micros = balance_micros + ? WHERE id = ?",
                (row["amount_micros"], row["tenant_id"]),
            )
            conn.execute(
                "INSERT INTO ledger_entries (tenant_id, request_id, delta_micros, reason, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (row["tenant_id"], invoice_id, row["amount_micros"], f"topup:{invoice_id}", now),
            )
            credited = int(row["amount_micros"])
        return credited

    def expire_invoices(self, now: Optional[int] = None) -> int:
        """Mark pending invoices past ``expires_at`` as expired, freeing their unique nominal."""
        moment = int(now if now is not None else time.time())
        expired = 0
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id FROM invoices WHERE status = 'pending' AND expires_at IS NOT NULL AND expires_at <= ?",
                (moment,),
            ).fetchall()
            for row in rows:
                conn.execute(
                    "UPDATE invoices SET status = 'expired' WHERE id = ? AND status = 'pending'", (row["id"],)
                )
                expired += 1
        return expired

    def find_pending_by_amount(self, amount_idr: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM invoices WHERE status = 'pending' AND amount_idr = ?", (int(amount_idr),)
        ).fetchone()
        return dict(row) if row else None

    # -- inbound payments (webhooks / manual reconciliation) -----------------------------------
    def record_payment(
        self,
        amount_idr: int,
        *,
        invoice_id: Optional[str] = None,
        status: str = "unmatched",
        provider: str = "",
        raw: str = "",
    ) -> dict:
        payment_id = "pay_" + secrets.token_hex(10)
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO payments (id, received_at, amount_idr, invoice_id, status, provider, raw)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (payment_id, int(time.time()), int(amount_idr), invoice_id, status, provider, raw[:4000]),
            )
        payment = self.payment(payment_id)
        assert payment is not None
        return payment

    def payment(self, payment_id: str) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        return dict(row) if row else None

    def payments(self, status: str = "", limit: int = 50) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM payments WHERE status = ? ORDER BY received_at DESC LIMIT ?", (status, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM payments ORDER BY received_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def claim_payment(self, payment_id: str, invoice_id: str) -> int:
        """Attach an unmatched payment to an invoice and credit it (manual reconciliation)."""
        payment = self.payment(payment_id)
        if payment is None or payment["status"] == "matched":
            return 0
        credited = self.pay_invoice(invoice_id)
        if not credited:
            return 0
        with self._tx() as conn:
            conn.execute(
                "UPDATE payments SET status = 'matched', invoice_id = ? WHERE id = ?", (invoice_id, payment_id)
            )
        return credited

    def issue_key(self, tenant_id: str, label: str = "") -> str:
        token = "mk_" + secrets.token_urlsafe(32)
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO api_keys (key_hash, tenant_id, label, active, created_at) VALUES (?, ?, ?, 1, ?)",
                (hash_key(token), tenant_id, label, int(time.time())),
            )
        return token

    def revoke_key(self, token: str) -> bool:
        changed = 0
        with self._tx() as conn:
            changed = conn.execute(
                "UPDATE api_keys SET active = 0 WHERE key_hash = ? AND active = 1", (hash_key(token),)
            ).rowcount
        return changed > 0

    def resolve(self, token: str) -> Optional[KeyRecord]:
        if not token:
            return None
        row = self._conn.execute(
            "SELECT key_hash, tenant_id, label FROM api_keys WHERE key_hash = ? AND active = 1",
            (hash_key(token),),
        ).fetchone()
        if row is None:
            return None
        return KeyRecord(key_hash=row["key_hash"], tenant_id=row["tenant_id"], label=row["label"])

    # -- pricing -----------------------------------------------------------------------------
    def set_price(
        self,
        model: str,
        in_micros_per_m: int,
        out_micros_per_m: int,
        cache_read_micros_per_m: Optional[int] = None,
        source: str = "manual",
    ) -> bool:
        """Upsert a model price. Returns ``True`` when the value changed (history row appended).

        Re-pricing to the identical numbers is a no-op by design: ``price_history`` must stay a
        record of *changes*, otherwise a nightly sync fills it with noise and hides real moves.
        """
        now = int(time.time())
        new = (int(in_micros_per_m), int(out_micros_per_m), cache_read_micros_per_m)
        changed = False
        with self._tx() as conn:
            row = conn.execute(
                "SELECT in_micros_per_m, out_micros_per_m, cache_read_micros_per_m FROM prices WHERE model = ?",
                (model,),
            ).fetchone()
            same = row is not None and (
                row["in_micros_per_m"], row["out_micros_per_m"], row["cache_read_micros_per_m"]
            ) == new
            if same:
                conn.execute("UPDATE prices SET updated_at = ? WHERE model = ?", (now, model))
            else:
                conn.execute(
                    "INSERT INTO prices (model, in_micros_per_m, out_micros_per_m, cache_read_micros_per_m, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)"
                    " ON CONFLICT(model) DO UPDATE SET in_micros_per_m = excluded.in_micros_per_m,"
                    " out_micros_per_m = excluded.out_micros_per_m,"
                    " cache_read_micros_per_m = excluded.cache_read_micros_per_m, updated_at = excluded.updated_at",
                    (model, new[0], new[1], new[2], now),
                )
                conn.execute(
                    "INSERT INTO price_history (model, in_micros_per_m, out_micros_per_m, cache_read_micros_per_m,"
                    " source, effective_from) VALUES (?, ?, ?, ?, ?, ?)",
                    (model, new[0], new[1], new[2], source, now),
                )
                changed = True
        return changed

    def price_history(self, model: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Newest-first price changes (optionally for one model)."""
        if model:
            rows = self._conn.execute(
                "SELECT * FROM price_history WHERE model = ? ORDER BY id DESC LIMIT ?", (model, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM price_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def price_for(self, model: str) -> Optional[ModelPrice]:
        row = self._conn.execute(
            "SELECT in_micros_per_m, out_micros_per_m, cache_read_micros_per_m FROM prices WHERE model = ?",
            (model,),
        ).fetchone()
        if row is None:
            return None
        return ModelPrice(
            in_micros_per_m=row["in_micros_per_m"],
            out_micros_per_m=row["out_micros_per_m"],
            cache_read_micros_per_m=row["cache_read_micros_per_m"],
        )

    def models(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT model, in_micros_per_m, out_micros_per_m, cache_read_micros_per_m FROM prices ORDER BY model"
        ).fetchall()
        return [dict(row) for row in rows]

    # -- balances ----------------------------------------------------------------------------
    def balance(self, tenant_id: str) -> int:
        row = self._conn.execute("SELECT balance_micros FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        return int(row["balance_micros"]) if row else 0

    def available(self, tenant_id: str) -> int:
        row = self._conn.execute(
            "SELECT balance_micros - reserved_micros AS av FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
        return int(row["av"]) if row else 0

    # -- the reserve/settle cycle ------------------------------------------------------------
    def reserve(self, key: KeyRecord, model: str, request_id: str, micros: int) -> Optional[Hold]:
        """Take a hold for ``micros``. ``None`` means the balance cannot cover it.

        The UPDATE carries the sufficiency test so the check and the debit are one atomic step;
        the hold row is written in the same transaction so a crash cannot leave a phantom charge.
        """
        micros = max(0, int(micros))
        now = int(time.time())
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE tenants SET reserved_micros = reserved_micros + ?"
                " WHERE id = ? AND balance_micros - reserved_micros >= ?",
                (micros, key.tenant_id, micros),
            )
            if cur.rowcount == 0:
                return None
            conn.execute(
                "INSERT INTO holds (request_id, tenant_id, key_hash, model, micros, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (request_id, key.tenant_id, key.key_hash, model, micros, now),
            )
            return Hold(request_id, key.tenant_id, key.key_hash, model, micros)

    def release(self, hold: Hold) -> bool:
        """Drop a hold without charging (upstream failure, aborted before any usage)."""
        return self._release_request(hold.request_id)

    def _release_request(self, request_id: str) -> bool:
        released = False
        with self._tx() as conn:
            row = conn.execute("SELECT tenant_id, micros FROM holds WHERE request_id = ?", (request_id,)).fetchone()
            if row is not None:
                conn.execute("DELETE FROM holds WHERE request_id = ?", (request_id,))
                conn.execute(
                    "UPDATE tenants SET reserved_micros = MAX(0, reserved_micros - ?) WHERE id = ?",
                    (row["micros"], row["tenant_id"]),
                )
                released = True
        return released

    def settle(self, hold: Hold, usage: Usage, price: ModelPrice, status: str = "ok") -> Settlement:
        """Charge the real cost and release the hold. Idempotent per ``request_id``."""
        cost = cost_micros(usage, price)
        now = int(time.time())
        with self._tx() as conn:
            row = conn.execute("SELECT micros FROM holds WHERE request_id = ?", (hold.request_id,)).fetchone()
            held = int(row["micros"]) if row else 0
            if row is not None:
                conn.execute("DELETE FROM holds WHERE request_id = ?", (hold.request_id,))
                conn.execute(
                    "UPDATE tenants SET reserved_micros = MAX(0, reserved_micros - ?) WHERE id = ?",
                    (held, hold.tenant_id),
                )
            cur = conn.execute(
                "INSERT OR IGNORE INTO usage_events (request_id, tenant_id, key_hash, model, prompt_tokens,"
                " completion_tokens, cache_read_tokens, cost_micros, status, estimated, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    hold.request_id,
                    hold.tenant_id,
                    hold.key_hash,
                    hold.model,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.cache_read_tokens,
                    cost,
                    status,
                    1 if usage.estimated else 0,
                    now,
                ),
            )
            if cur.rowcount == 0:  # already settled — release only, never double-charge
                return Settlement(hold.request_id, 0, True)
            conn.execute(
                "UPDATE tenants SET balance_micros = balance_micros - ? WHERE id = ?", (cost, hold.tenant_id)
            )
            conn.execute(
                "INSERT INTO ledger_entries (tenant_id, request_id, delta_micros, reason, created_at)"
                " VALUES (?, ?, ?, 'usage', ?)",
                (hold.tenant_id, hold.request_id, -cost, now),
            )
        return Settlement(hold.request_id, cost, False)

    # -- reporting ---------------------------------------------------------------------------
    def recent_usage(self, tenant_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        if tenant_id:
            rows = self._conn.execute(
                "SELECT * FROM usage_events WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM usage_events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def entries(self, tenant_id: str, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM ledger_entries WHERE tenant_id = ? ORDER BY id DESC LIMIT ?", (tenant_id, limit)
        ).fetchall()
        return [dict(row) for row in rows]


class _Transaction:
    """Context manager: ``BEGIN IMMEDIATE`` … ``COMMIT`` (rollback on any exception)."""

    def __init__(self, conn: sqlite3.Connection, lock: threading.RLock) -> None:
        self._conn, self._lock = conn, lock

    def __enter__(self) -> sqlite3.Connection:
        self._lock.acquire()
        self._conn.execute("BEGIN IMMEDIATE")
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                self._conn.execute("COMMIT")
            else:
                self._conn.execute("ROLLBACK")
        finally:
            self._lock.release()
        return False


class Meter:
    """Authorisation + pricing + the reserve/settle policy the proxy calls into."""

    def __init__(self, store: LedgerStore, default_price: Optional[ModelPrice] = None) -> None:
        self.store = store
        self.default_price = default_price

    def authenticate(self, token: str) -> Optional[KeyRecord]:
        return self.store.resolve(token)

    def price_for(self, model: str) -> Optional[ModelPrice]:
        return self.store.price_for(model) or self.default_price

    def hold(self, key: KeyRecord, model: str, request_id: str, usage_estimate: Usage) -> Optional[Hold]:
        price = self.price_for(model)
        if price is None:
            raise InsufficientBalance(f"model '{model}' has no price configured")
        return self.store.reserve(key, model, request_id, cost_micros(usage_estimate, price))

    def settle(self, hold: Hold, usage: Usage, status: str = "ok") -> Settlement:
        price = self.price_for(hold.model) or self.default_price or ModelPrice(0, 0)
        return self.store.settle(hold, usage, price, status=status)

    def release(self, hold: Hold) -> bool:
        return self.store.release(hold)


def meter_from_env() -> Optional[Meter]:
    """Build a meter when ``MERLIN_PROXY_METERING`` is truthy; ``None`` keeps the proxy unmetered."""
    if os.environ.get("MERLIN_PROXY_METERING", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    return Meter(LedgerStore())


__all__ = [
    "LedgerStore",
    "Meter",
    "KeyRecord",
    "Hold",
    "Settlement",
    "InsufficientBalance",
    "default_ledger_path",
    "hash_key",
    "meter_from_env",
]
