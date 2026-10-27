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
CHUNK_YEARS = 9  # janela máxima do SGS para séries diárias é 10 anos


def _check_rows(data: object) -> str | None:
    """O SGS às vezes responde 200 com um objeto de erro em vez da lista de observações."""
    if data is None or data == []:
        return None
    if isinstance(data, list) and all(
        isinstance(r, dict) and "data" in r and "valor" in r for r in data
    ):
        return None
    if isinstance(data, dict):
        return str(data.get("erro") or data.get("error") or data)[:200]
    return str(data)[:200]


def _fetch_chunk(code: int, start: date, end: date) -> list[dict]:
    """Um bloco de datas; vazio quando o SGS não tem observações no intervalo (404 ou [])."""
    data = http.get_json(
        URL.format(code=code),
        params={
            "formato": "json",
            "dataInicial": start.strftime("%d/%m/%Y"),
            "dataFinal": end.strftime("%d/%m/%Y"),
        },
        not_found_ok=True,
        retries=2,  # erro no corpo costuma ser determinístico: duas novas tentativas bastam
        validate=_check_rows,
    )
    return data or []


@lru_cache(maxsize=64)
def _sgs(code: int, start: date, end: date) -> pd.Series:
    rows: list[dict] = []
    cur = start
    while cur <= end:
        chunk_end = min(end, date(cur.year + CHUNK_YEARS, cur.month, 1) - timedelta(days=1))
        chunk = _fetch_chunk(code, cur, chunk_end)
        # Bloco vazio antes do início da série é normal; depois dele, é uma lacuna que
        # sumiria em silêncio (exceto um último bloco curto, sem divulgação nova ainda).
        short_tail = chunk_end == end and (chunk_end - cur).days < 62
        if not chunk and rows and not short_tail:
            raise http.FetchError(
                f"SGS {code}: bloco {cur:%d/%m/%Y}–{chunk_end:%d/%m/%Y} veio vazio no meio da série"
            )
        rows.extend(chunk)
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
