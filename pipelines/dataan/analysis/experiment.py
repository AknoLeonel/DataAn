"""Experimento: modelos de previsão de casos semanais comparados com validação honesta.

Para cada origem (semana) das últimas `origins` semanas, cada modelo é ajustado só com
o passado e prevê as próximas `horizon` semanas. O erro absoluto médio (em casos) é
comparado com a previsão ingênua ("repetir a última semana").

Modelos:
- Ingênuo: repete a última semana.
- Sazonal ingênuo: repete a mesma semana do ano anterior.
- Holt amortecido (o modelo publicado na página de dengue).
- Regressão com defasagens: ridge sobre log1p dos casos das últimas 4 semanas,
  tendência recente e sazonalidade (seno/cosseno da semana do ano), um modelo por horizonte.
- Regressão com defasagens + clima: a mesma, com temperatura e umidade médias das
  últimas 4 e das 4 semanas anteriores (o mosquito responde ao clima com atraso).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dataan.analysis.forecast import _fit, _project

NAIVE = "Ingênuo"
SEASONAL = "Sazonal ingênuo"
HOLT = "Holt amortecido"
RIDGE = "Regressão (defasagens)"
RIDGE_CLIMA = "Regressão (defasagens + clima)"
MODELS = [NAIVE, SEASONAL, HOLT, RIDGE, RIDGE_CLIMA]
CLIMA = ("tempmed", "umidmed")
LAM = 1.0


@dataclass
class Backtest:
    mae: dict[str, float]
    skill: dict[str, float]  # 1 - MAE / MAE do ingênuo
    preds: dict[str, pd.Series] = field(default_factory=dict)  # previsão para h = horizon
    actual: pd.Series | None = None
    clima_ok: bool = True


def _ridge_fit(X: np.ndarray, y: np.ndarray, lam: float = LAM):
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    ym = y.mean()
    w = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - ym))
    return mu, sd, w, ym


def _ridge_predict(model, x: np.ndarray) -> float:
    mu, sd, w, ym = model
    return float(((x - mu) / sd) @ w + ym)


def _features(y: np.ndarray, week: np.ndarray, clima: np.ndarray | None, i: int) -> np.ndarray:
    ang = 2 * np.pi * week[i] / 52.18
    base = [y[i], y[i - 1], y[i - 2], y[i - 3], y[i] - y[i - 4], np.sin(ang), np.cos(ang)]
    if clima is not None:
        recent = clima[i - 3 : i + 1].mean(axis=0)
        before = clima[i - 7 : i - 3].mean(axis=0)
        base.extend([*recent, *before])
    return np.array(base, dtype=float)


def backtest(
    df: pd.DataFrame, *, horizon: int = 4, origins: int = 52, min_train: int = 104
) -> Backtest:
    """`df`: colunas date, casos_est e, se houver, tempmed/umidmed; uma linha por semana."""
    df = df.sort_values("date").reset_index(drop=True)
    y = np.log1p(df["casos_est"].clip(lower=0).to_numpy(dtype=float))
    week = df["date"].dt.isocalendar().week.to_numpy(dtype=float)
    clima_df = (
        df[list(CLIMA)].apply(pd.to_numeric, errors="coerce") if set(CLIMA) <= set(df) else None
    )
    clima_ok = clima_df is not None and clima_df.notna().mean().min() > 0.8
    clima = clima_df.ffill().bfill().to_numpy(dtype=float) if clima_ok else None
    n = len(y)
    first = max(8, n - origins - horizon)
    if first < min_train:
        raise ValueError(f"Série curta para o experimento ({n} semanas)")

    err: dict[str, list[float]] = {m: [] for m in MODELS}
    preds: dict[str, dict[pd.Timestamp, float]] = {m: {} for m in MODELS}
    for origin in range(first, n - horizon):
        actual = np.expm1(y[origin + 1 : origin + 1 + horizon])
        target_date = df["date"].iloc[origin + horizon]
        out: dict[str, np.ndarray] = {
            NAIVE: np.repeat(np.expm1(y[origin]), horizon),
            SEASONAL: np.array([np.expm1(y[origin + h - 52 + 1]) for h in range(horizon)]),
        }
        params, lvl, trd = _fit(y[: origin + 1])
        out[HOLT] = np.expm1(_project(lvl, trd, params[2], horizon))
        for name, use_clima in ((RIDGE, False), (RIDGE_CLIMA, True)):
            if use_clima and clima is None:
                continue
            c = clima if use_clima else None
            fc = []
            for h in range(1, horizon + 1):
                rows = range(8, origin - h + 1)
                X = np.array([_features(y, week, c, t) for t in rows])
                tgt = np.array([y[t + h] for t in rows])
                model = _ridge_fit(X, tgt)
                fc.append(np.expm1(_ridge_predict(model, _features(y, week, c, origin))))
            out[name] = np.clip(np.array(fc), 0, None)
        for name, f in out.items():
            err[name].extend(np.abs(actual - f))
            preds[name][target_date] = float(f[-1])

    mae = {m: float(np.mean(e)) for m, e in err.items() if e}
    base = mae[NAIVE]
    skill = {m: (1 - v / base) if base > 0 else 0.0 for m, v in mae.items()}
    actual_s = pd.Series(np.expm1(y), index=df["date"])
    return Backtest(
        mae=mae,
        skill=skill,
        preds={m: pd.Series(p).sort_index() for m, p in preds.items() if p},
        actual=actual_s,
        clima_ok=clima_ok,
    )
