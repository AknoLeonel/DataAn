"""IBGE — API de agregados (SIDRA).

Documentação: https://servicodados.ibge.gov.br/api/docs/agregados?versao=3
O IBGE expõe os mesmos dados em dois servidores. O `servicodados` às vezes não
responde fora do Brasil (ex.: servidores de build nos EUA); nesse caso tentamos o
`apisidra`, que tem formato próprio (primeira linha = cabeçalho).
"""

from __future__ import annotations

import logging

import pandas as pd

from dataan import http

log = logging.getLogger(__name__)

URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{agregado}/periodos/{periodos}/variaveis/{variavel}"
SIDRA_API = "https://apisidra.ibge.gov.br/values/t/{agregado}/n3/all/v/{variavel}/p/{periodos}"
SIDRA = "https://sidra.ibge.gov.br/tabela/{agregado}"
COLUMNS = ["localidade_id", "localidade", "periodo", "valor"]

UF_SIGLAS = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}  # fmt: skip


def _servicodados(agregado: int, variavel: int, periodos: str) -> pd.DataFrame:
    data = http.get_json(
        URL.format(agregado=agregado, periodos=periodos, variavel=variavel),
        params={"localidades": "N3[all]"},
        retries=2,
    )
    rows = []
    for var in data or []:
        for res in var.get("resultados", []):
            for serie in res.get("series", []):
                loc = serie.get("localidade", {})
                for periodo, valor in (serie.get("serie") or {}).items():
                    rows.append([str(loc.get("id")), loc.get("nome"), str(periodo), valor])
    return pd.DataFrame(rows, columns=COLUMNS)


def _apisidra(agregado: int, variavel: int, periodos: str) -> pd.DataFrame:
    # "-2" (últimos 2 períodos) vira "last 2" na sintaxe do apisidra.
    n = periodos.lstrip("-") if periodos.startswith("-") else None
    p = f"last%20{n}" if n else periodos
    data = http.get_json(
        SIDRA_API.format(agregado=agregado, variavel=variavel, periodos=p),
        params={"formato": "json"},
        retries=2,
    )
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[0], dict):
        raise http.FetchError(f"apisidra {agregado}: resposta inesperada: {str(data)[:200]}")
    header, *body = data
    by_label = {label: key for key, label in header.items()}
    try:
        code_key = by_label["Unidade da Federação (Código)"]
        name_key = by_label["Unidade da Federação"]
        period_key = by_label["Ano"]
    except KeyError as exc:
        raise http.FetchError(f"apisidra {agregado}: cabeçalho sem {exc}") from exc
    rows = [[str(r[code_key]), r[name_key], str(r[period_key]), r["V"]] for r in body]
    return pd.DataFrame(rows, columns=COLUMNS)


def agregado(agregado: int, variavel: int, periodos: str = "-1") -> pd.DataFrame:
    """Valores por UF em formato longo: localidade_id, localidade, periodo, valor."""
    try:
        df = _servicodados(agregado, variavel, periodos)
    except http.FetchError as first:
        log.warning("IBGE servicodados indisponível (%s); tentando apisidra", first)
        try:
            df = _apisidra(agregado, variavel, periodos)
        except http.FetchError as second:
            raise http.FetchError(
                f"IBGE indisponível nos dois servidores — servicodados: {first} | apisidra: {second}"
            ) from second
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["valor"])
    if df.empty:
        raise http.FetchError(f"IBGE agregado {agregado}/{variavel}: sem valores")
    return df
