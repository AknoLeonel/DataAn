"""Saúde: dengue nas capitais (InfoDengue), com nowcasting e previsão de 4 semanas."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from dataan.analysis.forecast import holt_forecast
from dataan.analysis.quality import check_series
from dataan.analysis.series import br_date, fmt_num, signed, to_points
from dataan.models import (
    Badge,
    BarChart,
    BarItem,
    Column,
    Delta,
    GridChart,
    Kpi,
    LineChart,
    ModelInfo,
    RefLine,
    Series,
    Source,
)
from dataan.registry import Build, dataset, num, pct
from dataan.slug import slugify
from dataan.sources import infodengue

CAPITALS = [
    ("Rio de Janeiro", "RJ", 3304557),
    ("São Paulo", "SP", 3550308),
    ("Belo Horizonte", "MG", 3106200),
    ("Brasília", "DF", 5300108),
    ("Goiânia", "GO", 5208707),
    ("Curitiba", "PR", 4106902),
]
LEVELS = {
    1: ("good", "verde", "baixa transmissão"),
    2: ("warning", "amarelo", "condições favoráveis à transmissão"),
    3: ("serious", "laranja", "transmissão sustentada"),
    4: ("critical", "vermelho", "atividade acima do esperado"),
}
UF_OF = {city: uf for city, uf, _ in CAPITALS}
HORIZON = 4
HISTORY_WEEKS = 78


@dataset(
    slug="dengue-capitais",
    title="Dengue nas capitais",
    summary="Casos semanais estimados, nível de alerta e previsão para as próximas 4 semanas.",
    description=(
        "Acompanhamento semanal da dengue em seis capitais a partir do InfoDengue, sistema de "
        "alerta da Fiocruz e da FGV. Como as notificações chegam com atraso, usamos a estimativa "
        "corrigida (nowcasting) e projetamos as próximas 4 semanas com um modelo validado contra "
        "uma previsão ingênua."
    ),
    category="saude",
    sources=[
        Source(
            name="InfoDengue (Fiocruz/FGV) — API alertcity",
            url=infodengue.SITE,
            license="Dados abertos; citar InfoDengue",
        )
    ],
    frequency="Semanal (semana epidemiológica)",
    tags=["dengue", "arboviroses", "vigilância", "previsão", "nowcasting"],
    methodology=[
        "Casos estimados: estimativa do InfoDengue que corrige o atraso de notificação das "
        "últimas semanas. As semanas mais recentes podem ser revisadas.",
        "Previsão: suavização exponencial de Holt com tendência amortecida, ajustada no "
        "logaritmo dos casos. Parâmetros escolhidos por mínimo erro de um passo.",
        "Validação: origem móvel nas últimas 26 semanas (treina só com o passado de cada "
        "origem), comparando o erro absoluto médio com a previsão ingênua (repetir a última "
        "semana). O intervalo de 80% vem dos erros observados nesse backtest.",
        "Incidência: casos estimados nas últimas 4 semanas por 100 mil habitantes.",
    ],
    columns=[
        Column(name="semana_inicio", description="Início da semana epidemiológica (AAAA-MM-DD)"),
        Column(name="cidade", description="Capital"),
        Column(name="uf", description="Unidade da federação"),
        Column(name="geocodigo", description="Código IBGE do município"),
        Column(name="tipo", description="'observado' ou 'previsao'"),
        Column(name="casos_notificados", description="Casos notificados até a coleta"),
        Column(name="casos_estimados", description="Casos estimados (nowcast) ou previstos"),
        Column(
            name="limite_inferior",
            description="Limite inferior (IC do nowcast ou intervalo de 80% da previsão)",
        ),
        Column(name="limite_superior", description="Limite superior"),
        Column(name="nivel_alerta", description="1 verde, 2 amarelo, 3 laranja, 4 vermelho"),
        Column(name="rt", description="Número reprodutivo estimado"),
    ],
)
def dengue_capitais() -> Build:
    year = date.today().year
    charts: list[LineChart] = []
    rows: list[pd.DataFrame] = []
    incid: list[BarItem] = []
    weekly_totals: list[pd.Series] = []
    forecasts_total = 0.0
    mae_sum = mae_naive_sum = 0.0
    alerts: list[tuple[str, int]] = []
    growth: list[tuple[str, float]] = []
    last_week: pd.Timestamp | None = None

    for city, uf, geocode in CAPITALS:
        df = infodengue.alertcity(geocode, "dengue", year - 4, year)
        s = df.set_index("date")["casos_est"].astype(float)
        check_series(s, f"Dengue {city}", min_points=80, lo=0, max_age_days=28)
        fc = holt_forecast(s, horizon=HORIZON)
        mae_sum += fc.mae
        mae_naive_sum += fc.mae_naive
        forecasts_total += float(fc.mean.sum())
        weekly_totals.append(s)
        last_week = s.index[-1] if last_week is None else max(last_week, s.index[-1])

        hist = s.iloc[-HISTORY_WEEKS:]
        anchor = (hist.index[-1].strftime("%Y-%m-%d"), round(float(hist.iloc[-1]), 1))
        forecast_points = [anchor] + [
            (ts.strftime("%Y-%m-%d"), round(float(v), 1))
            for ts, v in zip(fc.index, fc.mean, strict=True)
        ]
        band = [(anchor[0], anchor[1], anchor[1])] + [
            (ts.strftime("%Y-%m-%d"), round(float(lo), 1), round(float(hi), 1))
            for ts, lo, hi in zip(fc.index, fc.lower, fc.upper, strict=True)
        ]
        level = int(df["nivel"].dropna().iloc[-1]) if df["nivel"].notna().any() else 1
        alerts.append((city, level))
        charts.append(
            LineChart(
                id=slugify(city),
                title=f"{city} ({uf})",
                format=num(0, compact=True),
                x_kind="week",
                y_zero=True,
                series=[
                    Series(
                        key="casos_est",
                        name="Casos estimados",
                        points=to_points(hist, decimals=1),
                        color=1,
                    ),
                    Series(
                        key="previsao",
                        name="Previsão (80%)",
                        points=forecast_points,
                        band=band,
                        style="dashed",
                        color=2,
                    ),
                ],
                marker=(anchor[0], "hoje"),
                badge=Badge(status=LEVELS[level][0], label=f"Alerta {LEVELS[level][1]}"),
            )
        )

        last4, prev4 = float(s.iloc[-4:].sum()), float(s.iloc[-8:-4].sum())
        if prev4 > 0:
            growth.append((city, (last4 / prev4 - 1) * 100))
        pop = float(df["pop"].dropna().iloc[-1]) if df["pop"].notna().any() else np.nan
        if np.isfinite(pop) and pop > 0:
            incid.append(BarItem(label=city, value=round(last4 / pop * 1e5, 1)))

        out = pd.DataFrame(
            {
                "semana_inicio": df["date"].dt.strftime("%Y-%m-%d"),
                "cidade": city,
                "uf": uf,
                "geocodigo": geocode,
                "tipo": "observado",
                "casos_notificados": df["casos"],
                "casos_estimados": df["casos_est"].round(1),
                "limite_inferior": df["casos_est_min"].round(1),
                "limite_superior": df["casos_est_max"].round(1),
                "nivel_alerta": df["nivel"],
                "rt": df["Rt"].round(3),
            }
        )
        fut = pd.DataFrame(
            {
                "semana_inicio": fc.index.strftime("%Y-%m-%d"),
                "cidade": city,
                "uf": uf,
                "geocodigo": geocode,
                "tipo": "previsao",
                "casos_estimados": np.round(fc.mean, 1),
                "limite_inferior": np.round(fc.lower, 1),
                "limite_superior": np.round(fc.upper, 1),
            }
        )
        rows.extend([out, fut])

    total = pd.concat(weekly_totals, axis=1).fillna(0).sum(axis=1).sort_index()
    last4, prev4 = float(total.iloc[-4:].sum()), float(total.iloc[-8:-4].sum())
    change4 = (last4 / prev4 - 1) * 100 if prev4 > 0 else 0.0
    high_alert = [(c, lvl) for c, lvl in alerts if lvl >= 3]
    skill = 1 - mae_sum / mae_naive_sum if mae_naive_sum > 0 else 0.0
    worst_level = max(lvl for _, lvl in alerts)

    kpis = [
        Kpi(
            label="Casos estimados (4 semanas)",
            value=last4,
            format=num(0, compact=True),
            delta=Delta(
                value=change4, format=pct(1), period="vs. 4 semanas anteriores", good="down"
            ),
            spark=[round(v, 1) for v in total.iloc[-12:].tolist()],
            as_of=f"semana de {br_date(total.index[-1])}",
        ),
        Kpi(
            label="Capitais em alerta laranja ou vermelho",
            value=len(high_alert),
            format=num(0, unit=f"de {len(CAPITALS)}"),
            status=LEVELS[worst_level][0],
            status_label=f"Maior nível: {LEVELS[worst_level][1]}",
        ),
        Kpi(
            label="Previsão (próximas 4 semanas)",
            value=forecasts_total,
            format=num(0, compact=True),
        ),
        Kpi(label="Ganho do modelo sobre o ingênuo", value=skill * 100, format=pct(0)),
    ]

    insights = [
        f"Somando as {len(CAPITALS)} capitais, foram estimados {fmt_num(last4, 0)} casos nas "
        f"últimas 4 semanas, {signed(change4, 1)}% em relação às 4 semanas anteriores."
    ]
    for city, lvl in sorted(high_alert, key=lambda x: -x[1]):
        _, color, meaning = LEVELS[lvl]
        insights.append(f"{city} está em alerta {color} ({meaning}).")
    if growth:
        city, g = max(growth, key=lambda x: x[1])
        if g > 0:
            insights.append(f"Maior aceleração recente: {city}, com {signed(g, 0)}% em 4 semanas.")
    if skill > 0:
        insights.append(
            f"No backtest das últimas 26 semanas, o modelo errou em média {fmt_num(skill * 100, 0)}% "
            "menos do que a previsão ingênua."
        )
    else:
        insights.append(
            "No backtest recente, o modelo não superou a previsão ingênua: trate a projeção "
            "com cautela."
        )

    incid.sort(key=lambda b: -b.value)
    if incid:
        incid[0].highlight = True
    charts_out = [
        GridChart(
            id="casos-semanais",
            title="Casos semanais estimados e previsão",
            subtitle="Últimos 18 meses e próximas 4 semanas; faixa = intervalo de 80%",
            charts=charts,
        ),
        BarChart(
            id="incidencia",
            title="Incidência nas últimas 4 semanas",
            subtitle="Casos estimados por 100 mil habitantes",
            format=num(1),
            items=incid or [BarItem(label="—", value=0)],
            highlight_label="Maior incidência",
        ),
    ]
    model = ModelInfo(
        name="Holt com tendência amortecida (escala log)",
        target="Casos estimados por semana epidemiológica, por capital",
        horizon="1 a 4 semanas",
        baseline="Ingênuo: repetir a última semana observada",
        mae=round(mae_sum / len(CAPITALS), 1),
        mae_baseline=round(mae_naive_sum / len(CAPITALS), 1),
        skill=round(skill, 3),
        notes="Erro absoluto médio por capital e semana prevista, origem móvel nas últimas 26 semanas.",
    )
    assert last_week is not None
    return Build(
        charts=charts_out,
        table=pd.concat(rows, ignore_index=True),
        kpis=kpis,
        insights=insights,
        coverage=f"{year - 4}–{year}",
        data_until=f"semana de {br_date(last_week)}",
        model=model,
    )


# --------------------------------------------------------------------------- Estudo de caso

CRITERIO_GANHO = 0.15  # ganho mínimo sobre o ingênuo
CRITERIO_CAPITAIS = 4  # em pelo menos 4 das 6 capitais


@dataset(
    slug="estudo-dengue-clima",
    title="Estudo: o clima ajuda a prever a dengue?",
    summary="Cinco modelos comparados nas seis capitais, prevendo só com o passado: o clima melhora a previsão de 4 semanas?",
    description=(
        "Estudo de caso reproduzível. A pergunta: temperatura e umidade das semanas anteriores "
        "melhoram a previsão de casos de dengue para as próximas 4 semanas, além do que a "
        "própria série já informa? Comparamos cinco modelos com validação de origem móvel nas "
        "últimas 52 semanas de seis capitais. O resultado é recalculado a cada atualização, "
        "inclusive quando a resposta for não."
    ),
    category="saude",
    sources=[
        Source(
            name="InfoDengue (Fiocruz/FGV) — casos estimados e clima semanal",
            url=infodengue.SITE,
            license="Dados abertos; citar InfoDengue",
        )
    ],
    frequency="Semanal (recalculado a cada atualização)",
    tags=["estudo de caso", "dengue", "clima", "previsão", "validação", "ciência de dados"],
    methodology=[
        "Pergunta e hipótese: o clima recente (temperatura e umidade médias das últimas 4 e "
        "das 4 semanas anteriores) carrega informação sobre a dengue das próximas 4 semanas "
        "que a série de casos ainda não tem.",
        "Alvo: casos estimados (nowcast do InfoDengue) por semana; modelos ajustados no "
        "logaritmo dos casos e avaliados em casos.",
        "Validação com origem móvel: em cada uma das últimas 52 semanas, cada modelo é "
        "ajustado só com o passado e prevê 1 a 4 semanas à frente. Métrica: erro absoluto "
        "médio (MAE), comparado ao ingênuo (repetir a última semana).",
        "Modelos: ingênuo; sazonal ingênuo (mesma semana do ano anterior); Holt amortecido; "
        "regressão ridge com 4 defasagens, tendência recente e sazonalidade (um modelo por "
        "horizonte); a mesma regressão com clima. Comparar as duas regressões isola o efeito "
        "do clima.",
        f"Critério definido antes de ver os dados: um modelo só substitui o atual se ganhar "
        f"pelo menos {CRITERIO_GANHO:.0%} do ingênuo em {CRITERIO_CAPITAIS} das 6 capitais.",
        "Limitações: o clima vem das estações usadas pelo InfoDengue (pode ter falhas, "
        "preenchidas com o valor anterior); casos recentes são estimativas que mudam; 52 "
        "semanas cobrem uma única temporada por capital.",
    ],
    columns=[
        Column(name="cidade", description="Capital"),
        Column(name="modelo", description="Modelo avaliado"),
        Column(name="mae", description="Erro absoluto médio em casos (h = 1 a 4 semanas)"),
        Column(name="ganho_vs_ingenuo", description="1 − MAE / MAE do ingênuo"),
        Column(
            name="clima_disponivel", description="Se havia clima suficiente para o modelo com clima"
        ),
    ],
)
def estudo_dengue_clima() -> Build:
    from dataan.analysis.experiment import (
        HOLT,
        MODELS,
        NAIVE,
        RIDGE,
        RIDGE_CLIMA,
        backtest,
    )

    year = date.today().year
    rows, results = [], {}
    for city, _uf, geocode in CAPITALS:
        df = infodengue.alertcity(geocode, "dengue", year - 4, year)
        bt = backtest(df, horizon=HORIZON, origins=52)
        results[city] = bt
        for m in MODELS:
            if m in bt.mae:
                rows.append([city, m, round(bt.mae[m], 2), round(bt.skill[m], 4), bt.clima_ok])
    table = pd.DataFrame(
        rows, columns=["cidade", "modelo", "mae", "ganho_vs_ingenuo", "clima_disponivel"]
    )

    # Ganho agregado: 1 − soma dos MAE / soma dos MAE do ingênuo (capitais pesam pelo volume).
    def pooled(model: str) -> float | None:
        cities = [c for c, b in results.items() if model in b.mae]
        if not cities:
            return None
        return 1 - sum(results[c].mae[model] for c in cities) / sum(
            results[c].mae[NAIVE] for c in cities
        )

    pooled_skill = {m: pooled(m) for m in MODELS if m != NAIVE}
    ranked = sorted(((m, s) for m, s in pooled_skill.items() if s is not None), key=lambda x: -x[1])
    best_model, best_skill = ranked[0]

    with_clima = [c for c, b in results.items() if RIDGE_CLIMA in b.mae]
    clima_gain = {c: results[c].skill[RIDGE_CLIMA] - results[c].skill[RIDGE] for c in with_clima}
    helped = [c for c, g in clima_gain.items() if g > 0]
    passing = {
        m: [c for c, b in results.items() if b.skill.get(m, -1) >= CRITERIO_GANHO] for m in MODELS
    }
    winners = [m for m in MODELS if m != NAIVE and len(passing[m]) >= CRITERIO_CAPITAIS]

    kpis = [
        Kpi(
            label="Ganho do melhor modelo sobre o ingênuo",
            value=best_skill * 100,
            format=pct(0),
            as_of=best_model,
            status="good" if best_skill >= CRITERIO_GANHO else "warning",
            status_label="Atinge o critério de 15%"
            if best_skill >= CRITERIO_GANHO
            else "Abaixo do critério de 15%",
        ),
        Kpi(
            label="Capitais em que o clima melhorou a previsão",
            value=len(helped),
            format=num(0, unit=f"de {len(with_clima)}"),
            dots=[c in helped for c in with_clima],
            dot_labels=[UF_OF[c] for c in with_clima],
            dot_legend=("clima ajudou", "não ajudou"),
        ),
        Kpi(
            label="Efeito médio do clima no ganho",
            value=float(np.mean(list(clima_gain.values())) * 100) if clima_gain else 0.0,
            format=num(1, unit="p.p."),
            as_of="regressão com clima − sem clima",
        ),
    ]

    verdict_clima = (
        f"Sim, em parte: o clima melhorou a previsão em {len(helped)} das {len(with_clima)} capitais"
        if len(helped) > len(with_clima) / 2
        else f"Não de forma consistente: o clima melhorou a previsão em só {len(helped)} das {len(with_clima)} capitais"
    )
    insights = [
        f"{verdict_clima}; o efeito médio foi de {signed(float(np.mean(list(clima_gain.values())) * 100), 1)} p.p. de ganho."
        if clima_gain
        else "Não havia dados de clima suficientes para testar a hipótese nesta atualização.",
        f"O melhor modelo no agregado foi “{best_model}”, com {signed(best_skill * 100, 0)}% de ganho sobre o ingênuo.",
        (
            f"Critério atingido por: {', '.join(winners)}."
            if winners
            else f"Nenhum modelo ganhou {CRITERIO_GANHO:.0%} do ingênuo em {CRITERIO_CAPITAIS} capitais: o modelo publicado segue o Holt, e a projeção deve ser lida com cautela."
        ),
        f"Holt amortecido (o modelo da página de dengue) teve {signed((pooled_skill[HOLT] or 0) * 100, 0)}% de ganho agregado.",
    ]

    order = [m for m in MODELS if m != NAIVE and pooled_skill.get(m) is not None]
    bars = [
        BarItem(label=m, value=round(pooled_skill[m] * 100, 1), highlight=m == best_model)
        for m in order
    ]
    gain_bars = [
        BarItem(label=c, value=round(g * 100, 1), highlight=g > 0)
        for c, g in sorted(clima_gain.items(), key=lambda x: -x[1])
    ]

    # Exemplo: capital com mais casos, previsões de 4 semanas do backtest vs. o que aconteceu.
    focus_city = max(results, key=lambda c: float(results[c].actual.iloc[-60:].sum()))
    bt = results[focus_city]
    window = bt.preds[NAIVE].index
    real = bt.actual.reindex(window)
    series = [
        Series(
            key="real", name="Casos estimados (real)", points=to_points(real, decimals=1), color=1
        )
    ]
    for key, m, color in (("melhor", best_model, 2), ("ingenuo", NAIVE, 3)):
        if m in bt.preds and not (key == "ingenuo" and best_model == NAIVE):
            series.append(
                Series(
                    key=key,
                    name=f"Previsão 4 sem. — {m}",
                    points=to_points(bt.preds[m], decimals=1),
                    style="dashed",
                    color=color,
                )
            )

    charts = [
        BarChart(
            id="ganho-por-modelo",
            title="Ganho de cada modelo sobre o ingênuo",
            subtitle="% de redução do erro médio, seis capitais somadas; linha = critério de 15%",
            format=num(1, "%"),
            items=bars,
            reference=[RefLine(value=CRITERIO_GANHO * 100, label="critério")],
            highlight_label="Melhor modelo",
        ),
        BarChart(
            id="efeito-do-clima",
            title="Quanto o clima mudou o ganho, por capital",
            subtitle="p.p.: regressão com clima menos regressão sem clima",
            format=num(1, "p.p."),
            items=gain_bars or [BarItem(label="—", value=0)],
            highlight_label="Clima ajudou",
        ),
        LineChart(
            id="previsoes-vs-real",
            title=f"{focus_city}: previsão de 4 semanas vs. o que aconteceu",
            subtitle="Cada ponto tracejado foi previsto 4 semanas antes, só com o passado",
            format=num(0, compact=True),
            x_kind="week",
            y_zero=True,
            series=series,
        ),
    ]
    model = ModelInfo(
        name=best_model,
        target="Casos estimados por semana, por capital",
        horizon="1 a 4 semanas",
        baseline="Ingênuo: repetir a última semana observada",
        mae=round(
            float(
                np.mean(
                    [results[c].mae[best_model] for c in results if best_model in results[c].mae]
                )
            ),
            1,
        ),
        mae_baseline=round(float(np.mean([results[c].mae[NAIVE] for c in results])), 1),
        skill=round(best_skill, 3),
        notes="Erro absoluto médio por capital e semana prevista, origem móvel nas últimas 52 semanas.",
    )
    last = max(b.actual.index.max() for b in results.values())
    return Build(
        charts=charts,
        table=table,
        kpis=kpis,
        insights=insights,
        coverage=f"{year - 4}–{year}",
        data_until=f"semana de {br_date(last)}",
        model=model,
    )
