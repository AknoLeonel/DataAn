"""Demografia: população estimada por UF (IBGE)."""

from __future__ import annotations

from dataan.analysis.quality import require
from dataan.analysis.series import fmt_num, signed
from dataan.models import BarChart, BarItem, Column, Kpi, Source
from dataan.registry import Build, dataset, num, pct
from dataan.sources import ibge

AGREGADO, VARIAVEL = 6579, 9324  # Estimativas da população residente


@dataset(
    slug="populacao-uf",
    title="População dos estados",
    summary="População estimada de cada unidade da federação e o crescimento recente.",
    description=(
        "Estimativas oficiais da população residente publicadas anualmente pelo IBGE, usadas "
        "inclusive na distribuição do Fundo de Participação de Estados e Municípios."
    ),
    category="demografia",
    sources=[
        Source(
            name=f"IBGE — Estimativas da população (SIDRA, tabela {AGREGADO})",
            url=ibge.SIDRA.format(agregado=AGREGADO),
            license="Dados abertos do IBGE",
        )
    ],
    frequency="Anual",
    tags=["população", "IBGE", "estados", "censo"],
    methodology=[
        f"Tabela {AGREGADO} do SIDRA, variável {VARIAVEL} (população residente estimada), "
        "nível Unidade da Federação.",
        "Crescimento: variação percentual entre as duas estimativas mais recentes publicadas.",
    ],
    columns=[
        Column(name="uf", description="Sigla da unidade da federação"),
        Column(name="estado", description="Nome"),
        Column(name="ano", description="Ano de referência"),
        Column(name="populacao", description="População residente estimada"),
    ],
)
def populacao_uf() -> Build:
    df = ibge.agregado(AGREGADO, VARIAVEL, periodos="-2")
    df["uf"] = df["localidade_id"].map(ibge.UF_SIGLAS)
    df = df.dropna(subset=["uf"])
    periods = sorted(df["periodo"].unique())
    latest = periods[-1]
    cur = df[df["periodo"] == latest].set_index("uf")
    require(len(cur) == 27, f"População: esperadas 27 UFs, vieram {len(cur)}")
    total = float(cur["valor"].sum())
    ranking = cur["valor"].sort_values(ascending=False)
    top_uf = ranking.index[0]

    growth = None
    if len(periods) > 1:
        prev = df[df["periodo"] == periods[-2]].set_index("uf")["valor"]
        growth = ((cur["valor"] / prev - 1) * 100).dropna().sort_values(ascending=False)
        total_prev = float(prev.sum())

    names = cur["localidade"].to_dict()
    kpis = [
        Kpi(label=f"População do Brasil ({latest})", value=total, format=num(0, compact=True)),
        Kpi(
            label="Estado mais populoso",
            value=float(ranking.iloc[0]) / total * 100,
            format=pct(1, "da população"),
            as_of=names[top_uf],
        ),
    ]
    insights = [
        f"Segundo o IBGE, o Brasil tinha {fmt_num(total / 1e6, 1)} milhões de habitantes em {latest}.",
        f"{names[top_uf]} concentra {fmt_num(float(ranking.iloc[0]) / total * 100, 1)}% da população; "
        f"os cinco estados mais populosos somam {fmt_num(float(ranking.iloc[:5].sum()) / total * 100, 1)}%.",
    ]
    charts = [
        BarChart(
            id="ranking",
            title=f"População por unidade da federação — {latest}",
            subtitle="habitantes",
            format=num(0, compact=True),
            items=[BarItem(label=names[uf], value=float(v)) for uf, v in ranking.items()],
        )
    ]
    if growth is not None:
        g_total = (total / total_prev - 1) * 100
        kpis.append(Kpi(label=f"Crescimento {periods[-2]}–{latest}", value=g_total, format=pct(2)))
        insights.append(
            f"Entre {periods[-2]} e {latest}, {names[growth.index[0]]} foi o que mais cresceu "
            f"({signed(float(growth.iloc[0]), 2)}%) e {names[growth.index[-1]]} o que menos cresceu "
            f"({signed(float(growth.iloc[-1]), 2)}%)."
        )
        charts.append(
            BarChart(
                id="crescimento",
                title=f"Crescimento da população, {periods[-2]}–{latest}",
                subtitle="% entre as duas estimativas mais recentes",
                format=pct(2),
                items=[
                    BarItem(label=names[uf], value=round(float(v), 3)) for uf, v in growth.items()
                ],
            )
        )

    table = df.rename(columns={"localidade": "estado", "periodo": "ano", "valor": "populacao"})
    table = table[["uf", "estado", "ano", "populacao"]].sort_values(
        ["ano", "populacao"], ascending=[True, False]
    )
    table["populacao"] = table["populacao"].astype("int64")
    return Build(
        charts=charts,
        table=table,
        kpis=kpis,
        insights=insights,
        coverage=" e ".join(periods),
        data_until=latest,
    )
