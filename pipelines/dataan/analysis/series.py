"""Utilitários de séries temporais: amostragem, pontos para gráfico e rótulos pt-BR."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_LONGOS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]  # fmt: skip


def lttb(y: np.ndarray, n_out: int) -> np.ndarray:
    """Largest-Triangle-Three-Buckets: índices que preservam a forma visual da série.

    Reduz séries longas (ex.: câmbio diário desde 2005) para poucas centenas de
    pontos sem apagar picos e vales, como faria uma média simples.
    """
    n = len(y)
    if n_out >= n or n_out < 3:
        return np.arange(n)
    x = np.arange(n, dtype=float)
    idx = [0]
    bucket = (n - 2) / (n_out - 2)
    a = 0
    for i in range(n_out - 2):
        # Balde i cobre os pontos do meio [start, end); a primeira e a última ficam fixas.
        start = int(math.floor(i * bucket)) + 1
        end = int(math.floor((i + 1) * bucket)) + 1
        nxt_start, nxt_end = end, min(int(math.floor((i + 2) * bucket)) + 1, n)
        if nxt_start >= nxt_end:
            avg_x, avg_y = x[-1], y[-1]
        else:
            avg_x, avg_y = x[nxt_start:nxt_end].mean(), y[nxt_start:nxt_end].mean()
        rng = slice(start, end)
        area = np.abs((x[a] - avg_x) * (y[rng] - y[a]) - (x[a] - x[rng]) * (avg_y - y[a]))
        a = start + int(np.argmax(area))
        idx.append(a)
    idx.append(n - 1)
    return np.array(idx)


def _num(v: float, decimals: int) -> float | None:
    if v is None or (isinstance(v, float) and not math.isfinite(v)) or pd.isna(v):
        return None
    return round(float(v), decimals)


def to_points(
    s: pd.Series, *, max_points: int | None = None, decimals: int = 4
) -> list[tuple[str, float | None]]:
    """Série indexada por data -> [(AAAA-MM-DD, valor)], com amostragem opcional."""
    s = s.sort_index()
    if max_points and len(s) > max_points:
        keep = lttb(s.to_numpy(dtype=float), max_points)
        s = s.iloc[keep]
    return [(ts.strftime("%Y-%m-%d"), _num(v, decimals)) for ts, v in s.items()]


def step_points(s: pd.Series, *, decimals: int = 4) -> list[tuple[str, float | None]]:
    """Para séries em degrau (ex.: Selic): só os pontos de mudança e o último."""
    s = s.sort_index()
    changed = s.ne(s.shift())
    changed.iloc[-1] = True
    return to_points(s[changed], decimals=decimals)


def br_date(ts: pd.Timestamp) -> str:
    return ts.strftime("%d/%m/%Y")


def month_label(ts: pd.Timestamp, long: bool = False) -> str:
    if long:
        return f"{MESES_LONGOS[ts.month - 1]} de {ts.year}"
    return f"{MESES[ts.month - 1]}/{ts.year}"


def fmt_num(v: float, decimals: int = 1) -> str:
    """Número em pt-BR para textos gerados (1.234,5)."""
    s = f"{v:,.{decimals}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def signed(v: float, decimals: int = 1) -> str:
    sign = "+" if v > 0 else ("−" if v < 0 else "")
    return f"{sign}{fmt_num(abs(v), decimals)}"


def value_at_or_before(s: pd.Series, ts: pd.Timestamp) -> float | None:
    sub = s[s.index <= ts]
    return float(sub.iloc[-1]) if len(sub) else None
