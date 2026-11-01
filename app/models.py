from dataclasses import dataclass, field
from typing import Any

@dataclass
class Complaint:
    dates: list[str] = field(default_factory=list)
    trip_ids: list[str] = field(default_factory=list)
    kinds: set[str] = field(default_factory=set)
    text: str = ""
    injection: bool = False

@dataclass
class TraceStep:
    at: str
    type: str
    name: str
    input: Any
    output: Any

@dataclass
class PendingItem:
    id: str
    rider_id: str
    type: str
    amount: int | None
    reason: str
    created_at: str

@dataclass
class Investigation:
    owed: int = 0
    facts: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    unresolved: bool = False
    reason: str = ""
