"""JU CivicWatch — Receipt system.

Every data pull produces a SHA-256 verified receipt.
Same standard as JU Command Center: receipts or it didn't happen.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


RECEIPTS_DIR = Path(__file__).resolve().parent.parent / "receipts"


@dataclass
class Receipt:
    """Verified receipt for one CivicWatch data operation."""

    operation: str
    source: str
    started_at: str
    completed_at: str
    status: str  # VERIFIED | FAILED | BLOCKED
    input_hash: str
    output_hash: str
    record_count: int
    flags: list[str] = field(default_factory=list)
    notes: str = ""
    cost_usd: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def hash_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def write_receipt(receipt: Receipt, directory: Optional[Path] = None) -> Path:
    """Persist a receipt as JSON. Returns the written path."""
    dest = directory or RECEIPTS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{receipt.operation.lower().replace(' ', '-')}-{stamp}.json"
    path = dest / filename
    path.write_text(receipt.to_json(), encoding="utf-8")
    return path


def make_receipt(
    operation: str,
    source: str,
    input_data: Any,
    output_data: Any,
    status: str = "VERIFIED",
    record_count: int = 0,
    flags: Optional[list[str]] = None,
    notes: str = "",
) -> Receipt:
    """Build a receipt from raw input/output. Hashes both sides."""
    now = datetime.now(timezone.utc).isoformat()
    inp = json.dumps(input_data, sort_keys=True, default=str).encode("utf-8")
    out = json.dumps(output_data, sort_keys=True, default=str).encode("utf-8")
    return Receipt(
        operation=operation,
        source=source,
        started_at=now,
        completed_at=now,
        status=status,
        input_hash=_sha256_bytes(inp),
        output_hash=_sha256_bytes(out),
        record_count=record_count,
        flags=flags or [],
        notes=notes,
    )


if __name__ == "__main__":
    # Smoke test
    r = make_receipt(
        operation="SMOKE-TEST",
        source="local",
        input_data={"ping": "ok"},
        output_data={"pong": "ok"},
        record_count=1,
    )
    p = write_receipt(r)
    print(f"Receipt written: {p}")
    print(r.to_json())
