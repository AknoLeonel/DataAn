"""Checagens de qualidade aplicadas antes de publicar qualquer dataset.

Se uma checagem falha, o dataset não é publicado nesta execução e o site
continua exibindo a última versão válida (marcada como desatualizada).
"""

from __future__ import annotations

import math

import pandas as pd

from dataan.models import BarChart, ColumnChart, Dataset, GridChart, LineChart


class DataQualityError(ValueError):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise DataQualityError(msg)


def check_series(
    s: pd.Series,
    name: str,
    *,
    min_points: int = 12,
    lo: float | None = None,
    hi: float | None = None,
    max_age_days: int | None = None,
) -> None:
    require(len(s) >= min_points, f"{name}: só {len(s)} pontos (mínimo {min_points})")
    require(bool(s.notna().all()), f"{name}: contém valores nulos")
    if lo is not None:
        require(bool((s >= lo).all()), f"{name}: valor abaixo de {lo} ({s.min()})")
    if hi is not None:
        require(bool((s <= hi).all()), f"{name}: valor acima de {hi} ({s.max()})")
    if max_age_days is not None and isinstance(s.index, pd.DatetimeIndex):
        age = (pd.Timestamp.now().normalize() - s.index.max()).days
        require(age <= max_age_days, f"{name}: último dado tem {age} dias (máx. {max_age_days})")


def _finite(v: float) -> bool:
    return v is not None and math.isfinite(v)


def check_dataset(ds: Dataset) -> None:
    """Invariantes do contrato que o Pydantic sozinho não garante."""
    for kpi in ds.kpis:
        require(_finite(kpi.value), f"KPI '{kpi.label}' não é finito")

    def check_line(c: LineChart) -> None:
        for s in c.series:
            require(len(s.points) > 0, f"Gráfico '{c.id}': série '{s.key}' vazia")
            xs = [p[0] for p in s.points]
            require(xs == sorted(xs), f"Gráfico '{c.id}': série '{s.key}' fora de ordem")
            require(
                any(p[1] is not None for p in s.points),
                f"Gráfico '{c.id}': série '{s.key}' sem valores",
            )

    for kpi in ds.kpis:
        if kpi.dots is not None and kpi.dot_labels is not None:
            require(len(kpi.dots) == len(kpi.dot_labels), f"KPI '{kpi.label}': pontos e rótulos")
        if kpi.range is not None:
            require(kpi.range.min < kpi.range.max, f"KPI '{kpi.label}': régua inválida")

    ids = set()
    for chart in ds.charts:
        require(chart.id not in ids, f"id de gráfico duplicado: {chart.id}")
        ids.add(chart.id)
        if isinstance(chart, LineChart):
            check_line(chart)
        elif isinstance(chart, GridChart):
            for sub in chart.charts:
                check_line(sub)
        elif isinstance(chart, (BarChart, ColumnChart)):
            require(all(_finite(i.value) for i in chart.items), f"'{chart.id}': valor inválido")

    lines = {c.id: c for c in ds.charts if isinstance(c, LineChart)}
    for h in ds.highlights:
        require(h.chart in lines, f"Destaque aponta para gráfico inexistente: {h.chart}")
        xs = {p[0] for s in lines[h.chart].series for p in s.points}
        require(h.at in xs, f"Destaque '{h.label}': ponto {h.at} fora do gráfico {h.chart}")
        require(h.start <= h.at <= h.end, f"Destaque '{h.label}': trecho inválido")
