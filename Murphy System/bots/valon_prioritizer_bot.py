from __future__ import annotations

import pandas as pd
import lightgbm as lgb


class ValonPrioritizerBot:
    """Predict priority scores for tasks using a LightGBM model."""

    def __init__(self, model_path: str) -> None:
        self.model = lgb.Booster(model_file=model_path)

    def prioritize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["priority_score"] = self.model.predict(df)
        return df.sort_values("priority_score", ascending=False)


class PriorityTrainerBot:
    """Train a LightGBM model for prioritization."""

    def train(self, df: pd.DataFrame, target: str, model_path: str) -> lgb.Booster:
        train_data = lgb.Dataset(df.drop(columns=[target]), label=df[target])
        model = lgb.train({}, train_data)
        model.save_model(model_path)
        return model
