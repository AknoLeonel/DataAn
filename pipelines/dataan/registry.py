"""Registro de datasets e categorias.

Adicionar um dataset ao ecossistema = escrever uma função decorada com
`@dataset(...)` em `dataan/datasets/<categoria>.py` que devolve um `Build`.
O runner descobre, executa, valida e publica automaticamente.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from dataan.models import Category, Chart, Column, Fmt, Highlight, Kpi, ModelInfo, Source

CATEGORIES: dict[str, Category] = {
    c.slug: c
    for c in [
        Category(
            slug="economia",
            name="Economia",
            description="Juros, inflação, câmbio e mercado de trabalho, direto do Banco Central.",
        ),
        Category(
            slug="saude",
            name="Saúde",
            description="Vigilância epidemiológica com estimativas corrigidas por atraso e previsões.",
        ),
        Category(
            slug="meio-ambiente",
            name="Meio ambiente",
            description="Qualidade do ar nas capitais comparada às diretrizes da OMS.",
        ),
        Category(
            slug="clima",
            name="Clima",
            description="Temperatura nas capitais e o quanto ela mudou nas últimas décadas.",
        ),
        Category(
            slug="demografia",
            name="Demografia",
            description="População dos estados e como ela cresce, segundo o IBGE.",
        ),
    ]
}


@dataclass
class Build:
    """O que a função de um dataset devolve. Metadados fixos ficam no decorador."""

    charts: list[Chart]
    table: pd.DataFrame
    kpis: list[Kpi] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)
    coverage: str | None = None
    data_until: str | None = None
    model: ModelInfo | None = None
    methodology: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DatasetSpec:
    slug: str
    title: str
    summary: str
    description: str
    category: str
    sources: tuple[Source, ...]
    frequency: str
    build: Callable[[], Build]
    tags: tuple[str, ...] = ()
    methodology: tuple[str, ...] = ()
    columns: tuple[Column, ...] = ()


REGISTRY: dict[str, DatasetSpec] = {}


def dataset(
    *,
    slug: str,
    title: str,
    summary: str,
    description: str,
    category: str,
    sources: list[Source],
    frequency: str,
    tags: list[str] | None = None,
    methodology: list[str] | None = None,
    columns: list[Column] | None = None,
) -> Callable[[Callable[[], Build]], Callable[[], Build]]:
    if category not in CATEGORIES:
        raise ValueError(f"Categoria desconhecida: {category}")

    def deco(fn: Callable[[], Build]) -> Callable[[], Build]:
        if slug in REGISTRY:
            raise ValueError(f"Dataset duplicado: {slug}")
        REGISTRY[slug] = DatasetSpec(
            slug=slug,
            title=title,
            summary=summary,
            description=description,
            category=category,
            sources=tuple(sources),
            frequency=frequency,
            build=fn,
            tags=tuple(tags or ()),
            methodology=tuple(methodology or ()),
            columns=tuple(columns or ()),
        )
        return fn

    return deco


# Atalhos de formatação usados pelos datasets.
def pct(decimals: int = 2, unit: str | None = None) -> Fmt:
    return Fmt(kind="percent", decimals=decimals, unit=unit)


def num(decimals: int = 0, unit: str | None = None, compact: bool = False) -> Fmt:
    return Fmt(kind="number", decimals=decimals, unit=unit, compact=compact)


def year() -> Fmt:
    return Fmt(kind="number", grouping=False)


def brl(decimals: int = 2) -> Fmt:
    return Fmt(kind="currency", decimals=decimals)


def pp(decimals: int = 2) -> Fmt:
    """Pontos percentuais (diferença entre duas taxas)."""
    return Fmt(kind="number", decimals=decimals, unit="p.p.")
