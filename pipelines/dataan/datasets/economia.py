"""Economia: juros, inflação, câmbio e desemprego (Banco Central — SGS)."""

from __future__ import annotations

from datetime import date

import pandas as pd

from dataan.analysis.quality import check_series
from dataan.analysis.series import (
    br_date,
    fmt_num,
    month_label,
    signed,
    step_points,
    to_points,
    value_at_or_before,
)
from dataan.models import (
    BarItem,
    Column,
    ColumnChart,
    Delta,
    Kpi,
    LineChart,
    RefLine,
    Series,
    Source,
)
from dataan.registry import Build, brl, dataset, num, pct, pp
from dataan.sources import bcb

LICENSE = "Dados abertos do Banco Central do Brasil"


def _src(code: int, name: str) -> Source:
    return Source(
        name=f"Banco Central do Brasil — SGS {code} ({name})",
        url=bcb.source_url(code),
        license=LICENSE,
    )


def _monthly(s: pd.Series) -> pd.Series:
    """Indexa uma série mensal do SGS pelo primeiro dia do mês."""
    out = s.copy()
    out.index = out.index.to_period("M").to_timestamp()
    return out[~out.index.duplicated(keep="last")]


# --------------------------------------------------------------------------- Selic


@dataset(
    slug="selic",
    title="Taxa Selic e juro real",
    summary="A taxa básica de juros definida pelo Copom e quanto ela rende acima da inflação.",
    description=(
        "A Selic é a taxa básica de juros da economia brasileira, definida a cada 45 dias "
        "pelo Comitê de Política Monetária (Copom). Ela influencia o custo do crédito, o "
        "rendimento de investimentos e a inflação. Aqui você acompanha a meta da Selic e o "
        "juro real: a Selic descontada da inflação acumulada em 12 meses."
    ),
    category="economia",
    sources=[_src(432, "Meta Selic"), _src(13522, "IPCA acumulado em 12 meses")],
    frequency="Diária (muda nas reuniões do Copom)",
    tags=["juros", "Copom", "política monetária", "inflação"],
    methodology=[
        "Meta Selic: série 432 do SGS, em % ao ano, registrada a cada dia útil.",
        "Juro real ex-post: (1 + Selic) / (1 + IPCA 12 meses) − 1, usando a Selic do último "
        "dia de cada mês e o IPCA acumulado em 12 meses do mesmo mês.",
    ],
    columns=[
        Column(name="mes", description="Mês de referência (AAAA-MM-01)"),
        Column(name="selic_meta", description="Meta Selic no fim do mês, % ao ano"),
        Column(name="ipca_12m", description="IPCA acumulado em 12 meses, %"),
        Column(name="juro_real", description="Juro real ex-post, % ao ano"),
    ],
)
def selic() -> Build:
    start = date(date.today().year - 20, 1, 1)
    s = bcb.sgs(432, start)
    check_series(s, "Selic", min_points=500, lo=0, hi=60, max_age_days=10)
    ipca12 = _monthly(bcb.sgs(13522, start))

    selic_m = s.resample("MS").last()
    df = pd.concat({"selic_meta": selic_m, "ipca_12m": ipca12}, axis=1).dropna()
    df["juro_real"] = ((1 + df["selic_meta"] / 100) / (1 + df["ipca_12m"] / 100) - 1) * 100

    last_date, current = s.index[-1], float(s.iloc[-1])
    year_ago = value_at_or_before(s, last_date - pd.Timedelta(days=365))
    moves = s[s.diff().fillna(0) != 0]
    move_date = moves.index[-1] if len(moves) else s.index[0]
    move_size = float(s.diff().loc[move_date]) if len(moves) else 0.0
    real_now = float(df["juro_real"].iloc[-1])
    real_rank = float((df["juro_real"] < real_now).mean() * 100)

    kpis = [
        Kpi(
            label="Meta Selic",
            value=current,
            format=pct(2, "a.a."),
            delta=Delta(
                value=current - (year_ago if year_ago is not None else current),
                format=pp(2),
                period="em 12 meses",
            ),
            spark=[round(v, 2) for v in selic_m.iloc[-12:].tolist()],
            as_of=br_date(last_date),
        ),
        Kpi(
            label="Juro real (ex-post)",
            value=real_now,
            format=pct(2, "a.a."),
            spark=[round(v, 2) for v in df["juro_real"].iloc[-12:].tolist()],
            as_of=month_label(df.index[-1]),
        ),
        Kpi(
            label="Último movimento do Copom",
            value=move_size,
            format=pp(2),
            as_of=br_date(move_date),
        ),
    ]

    if move_size > 0:
        move_txt = f"uma alta de {fmt_num(move_size, 2)} p.p."
    elif move_size < 0:
        move_txt = f"um corte de {fmt_num(-move_size, 2)} p.p."
    else:
        move_txt = "a manutenção da taxa"
    insights = [
        f"A meta Selic está em {fmt_num(current, 2)}% ao ano desde {br_date(move_date)}; "
        f"a última mudança foi {move_txt}.",
        f"Descontada a inflação de 12 meses, o juro real está em {fmt_num(real_now, 2)}% ao ano, "
        f"acima do registrado em {fmt_num(real_rank, 0)}% dos meses desde {df.index[0].year}.",
    ]
    if year_ago is not None:
        diff = current - year_ago
        verb = "subiu" if diff > 0 else ("caiu" if diff < 0 else "ficou estável")
        tail = f" {fmt_num(abs(diff), 2)} p.p." if diff else ""
        insights.append(f"Em 12 meses, a taxa {verb}{tail}.")

    charts = [
        LineChart(
            id="historico",
            title=f"Meta Selic desde {s.index[0].year}",
            subtitle="% ao ano",
            format=pct(2),
            series=[Series(key="selic", name="Meta Selic", points=step_points(s), color=1)],
            step=True,
            y_zero=True,
        ),
        LineChart(
            id="juro-real",
            title="Juro real ex-post",
            subtitle="Selic menos a inflação acumulada em 12 meses, % ao ano",
            format=pct(1),
            series=[
                Series(
                    key="juro_real", name="Juro real", points=to_points(df["juro_real"], decimals=3)
                )
            ],
            reference=[RefLine(value=0, label="0%")],
        ),
    ]
    table = df.round(4).reset_index(names="mes")
    table["mes"] = table["mes"].dt.strftime("%Y-%m-%d")
    return Build(
        charts=charts,
        table=table,
        kpis=kpis,
        insights=insights,
        coverage=f"{s.index[0].year}–{last_date.year}",
        data_until=br_date(last_date),
    )


# --------------------------------------------------------------------------- IPCA

# Metas de inflação do CMN: ano -> (centro, tolerância), em %.
INFLATION_TARGETS = {
    2005: (4.5, 2.5), 2006: (4.5, 2.0), 2007: (4.5, 2.0), 2008: (4.5, 2.0), 2009: (4.5, 2.0),
    2010: (4.5, 2.0), 2011: (4.5, 2.0), 2012: (4.5, 2.0), 2013: (4.5, 2.0), 2014: (4.5, 2.0),
    2015: (4.5, 2.0), 2016: (4.5, 2.0), 2017: (4.5, 1.5), 2018: (4.5, 1.5), 2019: (4.25, 1.5),
    2020: (4.0, 1.5), 2021: (3.75, 1.5), 2022: (3.5, 1.5), 2023: (3.25, 1.5), 2024: (3.0, 1.5),
}  # fmt: skip
CURRENT_TARGET = (3.0, 1.5)  # meta contínua desde 2025


def _target(year: int) -> tuple[float, float]:
    return INFLATION_TARGETS.get(year, CURRENT_TARGET)


@dataset(
    slug="ipca",
    title="Inflação (IPCA)",
    summary="A inflação oficial do Brasil, mês a mês e em 12 meses, comparada à meta.",
    description=(
        "O IPCA, calculado pelo IBGE, é o índice oficial de inflação do país e a referência do "
        "sistema de metas do Conselho Monetário Nacional. Acompanhe a inflação acumulada em 12 "
        "meses frente ao centro e ao teto da meta e a variação de cada mês."
    ),
    category="economia",
    sources=[_src(433, "IPCA mensal"), _src(13522, "IPCA acumulado em 12 meses")],
    frequency="Mensal",
    tags=["inflação", "preços", "meta de inflação", "IBGE"],
    methodology=[
        "IPCA mensal (série 433) e acumulado em 12 meses (série 13522) do SGS, em %.",
        "Metas do CMN: centro de 4,5% até 2018, reduzido gradualmente até 3% em 2024; desde "
        "2025 a meta de 3% é contínua. Tolerância de 1,5 p.p. desde 2017 (antes, 2 p.p.).",
    ],
    columns=[
        Column(name="mes", description="Mês de referência (AAAA-MM-01)"),
        Column(name="ipca_mensal", description="Variação do IPCA no mês, %"),
        Column(name="ipca_12m", description="IPCA acumulado em 12 meses, %"),
        Column(name="meta_centro", description="Centro da meta de inflação do ano, %"),
        Column(name="meta_teto", description="Teto da meta de inflação do ano, %"),
    ],
)
def ipca() -> Build:
    start = date(max(2006, date.today().year - 20), 1, 1)
    monthly = _monthly(bcb.sgs(433, start))
    a12 = _monthly(bcb.sgs(13522, start))
    check_series(monthly, "IPCA mensal", min_points=60, lo=-5, hi=10, max_age_days=75)
    check_series(a12, "IPCA 12m", min_points=60, lo=-5, hi=40, max_age_days=75)

    df = pd.concat({"ipca_mensal": monthly, "ipca_12m": a12}, axis=1).dropna()
    df["meta_centro"] = [_target(ts.year)[0] for ts in df.index]
    df["meta_teto"] = [sum(_target(ts.year)) for ts in df.index]
    df["meta_piso"] = df["meta_centro"] - (df["meta_teto"] - df["meta_centro"])

    last = df.index[-1]
    now12, prev12 = float(df["ipca_12m"].iloc[-1]), float(df["ipca_12m"].iloc[-2])
    teto, piso, centro = (float(df[c].iloc[-1]) for c in ("meta_teto", "meta_piso", "meta_centro"))
    if now12 > teto:
        status, status_label, rel = "serious", "Acima do teto da meta", "acima do teto"
    elif now12 < piso:
        status, status_label, rel = "warning", "Abaixo do piso da meta", "abaixo do piso"
    else:
        status, status_label, rel = "good", "Dentro do intervalo da meta", "dentro do intervalo"
    last12 = df.iloc[-12:]
    above = int((last12["ipca_12m"] > last12["meta_teto"]).sum())

    kpis = [
        Kpi(
            label="IPCA em 12 meses",
            value=now12,
            format=pct(2),
            delta=Delta(value=now12 - prev12, format=pp(2), period="vs. mês anterior", good="down"),
            spark=[round(v, 2) for v in last12["ipca_12m"].tolist()],
            as_of=month_label(last),
            status=status,
            status_label=status_label,
        ),
        Kpi(
            label="IPCA do mês",
            value=float(df["ipca_mensal"].iloc[-1]),
            format=pct(2),
            spark=[round(v, 2) for v in last12["ipca_mensal"].tolist()],
            as_of=month_label(last),
        ),
        Kpi(label="Meses acima do teto (últimos 12)", value=above, format=num(0)),
    ]

    same_month_ly = df["ipca_mensal"].get(last - pd.DateOffset(years=1))
    insights = [
        f"Em {month_label(last, long=True)}, o IPCA acumulado em 12 meses foi de "
        f"{fmt_num(now12, 2)}%, {rel} da meta (centro de {fmt_num(centro, 2)}% e teto de "
        f"{fmt_num(teto, 2)}%).",
    ]
    if same_month_ly is not None:
        cmp = "acima" if df["ipca_mensal"].iloc[-1] > same_month_ly else "abaixo"
        insights.append(
            f"A inflação do mês foi de {fmt_num(float(df['ipca_mensal'].iloc[-1]), 2)}%, {cmp} "
            f"do mesmo mês do ano anterior ({fmt_num(float(same_month_ly), 2)}%)."
        )
    insights.append(f"Nos últimos 12 meses, o IPCA ficou acima do teto da meta em {above} deles.")

    recent = df.iloc[-24:]
    charts = [
        LineChart(
            id="acumulado-12m",
            title="IPCA acumulado em 12 meses vs. meta",
            subtitle="%",
            format=pct(2),
            x_kind="month",
            series=[
                Series(
                    key="ipca_12m",
                    name="IPCA 12 meses",
                    points=to_points(df["ipca_12m"], decimals=2),
                    color=1,
                ),
                Series(
                    key="meta_teto",
                    name="Teto da meta",
                    points=to_points(df["meta_teto"], decimals=2),
                    style="dashed",
                    color=2,
                ),
                Series(
                    key="meta_centro",
                    name="Centro da meta",
                    points=to_points(df["meta_centro"], decimals=2),
                    style="dashed",
                    color=3,
                ),
            ],
            step=False,
        ),
        ColumnChart(
            id="mensal",
            title="Variação mensal — últimos 24 meses",
            subtitle="% no mês",
            format=pct(2),
            diverging=True,
            items=[
                BarItem(label=month_label(ts), value=round(float(v), 2))
                for ts, v in recent["ipca_mensal"].items()
            ],
        ),
    ]
    table = df.drop(columns="meta_piso").round(4).reset_index(names="mes")
    table["mes"] = table["mes"].dt.strftime("%Y-%m-%d")
    return Build(
        charts=charts,
        table=table,
        kpis=kpis,
        insights=insights,
        coverage=f"{df.index[0].year}–{last.year}",
        data_until=month_label(last, long=True),
    )


# --------------------------------------------------------------------------- Dólar


@dataset(
    slug="dolar",
    title="Dólar comercial",
    summary="Cotação diária do dólar em reais e sua variação recente.",
    description=(
        "Taxa de câmbio livre do dólar americano (venda), divulgada diariamente pelo Banco "
        "Central. O câmbio afeta preços de importados, combustíveis e a inflação."
    ),
    category="economia",
    sources=[_src(1, "Dólar americano, venda")],
    frequency="Diária (dias úteis)",
    tags=["câmbio", "dólar", "moeda"],
    methodology=[
        "Série 1 do SGS: taxa de câmbio livre, dólar americano (venda), R$/US$.",
        "Valores nominais, sem correção pela inflação. O histórico longo é amostrado com o "
        "algoritmo LTTB para o gráfico (picos e vales preservados); o CSV traz todos os dias.",
    ],
    columns=[
        Column(name="data", description="Data (AAAA-MM-DD)"),
        Column(name="dolar_venda", description="Cotação de venda, R$ por US$"),
    ],
)
def dolar() -> Build:
    s = bcb.sgs(1, date(date.today().year - 20, 1, 1))
    check_series(s, "Dólar", min_points=1000, lo=0.5, hi=30, max_age_days=10)
    last_date, now = s.index[-1], float(s.iloc[-1])

    def change(days: int) -> float | None:
        ref = value_at_or_before(s, last_date - pd.Timedelta(days=days))
        return (now / ref - 1) * 100 if ref else None

    ch30, ch365 = change(30), change(365)
    year = s[s.index > last_date - pd.Timedelta(days=365)]
    kpis = [
        Kpi(
            label="Dólar (venda)",
            value=now,
            format=brl(4),
            delta=Delta(value=ch30 or 0, format=pct(2), period="em 30 dias")
            if ch30 is not None
            else None,
            spark=[round(v, 4) for v in s.resample("MS").mean().iloc[-12:].tolist()],
            as_of=br_date(last_date),
        ),
        Kpi(label="Variação em 12 meses", value=ch365 or 0, format=pct(2)),
        Kpi(
            label="Máxima em 12 meses",
            value=float(year.max()),
            format=brl(4),
            as_of=br_date(year.idxmax()),
        ),
    ]
    insights = [f"O dólar fechou a R$ {fmt_num(now, 4)} em {br_date(last_date)}."]
    if ch365 is not None:
        insights.append(f"Em 12 meses, a variação foi de {signed(ch365, 2)}%.")
    insights.append(
        f"Nos últimos 12 meses, a cotação oscilou entre R$ {fmt_num(float(year.min()), 4)} "
        f"({br_date(year.idxmin())}) e R$ {fmt_num(float(year.max()), 4)} ({br_date(year.idxmax())})."
    )
    charts = [
        LineChart(
            id="12-meses",
            title="Últimos 12 meses",
            subtitle="R$ por US$, cotação diária",
            format=brl(2),
            series=[Series(key="dolar", name="Dólar (venda)", points=to_points(year, decimals=4))],
        ),
        LineChart(
            id="historico",
            title=f"Histórico desde {s.index[0].year}",
            subtitle="R$ por US$, valores nominais",
            format=brl(2),
            series=[
                Series(
                    key="dolar",
                    name="Dólar (venda)",
                    points=to_points(s, max_points=420, decimals=4),
                )
            ],
            y_zero=True,
        ),
    ]
    table = s.round(4).rename("dolar_venda").rename_axis("data").reset_index()
    table["data"] = table["data"].dt.strftime("%Y-%m-%d")
    return Build(
        charts=charts,
        table=table,
        kpis=kpis,
        insights=insights,
        coverage=f"{s.index[0].year}–{last_date.year}",
        data_until=br_date(last_date),
    )


# --------------------------------------------------------------------------- Desemprego


@dataset(
    slug="desemprego",
    title="Taxa de desemprego",
    summary="Desocupação no Brasil pela PNAD Contínua, em trimestres móveis.",
    description=(
        "Percentual da força de trabalho que está sem emprego e procurando trabalho, medido "
        "pela PNAD Contínua do IBGE em trimestres móveis e publicado no SGS do Banco Central."
    ),
    category="economia",
    sources=[_src(24369, "Taxa de desocupação — PNAD Contínua")],
    frequency="Mensal (trimestre móvel)",
    tags=["emprego", "mercado de trabalho", "PNAD", "IBGE"],
    methodology=[
        "Série 24369 do SGS: taxa de desocupação da PNAD Contínua, em %. Cada mês representa "
        "o trimestre móvel encerrado nele.",
        "A comparação em 12 meses usa o mesmo trimestre móvel do ano anterior, o que neutraliza "
        "a sazonalidade típica do mercado de trabalho.",
    ],
    columns=[
        Column(name="mes", description="Mês final do trimestre móvel (AAAA-MM-01)"),
        Column(name="desocupacao", description="Taxa de desocupação, %"),
        Column(name="variacao_12m", description="Diferença para 12 meses antes, p.p."),
    ],
)
def desemprego() -> Build:
    s = _monthly(bcb.sgs(24369, date(2012, 1, 1)))
    check_series(s, "Desocupação", min_points=60, lo=0, hi=40, max_age_days=120)
    yoy = (s - s.shift(12)).dropna()
    last, now = s.index[-1], float(s.iloc[-1])
    low_ts, low = s.idxmin(), float(s.min())
    kpis = [
        Kpi(
            label="Taxa de desocupação",
            value=now,
            format=pct(1),
            delta=Delta(value=float(yoy.iloc[-1]), format=pp(1), period="em 12 meses", good="down"),
            spark=[round(v, 2) for v in s.iloc[-12:].tolist()],
            as_of=f"trimestre até {month_label(last)}",
        ),
        Kpi(label="Mínima da série", value=low, format=pct(1), as_of=month_label(low_ts)),
        Kpi(
            label="Máxima da série",
            value=float(s.max()),
            format=pct(1),
            as_of=month_label(s.idxmax()),
        ),
    ]
    insights = [
        f"A taxa de desocupação foi de {fmt_num(now, 1)}% no trimestre encerrado em "
        f"{month_label(last, long=True)}, {signed(float(yoy.iloc[-1]), 1)} p.p. em 12 meses."
    ]
    if now <= low:
        insights.append(f"É a menor taxa da série histórica, iniciada em {s.index[0].year}.")
    else:
        insights.append(
            f"A menor taxa da série foi {fmt_num(low, 1)}%, em {month_label(low_ts, long=True)}."
        )
    recent = yoy.iloc[-24:]
    charts = [
        LineChart(
            id="historico",
            title=f"Taxa de desocupação desde {s.index[0].year}",
            subtitle="% da força de trabalho, trimestre móvel",
            format=pct(1),
            x_kind="month",
            series=[Series(key="desocupacao", name="Desocupação", points=to_points(s, decimals=2))],
            y_zero=True,
        ),
        ColumnChart(
            id="variacao-12m",
            title="Variação em 12 meses — últimos 24 meses",
            subtitle="pontos percentuais",
            format=pp(1),
            diverging=True,
            items=[
                BarItem(label=month_label(ts), value=round(float(v), 2)) for ts, v in recent.items()
            ],
        ),
    ]
    table = pd.DataFrame({"desocupacao": s, "variacao_12m": s - s.shift(12)}).round(3)
    table = table.reset_index(names="mes")
    table["mes"] = table["mes"].dt.strftime("%Y-%m-%d")
    return Build(
        charts=charts,
        table=table,
        kpis=kpis,
        insights=insights,
        coverage=f"{s.index[0].year}–{last.year}",
        data_until=month_label(last, long=True),
    )
