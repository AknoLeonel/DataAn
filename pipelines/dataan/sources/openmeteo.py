"""Open-Meteo — Air Quality API (modelo CAMS/Copernicus).

Documentação: https://open-meteo.com/en/docs/air-quality-api
Os valores são estimativas de modelo atmosférico na grade (~11 km na América
do Sul), não medições de estação. Licença dos dados: CC BY 4.0.
"""

from __future__ import annotations

import pandas as pd

from dataan import http

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
SITE = "https://open-meteo.com/en/docs/air-quality-api"
MIN_HOURS_PER_DAY = 18


def air_quality_daily(lat: float, lon: float, past_days: int = 92) -> pd.DataFrame:
    """Médias diárias (horário local de Brasília) de PM2.5 e PM10 em µg/m³."""
    data = http.get_json(
        AQ_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "pm2_5,pm10",
            "past_days": past_days,
            "forecast_days": 1,
            "timezone": "America/Sao_Paulo",
        },
    )
    hourly = (data or {}).get("hourly") or {}
    if not hourly.get("time"):
        raise http.FetchError(f"Open-Meteo ({lat},{lon}): resposta sem dados horários")
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(hourly["time"]),
            "pm2_5": pd.to_numeric(pd.Series(hourly.get("pm2_5")), errors="coerce"),
            "pm10": pd.to_numeric(pd.Series(hourly.get("pm10")), errors="coerce"),
        }
    )
    # Só dias já encerrados: o dia corrente e a previsão ficam de fora.
    today = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).normalize()
    df = df[df["time"] < today]
    df["date"] = df["time"].dt.normalize()
    grouped = df.groupby("date")
    daily = grouped[["pm2_5", "pm10"]].mean()
    counts = grouped["pm2_5"].count()
    daily = daily[counts >= MIN_HOURS_PER_DAY]
    return daily.reset_index()
