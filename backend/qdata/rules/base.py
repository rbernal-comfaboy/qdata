from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class RuleResult:
    rule_name: str
    description: str
    severity: str
    passed: bool
    total: int
    failed: int
    failure_pct: float
    details: list[dict] = field(default_factory=list)
    sample_failures: list[dict] = field(default_factory=list)
    recommendation: str | None = None
    duration_ms: float = 0.0


class Rule(ABC):
    def __init__(self, severity: str = "error"):
        self.severity = severity

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult: ...
