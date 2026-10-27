"""APIs públicas simuladas, no formato real de cada uma (sem rede, determinístico por dia).

Usado pelos testes para rodar os datasets de verdade de ponta a ponta. As séries são
sintéticas, relativas à data de hoje (as checagens de atraso da fonte dependem dela).
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta

import numpy as np

TODAY = date.today()


def bdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def sgs_values(code, start, end):
    out = []
    if code == 432:  # Selic: degraus
        for d in bdays(start, end):
            t = (d - date(2005, 1, 1)).days / 365.25
            v = 10 + 4 * math.sin(t / 2.2) + (3 if d.year >= 2024 else 0)
            v = round(round(v * 4) / 4, 2)
            if date(2020, 6, 1) <= d <= date(2021, 3, 1):
                v = 2.0
            out.append((d, v))
    elif code == 1:
        r = random.Random(code)  # noqa: S311 - dado sintético
        v = 2.6
        d0 = date(2005, 1, 1)
        for d in bdays(d0, end):
            v *= math.exp(r.gauss(0.00012, 0.009))
            if d >= start:
                out.append((d, round(v, 4)))
    else:
        d = date(start.year, start.month, 1)
        while d <= end - timedelta(days=40):
            t = d.year + d.month / 12
            if code == 433:
                v = 0.35 + 0.25 * math.sin(t * 3.1) + (0.5 if 2021 <= d.year <= 2022 else 0)
            elif code == 13522:
                v = 4.2 + 2.2 * math.sin(t / 1.3) + (4 if 2021.5 <= t <= 2022.8 else 0)
            else:  # 24369 desemprego
                v = 9 + 4 * math.sin((t - 2012) / 4) - (t - 2020) * 0.3 * (t > 2020)
            out.append((d, round(v, 2)))
            d = (d + timedelta(days=32)).replace(day=1)
    return [{"data": d.strftime("%d/%m/%Y"), "valor": f"{v:.2f}"} for d, v in out]


def infodengue(params):
    geo = params["geocode"]
    r = np.random.default_rng(geo % 1000)
    start = date(params["ey_start"], 1, 1)
    d = start - timedelta(days=start.weekday() + 1)
    rows = []
    scale = 200 + geo % 700
    while d <= TODAY - timedelta(days=7):
        week = d.isocalendar().week
        season = math.exp(2.4 * math.cos((week - 14) / 52 * 2 * math.pi))
        boost = 3.5 if d.year == 2024 else 1
        est = scale * season * boost * r.lognormal(0, 0.15) / 8
        rows.append(
            {
                "data_iniSE": int(datetime(d.year, d.month, d.day).timestamp() * 1000),
                "SE": d.isocalendar().year * 100 + week,
                "casos_est": round(est, 1),
                "casos_est_min": int(est * 0.8),
                "casos_est_max": int(est * 1.3),
                "casos": int(est * 0.9),
                "p_rt1": 0.4,
                "p_inc100k": est / 30,
                "Localidade_id": 0,
                "nivel": 1 + min(3, int(season * boost / 3)),
                "id": 1,
                "versao_modelo": "2025-01-01",
                "Rt": 0.9 + 0.2 * r.random(),
                "pop": 1_000_000 + geo % 5_000_000,
                "tempmin": 18,
                "tempmed": round(
                    24 + 3 * math.cos((week - 6) / 52 * 2 * math.pi) + r.normal(0, 0.8), 1
                ),
                "umidmed": round(
                    72 + 8 * math.cos((week - 10) / 52 * 2 * math.pi) + r.normal(0, 3), 1
                ),
                "umidmax": 80,
            }
        )
        d += timedelta(days=7)
    return list(reversed(rows))


def open_meteo(params):
    lat = params["latitude"]
    r = np.random.default_rng(int(abs(lat) * 100))
    base = (
        6 + abs(lat + 10) / 3 + (12 if lat > -16 and lat < -3 and params["longitude"] < -55 else 0)
    )
    start = datetime.combine(TODAY - timedelta(days=params["past_days"]), datetime.min.time())
    times, pm25, pm10 = [], [], []
    for h in range((params["past_days"] + params["forecast_days"]) * 24):
        t = start + timedelta(hours=h)
        times.append(t.strftime("%Y-%m-%dT%H:%M"))
        v = base * (1 + 0.4 * math.sin(h / 24 * 2 * math.pi)) * r.lognormal(0, 0.25)
        pm25.append(round(v, 1))
        pm10.append(round(v * 1.6, 1))
    return {
        "latitude": lat,
        "hourly_units": {"pm2_5": "μg/m³"},
        "hourly": {"time": times, "pm2_5": pm25, "pm10": pm10},
    }


def nasa(params):
    lat = params["latitude"]
    r = np.random.default_rng(int(abs(lat) * 10))
    base = 27 - abs(lat) * 0.35
    out = {}
    for y in range(params["start"], params["end"] + 1):
        annual = (
            base
            + 0.025 * (y - 1981)
            + r.normal(0, 0.25)
            + (0.4 if y in (2015, 2016, 2023, 2024) else 0)
        )
        for m in range(1, 13):
            out[f"{y}{m:02d}"] = round(annual + 2 * math.cos(m / 12 * 2 * math.pi), 2)
        out[f"{y}13"] = round(annual, 2)
    return {"type": "Feature", "properties": {"parameter": {"T2M": out}}}


UFS = {
    "11": ("Rondônia", 1.75),
    "12": ("Acre", 0.88),
    "13": ("Amazonas", 4.28),
    "14": ("Roraima", 0.72),
    "15": ("Pará", 8.66),
    "16": ("Amapá", 0.80),
    "17": ("Tocantins", 1.58),
    "21": ("Maranhão", 7.01),
    "22": ("Piauí", 3.38),
    "23": ("Ceará", 9.23),
    "24": ("Rio Grande do Norte", 3.45),
    "25": ("Paraíba", 4.15),
    "26": ("Pernambuco", 9.54),
    "27": ("Alagoas", 3.22),
    "28": ("Sergipe", 2.29),
    "29": ("Bahia", 14.85),
    "31": ("Minas Gerais", 21.32),
    "32": ("Espírito Santo", 4.10),
    "33": ("Rio de Janeiro", 17.22),
    "35": ("São Paulo", 46.08),
    "41": ("Paraná", 11.82),
    "42": ("Santa Catarina", 8.06),
    "43": ("Rio Grande do Sul", 11.23),
    "50": ("Mato Grosso do Sul", 2.90),
    "51": ("Mato Grosso", 3.84),
    "52": ("Goiás", 7.35),
    "53": ("Distrito Federal", 2.98),
}


def ibge(url):
    series = []
    for uid, (name, mi) in UFS.items():
        g = 1 + (int(uid) % 7) / 1000
        series.append(
            {
                "localidade": {
                    "id": uid,
                    "nivel": {"id": "N3", "nome": "Unidade da Federação"},
                    "nome": name,
                },
                "serie": {"2024": str(int(mi * 1e6)), "2025": str(int(mi * 1e6 * g))},
            }
        )
    return [
        {
            "id": "9324",
            "variavel": "População residente estimada",
            "unidade": "Pessoas",
            "resultados": [{"classificacoes": [], "series": series}],
        }
    ]


def get_json(url, params=None, **kw):
    params = params or {}
    if "bcdata.sgs" in url:
        code = int(url.split("bcdata.sgs.")[1].split("/")[0])
        s = datetime.strptime(params["dataInicial"], "%d/%m/%Y").date()
        e = datetime.strptime(params["dataFinal"], "%d/%m/%Y").date()
        return sgs_values(code, s, e) or None
    if "info.dengue" in url:
        return infodengue(params)
    if "air-quality" in url:
        return open_meteo(params)
    if "power.larc" in url:
        return nasa(params)
    if "servicodados.ibge" in url:
        return ibge(url)
    raise AssertionError(url)
