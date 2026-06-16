import pandas as pd
import pytest

from qdata.rules.nullity import NullCheck
from qdata.rules.duplicates import DuplicateCheck
from qdata.rules.types import TypeCheck
from qdata.rules.ranges import RangeCheck
from qdata.rules.patterns import PatternCheck
from qdata.rules.uniqueness import UniqueCheck
from qdata.rules.cardinality import CardinalityCheck
from qdata.rules.distributions import DistributionCheck
from qdata.rules.correlations import CorrelationCheck
from qdata.core.score import calculate_score


@pytest.fixture
def clean_df():
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "name": ["Ana", "Carlos", "María", "Juan", "Sofía"],
        "age": [25, 32, 28, 45, 30],
        "email": ["a@x.com", "b@x.com", "c@x.com", "d@x.com", "e@x.com"],
        "salary": [30000, 45000, 38000, 52000, 41000],
    })


@pytest.fixture
def dirty_df():
    import numpy as np
    np.random.seed(42)
    df = pd.DataFrame({
        "id": [1, 2, 2, 4, 5, 5],
        "name": ["Ana", "Carlos", "Carlos", None, "Sofía", "Sofía"],
        "age": [25, 32, 32, 45, 300, 30],
        "email": ["a@x.com", "b@x.com", "b@x.com", "correo-invalido", "e@x.com", "e@x.com"],
        "salary": [30000, 45000, 45000, 52000, 41000, None],
    })
    return df


class TestNullCheck:
    def test_clean_passes(self, clean_df):
        result = NullCheck().execute(clean_df)
        assert result.passed

    def test_dirty_fails(self, dirty_df):
        result = NullCheck().execute(dirty_df)
        assert not result.passed
        assert result.failed > 0
        assert result.recommendation is not None


class TestDuplicateCheck:
    def test_clean_passes(self, clean_df):
        result = DuplicateCheck().execute(clean_df)
        assert result.passed

    def test_dirty_fails(self, dirty_df):
        result = DuplicateCheck().execute(dirty_df)
        assert not result.passed
        assert result.details[0]["count"] > 0


class TestTypeCheck:
    def test_infers_types(self, clean_df):
        result = TypeCheck().execute(clean_df)
        assert isinstance(result.passed, bool)


class TestRangeCheck:
    def test_outliers_detected(self, dirty_df):
        result = RangeCheck().execute(dirty_df)
        details = {d["column"]: d["outliers"] for d in result.details}
        assert any(v > 0 for v in details.values())


class TestPatternCheck:
    def test_email_pattern(self, dirty_df):
        result = PatternCheck(column_patterns={"email": "email"}).execute(dirty_df)
        assert not result.passed


class TestUniqueCheck:
    def test_duplicates_detected(self, dirty_df):
        result = UniqueCheck(key_columns=["id"]).execute(dirty_df)
        assert not result.passed


class TestCardinalityCheck:
    def test_high_cardinality(self):
        df = pd.DataFrame({"id": range(1000)})
        result = CardinalityCheck().execute(df)
        assert not result.passed


class TestScore:
    def test_perfect_score(self, clean_df):
        from qdata.core.engine import resolve_rules
        rules = resolve_rules(["nullity", "duplicates", "types"])
        results = [r.execute(clean_df) for r in rules]
        score, label = calculate_score(results)
        assert score >= 90
        assert label == "excelente"
