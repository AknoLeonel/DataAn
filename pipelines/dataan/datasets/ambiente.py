"""Meio ambiente e clima: qualidade do ar (Open-Meteo/CAMS) e aquecimento (NASA POWER)."""

from __future__ import annotations

import pandas as pd

from dataan.analysis.quality import check_series, require
from dataan.analysis.series import br_date, fmt_num, signed, to_points
from dataan.models import (
    BarChart,
    BarItem,
    Column,
    ColumnChart,
    Kpi,
    LineChart,
    RefLine,
    Series,
    Source,
)
from dataan.registry import Build, dataset, num, year
from dataan.sources import nasa_power, openmeteo

# (cidade, UF, latitude, longitude)
CAPITALS = [
    ("São Paulo", "SP", -23.55, -46.63),
    ("Rio de Janeiro", "RJ", -22.91, -43.17),
    ("Belo Horizonte", "MG", -19.92, -43.94),
    ("Brasília", "DF", -15.79, -47.88),
    ("Salvador", "BA", -12.97, -38.50),
    ("Fortaleza", "CE", -3.73, -38.52),
    ("Recife", "PE", -8.05, -34.88),
    ("Porto Alegre", "RS", -30.03, -51.23),
    ("Curitiba", "PR", -25.43, -49.27),
    ("Manaus", "AM", -3.12, -60.02),
    ("Porto Velho", "RO", -8.76, -63.90),
    ("Cuiabá", "MT", -15.60, -56.10),
]
WHO_PM25_24H = 15.0  # Diretriz da OMS (2021) para média de 24 h de PM2.5, µg/m³
UG = "µg/m³"


@dataset(
    slug="qualidade-do-ar",
    title="Qualidade do ar nas capitais",
    summary="Partículas finas (PM2.5) nos últimos 90 dias comparadas à diretriz da OMS.",
    description=(
        "Material particulado fino (PM2.5) penetra fundo nos pulmões e é o poluente do ar mais "
        "associado a danos à saúde. Comparamos a média diária em 12 capitais com a diretriz de "
        "24 horas da Organização Mundial da Saúde, incluindo cidades afetadas pela temporada de "
        "queimadas na Amazônia e no Centro-Oeste."
    ),
    category="meio-ambiente",
    sources=[
        Source(
            name="Open-Meteo Air Quality API (Copernicus CAMS)",
            url=openmeteo.SITE,
            license="CC BY 4.0",
        )
    ],
    frequency="Diária",
    tags=["poluição", "PM2.5", "OMS", "queimadas", "saúde"],
    methodology=[
        "Valores horários de PM2.5 e PM10 do modelo CAMS (Copernicus) no ponto central de cada "
        "capital, agregados em média diária no horário de Brasília. Dias com menos de 18 horas "
        "de dados são descartados.",
        "Atenção: são estimativas de modelo atmosférico (grade de ~11 km), não medições de "
        "estações. Servem para comparar tendências e cidades, não para fiscalização.",
        f"Referência: diretriz da OMS (2021) de {fmt_num(WHO_PM25_24H, 0)} {UG} para a média de "
        "24 horas de PM2.5.",
    ],
    columns=[
        Column(name="data", description="Dia (AAAA-MM-DD)"),
        Column(name="cidade", description="Capital"),
        Column(name="uf", description="Unidade da federação"),
        Column(name="pm2_5", description=f"Média diária de PM2.5, {UG}"),
        Column(name="pm10", description=f"Média diária de PM10, {UG}"),
    ],
)
def qualidade_do_ar() -> Build:
    frames = []
    for city, uf, lat, lon in CAPITALS:
        daily = openmeteo.air_quality_daily(lat, lon)
        check_series(
            daily.set_index("date")["pm2_5"].dropna(),
            f"PM2.5 {city}",
            min_points=30,
            lo=0,
            hi=1000,
            max_age_days=5,
        )
        frames.append(daily.assign(cidade=city, uf=uf))
    df = pd.concat(frames, ignore_index=True).dropna(subset=["pm2_5"])
    last_day = df["date"].max()
    last30 = df[df["date"] > last_day - pd.Timedelta(days=30)]
    avg30 = last30.groupby("cidade")["pm2_5"].mean().sort_values(ascending=False)
    above = (
        df[df["pm2_5"] > WHO_PM25_24H].groupby("cidade").size().reindex(avg30.index, fill_value=0)
    )
    days = df["date"].nunique()
    total_above = int(above.sum())
    worst_city, worst_val = avg30.index[0], float(avg30.iloc[0])
    best_city, best_val = avg30.index[-1], float(avg30.iloc[-1])

    worst_day = df.loc[df["pm2_5"].idxmax()]
    kpis = [
        Kpi(
            label="Pior média (30 dias)",
            value=worst_val,
            format=num(1, UG),
            as_of=worst_city,
            status="serious" if worst_val > WHO_PM25_24H else "good",
            status_label="Acima da diretriz da OMS"
            if worst_val > WHO_PM25_24H
            else "Dentro da diretriz da OMS",
        ),
        Kpi(
            label="Dias-cidade acima da OMS",
            value=total_above,
            format=num(0, unit=f"de {days * len(CAPITALS)}"),
        ),
        Kpi(
            label="Pico diário no período",
            value=float(worst_day["pm2_5"]),
            format=num(1, UG),
            as_of=f"{worst_day['cidade']}, {br_date(worst_day['date'])}",
        ),
    ]
    insights = [
        f"Nos últimos 30 dias, {worst_city} teve a pior média de PM2.5 ({fmt_num(worst_val, 1)} {UG}) "
        f"e {best_city} a melhor ({fmt_num(best_val, 1)} {UG}).",
        f"Em {days} dias analisados, houve {total_above} registros diários acima da diretriz da OMS "
        f"({fmt_num(WHO_PM25_24H, 0)} {UG}) somando as {len(CAPITALS)} capitais.",
    ]
    if above.max() > 0:
        insights.append(
            f"{above.idxmax()} foi a capital com mais dias acima da diretriz: {int(above.max())} de {days}."
        )

    top3 = list(avg30.index[:3])
    series = []
    for i, city in enumerate(top3):
        s = df[df["cidade"] == city].set_index("date")["pm2_5"].sort_index()
        series.append(Series(key=f"c{i}", name=city, points=to_points(s, decimals=1), color=i + 1))

    bars = [
        BarItem(label=c, value=round(float(v), 1), highlight=bool(v > WHO_PM25_24H))
        for c, v in avg30.items()
    ]
    charts = [
        BarChart(
            id="ranking-30-dias",
            title="Média de PM2.5 nos últimos 30 dias",
            subtitle=f"{UG}; linha = diretriz de 24 h da OMS",
            format=num(1),
            items=bars,
            reference=[RefLine(value=WHO_PM25_24H, label="OMS")],
            highlight_label="Acima da diretriz da OMS",
        ),
        LineChart(
            id="diario-mais-poluidas",
            title="Média diária nas 3 capitais mais poluídas",
            subtitle=f"PM2.5, {UG}",
            format=num(0),
            series=series,
            y_zero=True,
            reference=[RefLine(value=WHO_PM25_24H, label="OMS")],
        ),
    ]
    table = df[["date", "cidade", "uf", "pm2_5", "pm10"]].rename(columns={"date": "data"})
    table[["pm2_5", "pm10"]] = table[["pm2_5", "pm10"]].round(2)
    table["data"] = table["data"].dt.strftime("%Y-%m-%d")
    return Build(
        charts=charts,
        table=table.sort_values(["data", "cidade"]),
        kpis=kpis,
        insights=insights,
        coverage=f"{br_date(df['date'].min())} a {br_date(last_day)}",
        data_until=br_date(last_day),
    )


# --------------------------------------------------------------------------- Clima

BASELINE = (1991, 2020)
CLIMATE_CAPITALS = [c for c in CAPITALS if c[0] not in {"Porto Velho", "Cuiabá"}][:8]


@dataset(
    slug="temperatura-capitais",
    title="Aquecimento nas capitais",
    summary="Quanto a temperatura média anual mudou desde 1981 em oito capitais.",
    description=(
        "Temperatura média anual a 2 metros do solo em oito capitais brasileiras, a partir da "
        "reanálise MERRA-2 disponibilizada pelo projeto NASA POWER. Mostramos a anomalia de cada "
        "ano em relação à normal climatológica de 1991–2020 e o aquecimento de cada cidade."
    ),
    category="clima",
    sources=[
        Source(
            name="NASA POWER — médias mensais (MERRA-2)",
            url=nasa_power.SITE,
            license="Dados públicos da NASA",
        )
    ],
    frequency="Anual",
    tags=["temperatura", "aquecimento global", "anomalia", "NASA"],
    methodology=[
        "Média anual de T2M (temperatura do ar a 2 m) no ponto de cada capital, apenas anos "
        "completos.",
        f"Anomalia: diferença entre o ano e a média de {BASELINE[0]}–{BASELINE[1]} da própria "
        "cidade; o gráfico mostra a média das anomalias das oito capitais.",
        "Aquecimento por capital: média dos últimos 10 anos menos a média de 1981–1990.",
        "Reanálise combina modelo e observações; pode diferir de estações locais do INMET.",
    ],
    columns=[
        Column(name="ano", description="Ano"),
        Column(name="cidade", description="Capital"),
        Column(name="uf", description="Unidade da federação"),
        Column(name="temperatura_media", description="Temperatura média anual, °C"),
        Column(
            name="anomalia", description=f"Diferença para a média {BASELINE[0]}–{BASELINE[1]}, °C"
        ),
    ],
)
def temperatura_capitais() -> Build:
    per_city: dict[str, pd.Series] = {}
    rows = []
    for city, uf, lat, lon in CLIMATE_CAPITALS:
        s = nasa_power.annual_mean(lat, lon, start_year=1981)
        require(len(s) >= 35, f"Temperatura {city}: série curta ({len(s)} anos)")
        check_series(s, f"Temperatura {city}", min_points=35, lo=-10, hi=40)
        base = s.loc[BASELINE[0] : BASELINE[1]].mean()
        anomaly = s - base
        per_city[city] = anomaly
        rows.append(
            pd.DataFrame(
                {
                    "ano": s.index,
                    "cidade": city,
                    "uf": uf,
                    "temperatura_media": s.round(2).values,
                    "anomalia": anomaly.round(3).values,
                }
            )
        )
    anomalies = pd.concat(per_city, axis=1).dropna()
    mean_anom = anomalies.mean(axis=1)
    last_year = int(mean_anom.index[-1])
    hottest_year = int(mean_anom.idxmax())

    warming = {}
    for city, anom in per_city.items():
        recent = anom.loc[last_year - 9 : last_year].mean()
        early = anom.loc[1981:1990].mean()
        warming[city] = float(recent - early)
    warming_s = pd.Series(warming).sort_values(ascending=False)

    kpis = [
        Kpi(
            label=f"Anomalia de {last_year}",
            value=float(mean_anom.iloc[-1]),
            format=num(2, "°C"),
            spark=[round(v, 2) for v in mean_anom.iloc[-12:].tolist()],
            as_of=f"vs. {BASELINE[0]}–{BASELINE[1]}",
        ),
        Kpi(
            label="Ano mais quente",
            value=hottest_year,
            format=year(),
            as_of=f"{signed(float(mean_anom.max()), 2)} °C",
        ),
        Kpi(
            label="Aquecimento médio",
            value=float(warming_s.mean()),
            format=num(2, "°C"),
            as_of=f"{last_year - 9}–{last_year} vs. 1981–1990",
        ),
    ]
    top5 = mean_anom.sort_values(ascending=False).index[:5]
    insights = [
        f"Em média, as oito capitais ficaram {signed(float(warming_s.mean()), 2)} °C mais quentes na "
        f"última década ({last_year - 9}–{last_year}) do que em 1981–1990.",
        f"{warming_s.index[0]} foi a que mais aqueceu ({signed(float(warming_s.iloc[0]), 2)} °C).",
        f"Os cinco anos mais quentes da série foram: {', '.join(str(y) for y in sorted(top5))}.",
    ]
    charts = [
        ColumnChart(
            id="anomalia-anual",
            title="Anomalia de temperatura média das capitais",
            subtitle=f"°C em relação à média de {BASELINE[0]}–{BASELINE[1]}",
            format=num(2, "°C"),
            diverging=True,
            items=[BarItem(label=str(y), value=round(float(v), 3)) for y, v in mean_anom.items()],
        ),
        BarChart(
            id="aquecimento-por-capital",
            title="Aquecimento por capital",
            subtitle=f"°C, média {last_year - 9}–{last_year} menos média 1981–1990",
            format=num(2, "°C"),
            items=[BarItem(label=c, value=round(v, 2)) for c, v in warming_s.items()],
        ),
    ]
    return Build(
        charts=charts,
        table=pd.concat(rows, ignore_index=True),
        kpis=kpis,
        insights=insights,
        coverage=f"{int(mean_anom.index[0])}–{last_year}",
        data_until=str(last_year),
    )
