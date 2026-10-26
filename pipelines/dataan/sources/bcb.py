"""Banco Central do Brasil — Sistema Gerenciador de Séries Temporais (SGS).

Documentação: https://dadosabertos.bcb.gov.br/dataset/sgs
Desde 2025 o SGS limita consultas de séries diárias a janelas de 10 anos,
por isso a busca é feita em blocos.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

from dataan import http

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
PORTAL = "https://www3.bcb.gov.br/sgspub/"
CHUNK_YEARS = 5


@lru_cache(maxsize=64)
def _sgs(code: int, start: date, end: date) -> pd.Series:
    rows: list[dict] = []
    cur = start
    while cur <= end:
        chunk_end = min(end, date(cur.year + CHUNK_YEARS, cur.month, 1) - timedelta(days=1))
        data = http.get_json(
            URL.format(code=code),
            params={
                "formato": "json",
                "dataInicial": cur.strftime("%d/%m/%Y"),
                "dataFinal": chunk_end.strftime("%d/%m/%Y"),
            },
            not_found_ok=True,
        )
        if data:
            rows.extend(data)
        cur = chunk_end + timedelta(days=1)
    if not rows:
        raise http.FetchError(f"SGS {code}: nenhuma observação entre {start} e {end}")
    df = pd.DataFrame(rows)
    values = pd.to_numeric(
        df["valor"].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )
    index = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    s = pd.Series(values.to_numpy(), index=index, name=f"sgs_{code}")
    s = s[s.index.notna()].dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def sgs(code: int, start: date, end: date | None = None) -> pd.Series:
    """Série do SGS indexada por data. Valores numéricos, sem nulos, ordenada."""
    return _sgs(code, start, end or date.today()).copy()


def source_url(code: int) -> str:
    return f"{PORTAL}?codigoSerie={code}"
