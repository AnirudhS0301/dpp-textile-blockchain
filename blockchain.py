"""
blockchain.py
=============
Custom SHA-256 Proof-of-Work blockchain engine for the DPP framework.

Design follows Section 3.2 of the paper:
  - SHA-256 block chaining
  - PoW difficulty: 4 leading zeros
  - Five-block test chain (indices 4818–4823)
  - Block #4821 is the primary DPP record block
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


DIFFICULTY = 4          # Number of leading zeros required
CHAIN_START_INDEX = 4818

# ─────────────────────────────────────────────────────────────────────────────
# Block
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Block:
    index: int
    timestamp: float
    data: Dict[str, Any]
    previous_hash: str
    nonce: int = 0
    hash: str = ""

    def compute_hash(self) -> str:
        """Return SHA-256 hash of this block's content."""
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine(self, difficulty: int = DIFFICULTY) -> None:
        """Proof-of-Work: iterate nonces until hash starts with `difficulty` zeros."""
        target = "0" * difficulty
        self.nonce = 0
        self.hash = self.compute_hash()
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Blockchain
# ─────────────────────────────────────────────────────────────────────────────

class Blockchain:
    """
    Append-only SHA-256 / PoW blockchain.

    Initialised with a pre-seeded genesis chain starting at index CHAIN_START_INDEX
    so that scenario execution begins at block #4821 as described in the paper.
    """

    def __init__(self, difficulty: int = DIFFICULTY, seed_chain: bool = True):
        self.difficulty = difficulty
        self.chain: List[Block] = []
        self.rejection_log: List[Dict[str, Any]] = []   # Failed registration attempts
        self._dpp_registry: Dict[str, Dict[str, Any]] = {}  # dpp_id → record

        if seed_chain:
            self._seed_genesis_chain()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_genesis_chain(self) -> None:
        """
        Build the first three blocks (4818-4820) as pre-existing chain history
        so that the first DPP registration lands on block #4821.
        """
        genesis_data = {"type": "GENESIS", "note": "DPP chain initialised"}
        genesis = Block(
            index=CHAIN_START_INDEX,
            timestamp=time.time(),
            data=genesis_data,
            previous_hash="0" * 64,
        )
        genesis.mine(self.difficulty)
        self.chain.append(genesis)

        for i in range(1, 3):          # blocks 4819, 4820
            filler_data = {"type": "PRE_CHAIN", "seq": i}
            blk = Block(
                index=CHAIN_START_INDEX + i,
                timestamp=time.time(),
                data=filler_data,
                previous_hash=self.chain[-1].hash,
            )
            blk.mine(self.difficulty)
            self.chain.append(blk)

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_block(self, data: Dict[str, Any]) -> Block:
        """Mine and append a new block; return it."""
        blk = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            data=data,
            previous_hash=self.last_block.hash,
        )
        blk.mine(self.difficulty)
        self.chain.append(blk)
        return blk

    def log_rejection(self, data: Dict[str, Any]) -> None:
        """Record a rejected DPP registration (no block mined)."""
        entry = {
            "timestamp": time.time(),
            "rejection_data": data,
        }
        self.rejection_log.append(entry)

    def register_dpp(self, dpp_id: str, record: Dict[str, Any]) -> None:
        """Store DPP metadata in the in-memory registry."""
        self.update_dpp(dpp_id, record)

    def update_dpp(self, dpp_id: str, updates: Dict[str, Any]) -> None:
        """Merge updates into an existing DPP registry entry."""
        if dpp_id not in self._dpp_registry:
            self._dpp_registry[dpp_id] = {}
        self._dpp_registry[dpp_id].update(updates)

    def get_dpp(self, dpp_id: str) -> Optional[Dict[str, Any]]:
        return self._dpp_registry.get(dpp_id)

    def is_valid(self) -> bool:
        """Validate chain integrity (hash links + PoW)."""
        target = "0" * self.difficulty
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not current.hash.startswith(target):
                return False
        return True

    def summary(self) -> Dict[str, Any]:
        return {
            "chain_length": len(self.chain),
            "last_block_index": self.last_block.index,
            "last_block_hash": self.last_block.hash[:20] + "...",
            "last_nonce": self.last_block.nonce,
            "is_valid": self.is_valid(),
            "rejection_log_count": len(self.rejection_log),
            "registered_dpps": list(self._dpp_registry.keys()),
        }
