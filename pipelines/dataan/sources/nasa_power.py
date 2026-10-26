"""NASA POWER — médias mensais e anuais de variáveis meteorológicas (reanálise MERRA-2).

Documentação: https://power.larc.nasa.gov/docs/services/api/temporal/monthly/
A chave "AAAA13" de cada ano traz a média anual. -999 indica dado ausente.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from dataan import http

URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
SITE = "https://power.larc.nasa.gov/"
MISSING = -999


def annual_mean(lat: float, lon: float, start_year: int, parameter: str = "T2M") -> pd.Series:
    """Média anual do parâmetro para anos completos, indexada por ano (int)."""
    last_error: Exception | None = None
    # O ano anterior pode ainda não estar consolidado no início do ano: recua um ano.
    for end_year in (date.today().year - 1, date.today().year - 2):
        try:
            data = http.get_json(
                URL,
                params={
                    "parameters": parameter,
                    "community": "AG",
                    "latitude": lat,
                    "longitude": lon,
                    "start": start_year,
                    "end": end_year,
                    "format": "JSON",
                },
                retries=2,
            )
        except http.FetchError as exc:
            last_error = exc
            continue
        values = (((data or {}).get("properties") or {}).get("parameter") or {}).get(parameter)
        if not values:
            last_error = http.FetchError("NASA POWER: resposta sem o parâmetro pedido")
            continue
        annual = {
            int(k[:4]): float(v)
            for k, v in values.items()
            if k.endswith("13") and len(k) == 6 and v is not None and float(v) != MISSING
        }
        if annual:
            return pd.Series(annual, name=parameter).sort_index()
    raise http.FetchError(f"NASA POWER ({lat},{lon}): {last_error}")
