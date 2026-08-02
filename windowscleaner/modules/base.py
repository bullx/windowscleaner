"""Base types for cleanup modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Risk(Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class CleanItem:
    id: str
    label: str
    detail: str
    bytes_estimate: int = 0
    requires_admin: bool = False
    # Shown in Scan results so users know impact before cleaning
    effect: str = ""
    repercussions: str = ""
    # Product status: Ready / Needs Admin / Came back / Applied / Failed / ...
    status: str = ""
    # What the user should do next
    next_step: str = ""


@dataclass
class ModuleResult:
    module_id: str
    label: str
    items: list[CleanItem] = field(default_factory=list)
    bytes_freed: int = 0
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def bytes_estimate(self) -> int:
        return sum(i.bytes_estimate for i in self.items)


ProgressCb = Callable[[str], None]


class CleanModule(ABC):
    id: str
    label: str
    description: str
    risk: Risk = Risk.SAFE
    requires_admin: bool = False
    default_enabled: bool = True

    @abstractmethod
    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        ...

    @abstractmethod
    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        ...
