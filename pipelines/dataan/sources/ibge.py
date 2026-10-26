"""IBGE — API de agregados (SIDRA).

Documentação: https://servicodados.ibge.gov.br/api/docs/agregados?versao=3
"""

from __future__ import annotations

import pandas as pd

from dataan import http

URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{agregado}/periodos/{periodos}/variaveis/{variavel}"
SIDRA = "https://sidra.ibge.gov.br/tabela/{agregado}"

UF_SIGLAS = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}  # fmt: skip


def agregado(
    agregado: int, variavel: int, periodos: str = "-1", localidades: str = "N3[all]"
) -> pd.DataFrame:
    """Formato longo: localidade_id, localidade, periodo, valor."""
    data = http.get_json(
        URL.format(agregado=agregado, periodos=periodos, variavel=variavel),
        params={"localidades": localidades},
    )
    rows = []
    for var in data or []:
        for res in var.get("resultados", []):
            for serie in res.get("series", []):
                loc = serie.get("localidade", {})
                for periodo, valor in (serie.get("serie") or {}).items():
                    rows.append(
                        {
                            "localidade_id": str(loc.get("id")),
                            "localidade": loc.get("nome"),
                            "periodo": str(periodo),
                            "valor": pd.to_numeric(valor, errors="coerce"),
                        }
                    )
    df = pd.DataFrame(rows).dropna(subset=["valor"])
    if df.empty:
        raise http.FetchError(f"IBGE agregado {agregado}/{variavel}: sem valores")
    return df
