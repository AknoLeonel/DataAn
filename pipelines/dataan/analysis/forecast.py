"""Previsão de curto prazo com suavização exponencial (Holt amortecido) e backtest honesto.

O modelo é ajustado em log1p (contagens positivas e assimétricas). A qualidade
é medida por validação com origem móvel (só passado -> futuro) e comparada com
a previsão ingênua ("o próximo valor repete o último"). O intervalo de previsão
vem dos quantis empíricos dos erros do próprio backtest, por horizonte.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

ALPHAS = (0.2, 0.4, 0.6, 0.8, 0.95)
BETAS = (0.02, 0.1, 0.25)
PHIS = (0.8, 0.9, 0.98)


@dataclass
class Forecast:
    index: pd.DatetimeIndex
    mean: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    mae: float
    mae_naive: float
    skill: float
    params: tuple[float, float, float]
    coverage_level: float


def _sse_and_state(y: np.ndarray, alpha: float, beta: float, phi: float):
    level, trend = y[0], y[1] - y[0] if len(y) > 1 else 0.0
    sse = 0.0
    for t in range(1, len(y)):
        pred = level + phi * trend
        err = y[t] - pred
        sse += err * err
        new_level = alpha * y[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return sse, level, trend


def _fit(y: np.ndarray) -> tuple[tuple[float, float, float], float, float]:
    best = None
    for alpha, beta, phi in itertools.product(ALPHAS, BETAS, PHIS):
        sse, level, trend = _sse_and_state(y, alpha, beta, phi)
        if best is None or sse < best[0]:
            best = (sse, (alpha, beta, phi), level, trend)
    assert best is not None
    return best[1], best[2], best[3]


def _project(level: float, trend: float, phi: float, horizon: int) -> np.ndarray:
    damp = np.cumsum(phi ** np.arange(1, horizon + 1))
    return level + damp * trend


def holt_forecast(
    s: pd.Series,
    *,
    horizon: int = 4,
    backtest_origins: int = 26,
    level: float = 0.8,
) -> Forecast:
    """Previsão de `horizon` passos para uma série regular (ex.: semanal)."""
    s = s.dropna().astype(float)
    if len(s) < backtest_origins + horizon + 20:
        raise ValueError("Série curta demais para previsão com backtest")
    y = np.log1p(s.clip(lower=0).to_numpy())

    # Backtest com origem móvel: ajusta só com o passado de cada origem.
    errors_log = [[] for _ in range(horizon)]
    abs_err, abs_err_naive = [], []
    n = len(y)
    for origin in range(n - backtest_origins - horizon, n - horizon):
        train = y[: origin + 1]
        (alpha, beta, phi), lvl, trd = _fit(train)
        pred = _project(lvl, trd, phi, horizon)
        actual = y[origin + 1 : origin + 1 + horizon]
        for h in range(horizon):
            errors_log[h].append(actual[h] - pred[h])
        abs_err.extend(np.abs(np.expm1(actual) - np.expm1(pred)))
        abs_err_naive.extend(np.abs(np.expm1(actual) - np.expm1(train[-1])))

    params, lvl, trd = _fit(y)
    mean_log = _project(lvl, trd, params[2], horizon)
    q_lo, q_hi = (1 - level) / 2, 1 - (1 - level) / 2
    lo = np.array([np.quantile(errors_log[h], q_lo) for h in range(horizon)])
    hi = np.array([np.quantile(errors_log[h], q_hi) for h in range(horizon)])

    freq = pd.infer_freq(s.index[-8:]) or "7D"
    idx = pd.date_range(s.index[-1], periods=horizon + 1, freq=freq)[1:]
    mae = float(np.mean(abs_err))
    mae_naive = float(np.mean(abs_err_naive))
    return Forecast(
        index=idx,
        mean=np.clip(np.expm1(mean_log), 0, None),
        lower=np.clip(np.expm1(mean_log + lo), 0, None),
        upper=np.clip(np.expm1(mean_log + hi), 0, None),
        mae=mae,
        mae_naive=mae_naive,
        skill=float(1 - mae / mae_naive) if mae_naive > 0 else 0.0,
        params=params,
        coverage_level=level,
    )
