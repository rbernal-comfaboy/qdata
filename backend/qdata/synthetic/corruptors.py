import random

import numpy as np
import pandas as pd


def introduce_nulls(df: pd.DataFrame, columns: list[str] | None = None, rate: float = 0.05) -> pd.DataFrame:
    df = df.copy()
    cols = columns or df.columns.tolist()
    for col in cols:
        mask = np.random.random(len(df)) < rate
        df.loc[mask, col] = None
    return df


def introduce_duplicates(df: pd.DataFrame, rate: float = 0.02) -> pd.DataFrame:
    n_dupes = int(len(df) * rate)
    if n_dupes == 0:
        return df
    idx = np.random.choice(df.index, n_dupes, replace=False)
    dupes = df.loc[idx].copy()
    return pd.concat([df, dupes], ignore_index=True)


def introduce_outliers(df: pd.DataFrame, columns: list[str] | None = None, rate: float = 0.01, factor: float = 10) -> pd.DataFrame:
    df = df.copy()
    numeric = df.select_dtypes(include=[np.number]).columns
    cols = columns or numeric.tolist()
    for col in cols:
        if col not in numeric:
            continue
        mask = np.random.random(len(df)) < rate
        if mask.any():
            multiplier = np.random.choice([-1, 1], size=mask.sum()) * factor
            df.loc[mask, col] = df.loc[mask, col] * multiplier
    return df


def introduce_typos(df: pd.DataFrame, columns: list[str] | None = None, rate: float = 0.03) -> pd.DataFrame:
    df = df.copy()
    cols = columns or df.select_dtypes(include=["object"]).columns.tolist()
    for col in cols:
        mask = np.random.random(len(df)) < rate
        for idx in df[mask].index:
            val = str(df.at[idx, col])
            if len(val) < 2:
                continue
            pos = random.randint(0, len(val) - 1)
            chars = list(val)
            chars[pos] = random.choice("abcdefghijklmnopqrstuvwxyz")
            df.at[idx, col] = "".join(chars)
    return df


def corrupt(df: pd.DataFrame,
            null_rate: float = 0.0,
            duplicate_rate: float = 0.0,
            outlier_rate: float = 0.0,
            typo_rate: float = 0.0) -> pd.DataFrame:
    df = df.copy()
    if null_rate > 0:
        df = introduce_nulls(df, rate=null_rate)
    if duplicate_rate > 0:
        df = introduce_duplicates(df, rate=duplicate_rate)
    if outlier_rate > 0:
        df = introduce_outliers(df, rate=outlier_rate)
    if typo_rate > 0:
        df = introduce_typos(df, rate=typo_rate)
    return df
