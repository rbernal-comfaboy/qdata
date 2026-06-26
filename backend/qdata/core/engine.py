import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

from qdata.rules.base import Rule, RuleResult
from qdata.rules.nullity import NullCheck
from qdata.rules.duplicates import DuplicateCheck
from qdata.rules.types import TypeCheck
from qdata.rules.ranges import RangeCheck
from qdata.rules.patterns import PatternCheck
from qdata.rules.uniqueness import UniqueCheck
from qdata.rules.referential import ReferentialIntegrityCheck
from qdata.rules.cardinality import CardinalityCheck
from qdata.rules.distributions import DistributionCheck
from qdata.rules.correlations import CorrelationCheck
from qdata.rules.format_rules import EmailCheck, SpecialCharsCheck, StringLengthCheck, TrimCheck, CaseConsistencyCheck, PhoneCheck, ZipCodeCheck, RfcCurpCheck
from qdata.rules.date_rules import InvalidDateCheck, DateRangeCheck, DateInconsistencyCheck, FreshnessCheck, LatencyCheck
from qdata.rules.business_rules import CrossConsistencyCheck, FunctionalDependencyCheck, ClassBalanceCheck, BooleanBiasCheck, DerivedColumnCheck
from qdata.rules.advanced_rules import RowCompletenessCheck, MultivariateOutlierCheck, DriftCheck, SchemaEvolutionCheck
from qdata.rules.integrity_rules import VolumeAnomalyCheck, SequentialIntegrityCheck, MissingFKCheck
from qdata.rules.person_dedup_rules import FuzzyNameMatch, FuzzyIdMatch, SimilarDob, PersonCompositeSimilarity, SimilarPeopleCheck

RULE_REGISTRY = {
    # Grupo: básico (reglas originales)
    "nullity": NullCheck,
    "duplicates": DuplicateCheck,
    "types": TypeCheck,
    "ranges": RangeCheck,
    "patterns": PatternCheck,
    "uniqueness": UniqueCheck,
    "referential": ReferentialIntegrityCheck,
    "cardinality": CardinalityCheck,
    "distributions": DistributionCheck,
    "correlations": CorrelationCheck,
    # Grupo: formato
    "email_valid": EmailCheck,
    "special_chars": SpecialCharsCheck,
    "string_length": StringLengthCheck,
    "trim_check": TrimCheck,
    "case_check": CaseConsistencyCheck,
    "phone_valid": PhoneCheck,
    "zip_valid": ZipCodeCheck,
    "rfc_curp": RfcCurpCheck,
    # Grupo: fechas
    "invalid_dates": InvalidDateCheck,
    "date_range": DateRangeCheck,
    "date_inconsistency": DateInconsistencyCheck,
    "freshness": FreshnessCheck,
    "latency": LatencyCheck,
    # Grupo: negocio
    "cross_consistency": CrossConsistencyCheck,
    "functional_dependency": FunctionalDependencyCheck,
    "class_balance": ClassBalanceCheck,
    "boolean_bias": BooleanBiasCheck,
    "derived_columns": DerivedColumnCheck,
    # Grupo: avanzadas
    "row_completeness": RowCompletenessCheck,
    "multivariate_outliers": MultivariateOutlierCheck,
    "drift": DriftCheck,
    "schema_evolution": SchemaEvolutionCheck,
    # Grupo: integridad
    "volume_anomaly": VolumeAnomalyCheck,
    "sequential_integrity": SequentialIntegrityCheck,
    "missing_fks": MissingFKCheck,
    # Grupo: personas
    "fuzzy_name_match": FuzzyNameMatch,
    "fuzzy_id_match": FuzzyIdMatch,
    "similar_dob": SimilarDob,
    "person_composite_similarity": PersonCompositeSimilarity,
    "personas_similares": SimilarPeopleCheck,
}

RULE_GROUPS = {
    "basico": ["nullity", "duplicates", "types", "ranges", "patterns", "uniqueness", "referential", "cardinality", "distributions", "correlations"],
    "formato": ["email_valid", "special_chars", "string_length", "trim_check", "case_check", "phone_valid", "zip_valid", "rfc_curp"],
    "fechas": ["invalid_dates", "date_range", "date_inconsistency", "freshness", "latency"],
    "negocio": ["cross_consistency", "functional_dependency", "class_balance", "boolean_bias", "derived_columns"],
    "avanzadas": ["row_completeness", "multivariate_outliers", "drift", "schema_evolution"],
    "integridad": ["volume_anomaly", "sequential_integrity", "missing_fks"],
    "personas_similares": ["personas_similares"],
    "todo": list(RULE_REGISTRY.keys()),
}

SIMILARITY_LEVELS = {
    "ninguno": [],
    "rapido": ["fuzzy_id_match", "similar_dob"],
    "medio": ["fuzzy_id_match", "similar_dob", "fuzzy_name_match"],
    "profundo": ["fuzzy_id_match", "similar_dob", "fuzzy_name_match", "person_composite_similarity"],
}


def resolve_rules(rules_config: list[str] | str, rule_configs: dict | None = None) -> list[Rule]:
    if isinstance(rules_config, str):
        if rules_config == "all":
            return [cls() for cls in RULE_REGISTRY.values()]
        rules_config = [r.strip() for r in rules_config.split(",")]

    rule_names = []
    for item in rules_config:
        if item == "all":
            return [cls() for cls in RULE_REGISTRY.values()]
        if item.startswith("grupo:"):
            group_name = item.replace("grupo:", "")
            if group_name in RULE_GROUPS:
                rule_names.extend(RULE_GROUPS[group_name])
        elif item.startswith("nivel:"):
            level_name = item.replace("nivel:", "")
            if level_name in SIMILARITY_LEVELS:
                rule_names.extend(SIMILARITY_LEVELS[level_name])
        elif item in RULE_REGISTRY:
            rule_names.append(item)

    # Deduplicate preserving order
    seen = set()
    unique_names = []
    for n in rule_names:
        if n not in seen:
            seen.add(n)
            unique_names.append(n)

    configs = rule_configs or {}
    rules = []
    for name in unique_names:
        if name in RULE_REGISTRY:
            cls = RULE_REGISTRY[name]
            rule_cfg = configs.get(name, {})
            if rule_cfg:
                rules.append(cls(**rule_cfg))
            else:
                rules.append(cls())
    return rules


class Engine:
    def __init__(self, parallel: bool = True):
        self.parallel = parallel

    async def run(self, df: pd.DataFrame, rules: list[Rule] | list[str], duckdb_conn=None) -> list[RuleResult]:
        if isinstance(rules[0], str):
            rules = resolve_rules(rules)

        # Try to create a DuckDB connection for SQL-powered rules
        if duckdb_conn is None:
            try:
                import duckdb
                duckdb_conn = duckdb.connect(":memory:")
                duckdb_conn.register("data", df)
            except ImportError:
                pass

        extra = {}
        if duckdb_conn is not None:
            extra["duckdb_conn"] = duckdb_conn

        results = []
        if self.parallel and len(rules) > 2:
            with ProcessPoolExecutor(max_workers=min(len(rules), 4)) as executor:
                start_times = {}
                futures = {}
                for r in rules:
                    start_times[r.name] = time.perf_counter()
                    futures[executor.submit(r.execute, df.copy(), **extra)] = r
                for future in as_completed(futures):
                    t0 = start_times.get(futures[future].name, time.perf_counter())
                    try:
                        result = future.result()
                        result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                        results.append(result)
                    except Exception as e:
                        rule = futures[future]
                        results.append(RuleResult(
                            rule_name=rule.name,
                            description=rule.description,
                            severity=rule.severity,
                            passed=False,
                            total=0,
                            failed=0,
                            failure_pct=0,
                            details=[{"error": str(e)}],
                            recommendation=f"Error al ejecutar regla: {e}",
                            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                        ))
        else:
            for rule in rules:
                t0 = time.perf_counter()
                try:
                    result = rule.execute(df.copy(), **extra)
                    result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                    results.append(result)
                except Exception as e:
                    results.append(RuleResult(
                        rule_name=rule.name,
                        description=rule.description,
                        severity=rule.severity,
                        passed=False,
                        total=0,
                        failed=0,
                        failure_pct=0,
                        details=[{"error": str(e)}],
                        recommendation=f"Error al ejecutar regla: {e}",
                        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                    ))

        if duckdb_conn is not None:
            try:
                duckdb_conn.close()
            except Exception:
                pass

        return results
