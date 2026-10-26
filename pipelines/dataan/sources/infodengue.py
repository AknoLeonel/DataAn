"""InfoDengue — sistema de alerta de arboviroses (Fiocruz / FGV).

Documentação: https://info.dengue.mat.br/services/api
A API devolve, por semana epidemiológica, os casos notificados e uma estimativa
de casos corrigida pelo atraso de notificação (nowcasting: `casos_est`).
"""

from __future__ import annotations

import pandas as pd

from dataan import http

URL = "https://info.dengue.mat.br/api/alertcity"
SITE = "https://info.dengue.mat.br/"

COLUMNS = [
    "date",
    "SE",
    "casos",
    "casos_est",
    "casos_est_min",
    "casos_est_max",
    "nivel",
    "p_inc100k",
    "Rt",
    "pop",
]


def alertcity(geocode: int, disease: str, year_start: int, year_end: int) -> pd.DataFrame:
    data = http.get_json(
        URL,
        params={
            "geocode": geocode,
            "disease": disease,
            "format": "json",
            "ew_start": 1,
            "ew_end": 53,
            "ey_start": year_start,
            "ey_end": year_end,
        },
    )
    if not data:
        raise http.FetchError(f"InfoDengue {geocode}: resposta vazia")
    df = pd.DataFrame(data)
    raw = df["data_iniSE"]
    if pd.api.types.is_numeric_dtype(raw):
        dates = pd.to_datetime(raw, unit="ms", errors="coerce")
    else:
        dates = pd.to_datetime(raw, errors="coerce")
    df["date"] = dates.dt.tz_localize(None).dt.normalize() if dates.dt.tz else dates.dt.normalize()
    for col in COLUMNS[1:]:
        if col not in df:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[COLUMNS].dropna(subset=["date", "casos_est"])
    df = df.drop_duplicates(subset="date", keep="last").sort_values("date").reset_index(drop=True)
    return df
