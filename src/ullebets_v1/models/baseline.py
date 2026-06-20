from __future__ import annotations

import pandas as pd


def baseline_lambda(frame: pd.DataFrame) -> pd.Series:
    return frame["baseline_lambda"]
