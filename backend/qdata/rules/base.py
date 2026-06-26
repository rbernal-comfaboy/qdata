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
    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        """Execute the rule on the given DataFrame.

        Optional kwargs recognized by some rules:
          progress_callback(processed: int, total: int, message: str, phase: str = "", extra: dict | None = None)
              Called periodically to report progress (processed/total).
              `phase` indicates the sub-phase (blocking, scoring, clustering).
              `extra` may contain additional metrics (field_avgs, score_distribution, eta_sec, etc.).
          log_callback(message: str)
              Called to emit log messages during execution.
        """
