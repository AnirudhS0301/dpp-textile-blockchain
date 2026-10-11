"""
wallet.py
=========
RSA-2048 wallet system for actor authentication in the DPP framework.

Each actor (producer, citizen, repair enterprise, social organisation,
local authority) holds a public/private key pair.  DPP write transactions
require a valid RSA-2048 digital signature from the initiating actor's
private key, verified against their registered public key before block
inclusion (Section 3.1 of the paper).

Signature verification averages <50 ms per transaction.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


# ─────────────────────────────────────────────────────────────────────────────
# Actor types (mirrors actor tables in the paper)
# ─────────────────────────────────────────────────────────────────────────────

ACTOR_TYPES = {
    "PRODUCER",
    "CITIZEN",
    "REPAIR_ENTERPRISE",
    "SOCIAL_ORGANISATION",
    "LOCAL_AUTHORITY",
    "AUDITOR",
}


# ─────────────────────────────────────────────────────────────────────────────
# Wallet
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Wallet:
    """RSA-2048 wallet for a single DPP actor."""

    wallet_id: str          # e.g. "PRODUCER-WALLET-EU-001"
    actor_type: str         # one of ACTOR_TYPES
    token_balance: int = 0

    def __post_init__(self):
        if self.actor_type not in ACTOR_TYPES:
            raise ValueError(f"Unknown actor_type: {self.actor_type}")
        # Generate RSA-2048 key pair on creation
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        self._public_key = self._private_key.public_key()

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def sign(self, payload: dict) -> bytes:
        """
        Sign a JSON-serialisable payload with the actor's private key.
        Returns raw signature bytes (PKCS1v15 / SHA-256).
        """
        message = json.dumps(payload, sort_keys=True).encode()
        signature = self._private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return signature

    def verify(self, payload: dict, signature: bytes) -> bool:
        """Verify a signature against this wallet's public key."""
        message = json.dumps(payload, sort_keys=True).encode()
        try:
            self._public_key.verify(
                signature,
                message,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False

    # ------------------------------------------------------------------
    # Public key export (for registry)
    # ------------------------------------------------------------------

    def public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def credit(self, amount: int) -> None:
        assert amount >= 0, "Token credit must be non-negative"
        self.token_balance += amount

    def debit(self, amount: int) -> None:
        if amount > self.token_balance:
            raise ValueError(f"Insufficient tokens: have {self.token_balance}, need {amount}")
        self.token_balance -= amount

    def info(self) -> dict:
        return {
            "wallet_id": self.wallet_id,
            "actor_type": self.actor_type,
            "token_balance": self.token_balance,
            "public_key_fingerprint": hashlib.sha256(
                self.public_key_pem().encode()
            ).hexdigest()[:16],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Wallet Registry
# ─────────────────────────────────────────────────────────────────────────────

class WalletRegistry:
    """
    In-memory registry mapping wallet_id → Wallet.
    Provides lookup and cross-wallet signature verification.
    """

    def __init__(self):
        self._wallets: Dict[str, Wallet] = {}

    def register(self, wallet: Wallet) -> None:
        self._wallets[wallet.wallet_id] = wallet

    def get(self, wallet_id: str) -> Optional[Wallet]:
        return self._wallets.get(wallet_id)

    def verify_transaction(
        self, wallet_id: str, payload: dict, signature: bytes
    ) -> bool:
        """Look up wallet and verify the provided signature."""
        wallet = self.get(wallet_id)
        if wallet is None:
            return False
        return wallet.verify(payload, signature)

    def credit(self, wallet_id: str, amount: int) -> None:
        wallet = self.get(wallet_id)
        if wallet is None:
            raise KeyError(f"Wallet not found: {wallet_id}")
        wallet.credit(amount)

    def all_balances(self) -> Dict[str, int]:
        return {wid: w.token_balance for wid, w in self._wallets.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Pre-built actor wallets (matches paper scenario actor tables)
# ─────────────────────────────────────────────────────────────────────────────

def create_default_wallets() -> WalletRegistry:
    """
    Instantiate and register all wallets referenced in Scenarios S1–S6.
    Returns a populated WalletRegistry.
    """
    registry = WalletRegistry()

    actors = [
        ("PRODUCER-WALLET-EU-001",      "PRODUCER"),
        ("CITIZEN-WALLET-EU-4412",       "CITIZEN"),
        ("CITIZEN-WALLET-EU-8821",       "CITIZEN"),
        ("REPAIR-EU-001",                "REPAIR_ENTERPRISE"),
        ("REPAIR-EU-TEXTIL-007",         "REPAIR_ENTERPRISE"),
        ("TEXTILBANK-EU-003",            "SOCIAL_ORGANISATION"),
        ("EPR-AUTH-EU-NAT",              "LOCAL_AUTHORITY"),
        ("CCRI-AUTH-EU-CITY",            "LOCAL_AUTHORITY"),
    ]

    for wallet_id, actor_type in actors:
        w = Wallet(wallet_id=wallet_id, actor_type=actor_type)
        registry.register(w)

    return registry
