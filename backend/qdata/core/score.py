from qdata.rules.base import RuleResult

WEIGHTS = {
    "error": 10,
    "warning": 5,
    "info": 2,
}


def calculate_score(results: list[RuleResult]) -> tuple[int, str]:
    total_weight = 0
    total_penalty = 0

    for r in results:
        weight = WEIGHTS.get(r.severity, 5)
        total_weight += weight * 100
        penalty = r.failure_pct * weight
        total_penalty += penalty

    if total_weight == 0:
        return 100, "excelente"

    raw_score = max(0, 100 - (total_penalty / total_weight * 100))
    score = round(raw_score, 2)

    if score >= 90:
        label = "excelente"
    elif score >= 70:
        label = "aceptable"
    elif score >= 50:
        label = "deficiente"
    else:
        label = "critico"

    return score, label


def build_recommendations(results: list[RuleResult]) -> list[dict]:
    recs = []
    for r in results:
        if not r.passed and r.recommendation:
            recs.append({
                "rule": r.rule_name,
                "severity": r.severity,
                "failure_pct": r.failure_pct,
                "recommendation": r.recommendation,
            })
    return recs
