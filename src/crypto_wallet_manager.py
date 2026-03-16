# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Crypto Wallet Manager — Murphy System

Manages three wallet categories in a single unified view:
  - ExchangeWallet  : balances fetched from an exchange API
  - SoftwareWallet  : EVM / Bitcoin address with optional private-key signing
  - HardwareWallet  : abstract interface for Ledger / Trezor (key never stored)

All private keys are encrypted at rest via the Murphy SecureKeyManager.
Transfer operations route through the TradingHITLGateway so every
on-chain send or exchange withdrawal requires human confirmation.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_TX_HISTORY = 20_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class WalletType(Enum):
    """Category of wallet (Enum subclass)."""
    EXCHANGE = "exchange"
    SOFTWARE = "software"
    HARDWARE = "hardware"


class WalletChain(Enum):
    """Blockchain network (Enum subclass)."""
    BITCOIN   = "bitcoin"
    ETHEREUM  = "ethereum"
    POLYGON   = "polygon"
    SOLANA    = "solana"
    BASE      = "base"
    ARBITRUM  = "arbitrum"
    OPTIMISM  = "optimism"
    EXCHANGE  = "exchange"   # Not on-chain — held by exchange


class WalletStatus(Enum):
    """Wallet health state (Enum subclass)."""
    ACTIVE    = "active"
    SYNCING   = "syncing"
    OFFLINE   = "offline"
    LOCKED    = "locked"
    ERROR     = "error"


class TransactionType(Enum):
    """Type of wallet transaction (Enum subclass)."""
    DEPOSIT    = "deposit"
    WITHDRAWAL = "withdrawal"
    INTERNAL   = "internal"
    TRADE_BUY  = "trade_buy"
    TRADE_SELL = "trade_sell"
    FEE        = "fee"
    STAKE      = "stake"
    UNSTAKE    = "unstake"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WalletAsset:
    """A single asset holding within a wallet."""
    symbol:          str
    name:            str
    balance:         float
    locked:          float      = 0.0
    price_usd:       float      = 0.0
    chain:           WalletChain = WalletChain.EXCHANGE

    @property
    def total(self) -> float:
        """Total balance including locked funds."""
        return self.balance + self.locked

    @property
    def value_usd(self) -> float:
        """USD value of the free balance at current price."""
        return self.balance * self.price_usd


@dataclass
class WalletTransaction:
    """Historical record of a wallet event."""
    tx_id:        str
    wallet_id:    str
    tx_type:      TransactionType
    asset:        str
    amount:       float
    fee:          float
    timestamp:    str
    status:       str   = "confirmed"
    chain_tx_hash: Optional[str] = None
    from_address:  Optional[str] = None
    to_address:    Optional[str] = None
    notes:         str  = ""


@dataclass
class WalletSummary:
    """Snapshot of a wallet's full state."""
    wallet_id:    str
    label:        str
    wallet_type:  WalletType
    chain:        WalletChain
    status:       WalletStatus
    address:      Optional[str]
    assets:       List[WalletAsset]     = field(default_factory=list)
    total_usd:    float                  = 0.0
    last_synced:  str                    = ""


# ---------------------------------------------------------------------------
# Wallet base and concrete types
# ---------------------------------------------------------------------------

class BaseWallet(ABC):
    """Abstract wallet.  Subclasses implement ``sync()`` and ``transfer()``."""

    def __init__(
        self,
        wallet_id:   str,
        label:       str,
        wallet_type: WalletType,
        chain:       WalletChain,
        address:     Optional[str] = None,
    ) -> None:
        self.wallet_id   = wallet_id
        self.label       = label
        self.wallet_type = wallet_type
        self.chain       = chain
        self.address     = address
        self.status      = WalletStatus.SYNCING
        self._lock       = threading.Lock()
        self._assets:     List[WalletAsset]       = []
        self._tx_history: List[WalletTransaction] = []

    # ---- public surface --------------------------------------------------

    def sync(self) -> bool:
        """Refresh balances.  Returns True on success."""
        try:
            result = self._do_sync()
            with self._lock:
                self.status = WalletStatus.ACTIVE
            return result
        except Exception as exc:
            logger.error("Wallet %s sync error: %s", self.wallet_id, exc)
            with self._lock:
                self.status = WalletStatus.ERROR
            return False

    def get_assets(self) -> List[WalletAsset]:
        """Return current asset holdings."""
        with self._lock:
            return list(self._assets)

    def get_transaction_history(self, limit: int = 100) -> List[WalletTransaction]:
        """Return most recent *limit* transactions."""
        with self._lock:
            return list(self._tx_history[-limit:])

    def get_summary(self) -> WalletSummary:
        """Return a full wallet snapshot."""
        with self._lock:
            total_usd = sum(a.value_usd for a in self._assets)
            return WalletSummary(
                wallet_id   = self.wallet_id,
                label       = self.label,
                wallet_type = self.wallet_type,
                chain       = self.chain,
                status      = self.status,
                address     = self.address,
                assets      = list(self._assets),
                total_usd   = total_usd,
                last_synced = datetime.now(timezone.utc).isoformat(),
            )

    def close(self) -> None:
        """Release resources and mark wallet offline."""
        with self._lock:
            self.status = WalletStatus.OFFLINE

    def __enter__(self) -> "BaseWallet":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---- overridable internals -------------------------------------------

    @abstractmethod
    def _do_sync(self) -> bool:
        """Refresh wallet balances.  Subclasses must override."""
        ...

    def _record_tx(self, tx: WalletTransaction) -> None:
        with self._lock:
            try:
                from thread_safe_operations import capped_append
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            capped_append(self._tx_history, tx, _MAX_TX_HISTORY)


class ExchangeWallet(BaseWallet):
    """
    Wallet backed by an exchange API.  Balances are fetched via the
    ``ExchangeRegistry``; transfers require HITL approval.
    """

    def __init__(
        self,
        exchange_id:  str,
        registry:     Any,   # ExchangeRegistry — avoid circular import at type level
        label:        str    = "",
    ) -> None:
        super().__init__(
            wallet_id   = f"exchange::{exchange_id}::{str(uuid.uuid4())[:8]}",
            label       = label or f"{exchange_id.capitalize()} Exchange Wallet",
            wallet_type = WalletType.EXCHANGE,
            chain       = WalletChain.EXCHANGE,
            address     = None,
        )
        self._exchange_id = exchange_id
        self._registry    = registry

    def _do_sync(self) -> bool:
        balances = self._registry.get_balances(self._exchange_id)
        assets   = []
        for b in balances:
            if b.free > 0.0 or b.locked > 0.0:
                assets.append(
                    WalletAsset(
                        symbol  = b.currency,
                        name    = b.currency,
                        balance = b.free,
                        locked  = b.locked,
                        chain   = WalletChain.EXCHANGE,
                    )
                )
        with self._lock:
            self._assets = assets
        return True


class SoftwareWallet(BaseWallet):
    """
    EVM / Bitcoin software wallet.  Address is public; the private key,
    if provided, is stored encrypted via SecureKeyManager and only loaded
    when a signing operation is requested.

    For read-only portfolio tracking, *private_key_ref* may be omitted.
    """

    def __init__(
        self,
        chain:           WalletChain,
        address:         str,
        label:           str               = "",
        private_key_ref: Optional[str]     = None,
    ) -> None:
        super().__init__(
            wallet_id   = f"sw::{chain.value}::{address[:8]}",
            label       = label or f"{chain.value.capitalize()} Wallet",
            wallet_type = WalletType.SOFTWARE,
            chain       = chain,
            address     = address,
        )
        self._private_key_ref = private_key_ref   # key name in SecureKeyManager

    def _do_sync(self) -> bool:
        """Sync on-chain balances.  Requires web3/bitcoin RPC; stub for now."""
        logger.debug("SoftwareWallet._do_sync: %s %s — requires RPC node", self.chain.value, self.address)
        with self._lock:
            self.status = WalletStatus.ACTIVE
        return True

    def can_sign(self) -> bool:
        """Return True if a private key reference is configured."""
        return self._private_key_ref is not None

    def sign_transaction(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """
        Return a hex-encoded signed transaction.

        The private key is loaded from SecureKeyManager only at signing
        time and never persisted in plaintext memory longer than needed.
        """
        if not self._private_key_ref:
            logger.warning("SoftwareWallet: no private key configured for %s", self.wallet_id)
            return None
        try:
            from secure_key_manager import retrieve_api_key
            private_key = retrieve_api_key(self._private_key_ref)
            if not private_key:
                logger.error("SoftwareWallet: private key %s not found in SecureKeyManager", self._private_key_ref)
                return None
            # NOTE: Actual web3/btc signing deferred to chain-specific libraries
            # (web3.py for EVM, bitcoin-utils for Bitcoin).  Returning placeholder.
            logger.info("SoftwareWallet: sign_transaction called for %s", self.wallet_id)
            return f"0xSIGNED::{self.wallet_id}"
        except Exception as exc:
            logger.error("SoftwareWallet sign_transaction error: %s", exc)
            return None


class HardwareWallet(BaseWallet):
    """
    Abstract interface for hardware wallets (Ledger, Trezor).

    Private keys **never** leave the device; signing happens on-device
    and only the result is returned.  Connection to the physical device
    is handled by ledgerblue / python-trezor libraries loaded lazily.
    """

    def __init__(
        self,
        chain:       WalletChain,
        address:     str,
        device_type: str = "ledger",
        label:       str = "",
    ) -> None:
        super().__init__(
            wallet_id   = f"hw::{device_type}::{chain.value}::{address[:8]}",
            label       = label or f"{device_type.capitalize()} Hardware Wallet",
            wallet_type = WalletType.HARDWARE,
            chain       = chain,
            address     = address,
        )
        self._device_type = device_type

    def _do_sync(self) -> bool:
        logger.debug(
            "HardwareWallet._do_sync: %s %s — requires device connection",
            self._device_type, self.address,
        )
        return True

    def request_sign(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """
        Request on-device signing.  Returns signed hex or None if user rejects.

        Actual implementation delegates to ledgerblue / python-trezor SDK.
        """
        logger.info(
            "HardwareWallet.request_sign: user must confirm on %s device for %s",
            self._device_type, self.wallet_id,
        )
        return None


# ---------------------------------------------------------------------------
# Wallet Manager
# ---------------------------------------------------------------------------

class CryptoWalletManager:
    """
    Aggregates all wallet types into a single portfolio view.

    All write operations (transfers, withdrawals) are validated through
    the TradingHITLGateway before execution.
    """

    def __init__(self, hitl_gateway: Optional[Any] = None) -> None:
        self._lock          = threading.Lock()
        self._wallets:       Dict[str, BaseWallet] = {}
        self._hitl_gateway  = hitl_gateway

    # ---- wallet lifecycle ------------------------------------------------

    def add_wallet(self, wallet: BaseWallet) -> str:
        """Register *wallet* and trigger an initial sync."""
        with self._lock:
            self._wallets[wallet.wallet_id] = wallet
        wallet.sync()
        logger.info("CryptoWalletManager: added wallet %s", wallet.wallet_id)
        return wallet.wallet_id

    def remove_wallet(self, wallet_id: str) -> bool:
        """Unregister and close *wallet_id*."""
        with self._lock:
            wallet = self._wallets.pop(wallet_id, None)
        if wallet:
            wallet.close()
            logger.info("CryptoWalletManager: removed wallet %s", wallet_id)
            return True
        return False

    def get_wallet(self, wallet_id: str) -> Optional[BaseWallet]:
        """Fetch a registered wallet by ID."""
        with self._lock:
            return self._wallets.get(wallet_id)

    def list_wallets(self) -> List[WalletSummary]:
        """Return summaries of all registered wallets."""
        with self._lock:
            wallets = list(self._wallets.values())
        return [w.get_summary() for w in wallets]

    # ---- portfolio view --------------------------------------------------

    def get_portfolio_snapshot(self) -> Dict[str, Any]:
        """
        Aggregate all wallet assets into a combined portfolio view.

        Returns currency → {total_balance, total_usd, wallets: [...]} mapping.
        """
        aggregated: Dict[str, Dict[str, Any]] = {}
        total_usd = 0.0
        for summary in self.list_wallets():
            for asset in summary.assets:
                entry = aggregated.setdefault(asset.symbol, {
                    "symbol":      asset.symbol,
                    "total_balance": 0.0,
                    "locked":      0.0,
                    "total_usd":   0.0,
                    "wallets":     [],
                })
                entry["total_balance"] += asset.balance
                entry["locked"]        += asset.locked
                entry["total_usd"]     += asset.value_usd
                entry["wallets"].append({
                    "wallet_id": summary.wallet_id,
                    "label":     summary.label,
                    "balance":   asset.balance,
                })
                total_usd += asset.value_usd
        return {
            "total_usd":  total_usd,
            "asset_count": len(aggregated),
            "wallet_count": len(self._wallets),
            "assets":     list(aggregated.values()),
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }

    # ---- sync ------------------------------------------------------------

    def sync_all(self) -> Dict[str, bool]:
        """Trigger sync on all registered wallets and return per-wallet results."""
        with self._lock:
            wallets = list(self._wallets.values())
        return {w.wallet_id: w.sync() for w in wallets}

    # ---- HITL-gated transfer ---------------------------------------------

    def request_transfer(
        self,
        from_wallet_id: str,
        to_address:     str,
        asset:          str,
        amount:         float,
        chain:          Optional[WalletChain] = None,
        notes:          str                   = "",
    ) -> Dict[str, Any]:
        """
        Queue a transfer request through the HITL gateway.

        Returns the approval request dict; actual transfer executes only
        after a human approves via ``TradingHITLGateway.approve()``.
        """
        transfer_request = {
            "request_id":     str(uuid.uuid4()),
            "from_wallet_id": from_wallet_id,
            "to_address":     to_address,
            "asset":          asset,
            "amount":         amount,
            "chain":          chain.value if chain else "unknown",
            "notes":          notes,
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }
        if self._hitl_gateway is not None:
            return self._hitl_gateway.submit_transfer_request(transfer_request)
        logger.warning(
            "CryptoWalletManager: no HITL gateway configured — transfer request %s queued locally",
            transfer_request["request_id"],
        )
        return {"queued": True, "request": transfer_request, "requires_approval": True}
