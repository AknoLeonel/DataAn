"""Contrato de dados publicado pelo pipeline e consumido pelo site.

Tudo que sai do pipeline passa por estes modelos: se um campo mudar aqui,
o tipo correspondente em `web/src/lib/types.ts` precisa mudar junto.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = 1

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)]
StatusLevel = Literal["good", "warning", "serious", "critical"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fmt(_Model):
    """Como o site deve formatar um número (pt-BR)."""

    kind: Literal["number", "percent", "currency"] = "number"
    decimals: int = Field(default=0, ge=0, le=6)
    unit: str | None = None
    compact: bool = False
    grouping: bool = True  # False para anos: 2024, não 2.024


class Source(_Model):
    name: str
    url: str
    license: str | None = None


class RefLine(_Model):
    value: float
    label: str


class Series(_Model):
    key: str
    name: str
    points: list[tuple[str, float | None]]
    style: Literal["solid", "dashed"] = "solid"
    band: list[tuple[str, float, float]] | None = None
    # Slot categórico fixo (1-8). A cor acompanha a entidade, nunca a posição.
    color: int = Field(default=1, ge=1, le=8)


class LineChart(_Model):
    type: Literal["line"] = "line"
    id: Slug
    title: str
    subtitle: str | None = None
    format: Fmt
    series: list[Series] = Field(min_length=1)
    x_kind: Literal["date", "week", "month", "year"] = "date"
    step: bool = False
    y_zero: bool = False
    reference: list[RefLine] = Field(default_factory=list)
    marker: tuple[str, str] | None = None  # (x, rótulo), ex.: início da previsão
    note: str | None = None


class BarItem(_Model):
    label: str
    value: float
    highlight: bool = False
    note: str | None = None


class BarChart(_Model):
    """Barras horizontais: rankings e comparações entre categorias."""

    type: Literal["bar"] = "bar"
    id: Slug
    title: str
    subtitle: str | None = None
    format: Fmt
    items: list[BarItem] = Field(min_length=1)
    reference: list[RefLine] = Field(default_factory=list)
    highlight_label: str | None = None  # legenda das barras destacadas
    note: str | None = None


class ColumnChart(_Model):
    """Colunas verticais ao longo do tempo; `diverging` colore acima/abaixo de zero."""

    type: Literal["column"] = "column"
    id: Slug
    title: str
    subtitle: str | None = None
    format: Fmt
    items: list[BarItem] = Field(min_length=1)
    diverging: bool = False
    note: str | None = None


class GridChart(_Model):
    """Pequenos múltiplos: o mesmo gráfico de linha repetido por entidade."""

    type: Literal["grid"] = "grid"
    id: Slug
    title: str
    subtitle: str | None = None
    charts: list[LineChart] = Field(min_length=1)
    note: str | None = None


Chart = Annotated[LineChart | BarChart | ColumnChart | GridChart, Field(discriminator="type")]


def _round(v: float) -> float:
    return round(float(v), 6)


class Delta(_Model):
    value: float
    format: Fmt
    period: str
    good: Literal["up", "down", "neutral"] = "neutral"

    _r = field_validator("value")(_round)


class Kpi(_Model):
    label: str
    value: float
    format: Fmt
    delta: Delta | None = None
    spark: list[float] | None = None
    as_of: str | None = None
    status: StatusLevel | None = None
    status_label: str | None = None

    _r = field_validator("value")(_round)


class ModelInfo(_Model):
    name: str
    target: str
    horizon: str
    baseline: str
    mae: float
    mae_baseline: float
    skill: float
    notes: str | None = None


class Column(_Model):
    name: str
    description: str


class Dataset(_Model):
    schema_version: int = SCHEMA_VERSION
    slug: Slug
    title: str
    summary: str
    description: str
    category: Slug
    tags: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(min_length=1)
    frequency: str
    coverage: str | None = None
    updated_at: datetime
    data_until: str | None = None
    kpis: list[Kpi] = Field(default_factory=list)
    charts: list[Chart] = Field(min_length=1)
    insights: list[str] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)
    model: ModelInfo | None = None
    columns: list[Column] = Field(default_factory=list)
    rows: int = 0


class Category(_Model):
    slug: Slug
    name: str
    description: str
    count: int = 0


class CatalogEntry(_Model):
    slug: Slug
    title: str
    summary: str
    category: Slug
    tags: list[str]
    frequency: str
    updated_at: datetime
    data_until: str | None
    stale: bool
    sources: list[str]
    headline: Kpi | None = None


class Catalog(_Model):
    schema_version: int = SCHEMA_VERSION
    generated_at: datetime
    categories: list[Category]
    datasets: list[CatalogEntry]


class DatasetStatus(_Model):
    slug: Slug
    title: str
    ok: bool
    stale: bool
    error: str | None = None
    duration_s: float
    rows: int = 0
    updated_at: datetime | None = None
    data_until: str | None = None


class RunSummary(_Model):
    at: datetime
    ok: int
    failed: int
    results: dict[str, bool]


class Status(_Model):
    schema_version: int = SCHEMA_VERSION
    generated_at: datetime
    run_url: str | None = None
    duration_s: float
    datasets: list[DatasetStatus]
    history: list[RunSummary] = Field(default_factory=list)
