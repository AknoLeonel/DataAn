"""Os conjuntos de dados de verdade, rodando sobre APIs simuladas (tests/fakes.py)."""

from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import fakes
import pandas as pd
import pytest

import dataan.datasets  # noqa: F401  (registra os datasets)
from dataan import http, runner
from dataan.datasets.economia import _target
from dataan.registry import REGISTRY
from dataan.sources import bcb, infodengue

NOW = datetime.now(UTC).replace(microsecond=0)


@pytest.fixture(autouse=True)
def fake_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http, "get_json", fakes.get_json)
    monkeypatch.setattr(http, "get_text", lambda url, **kw: None)
    bcb._sgs.cache_clear()
    infodengue._alertcity.cache_clear()


@pytest.mark.parametrize("slug", sorted(REGISTRY))
def test_cada_dataset_passa_no_contrato_e_na_qualidade(slug: str) -> None:
    ds, csv = runner._build_one(REGISTRY[slug], NOW)
    assert ds.rows > 0 and ds.kpis and ds.charts and ds.insights
    header = csv.splitlines()[0].split(",")
    assert header == [c.name for c in ds.columns]


# ----------------------------------------------------------------------------- IPCA


def month_starts(n: int) -> pd.DatetimeIndex:
    last = pd.Timestamp(date.today()).to_period("M").to_timestamp() - pd.DateOffset(months=1)
    return pd.date_range(end=last, periods=n, freq="MS")


def test_ipca_indicadores_e_destaques_com_numeros_conhecidos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    idx = month_starts(120)
    a12 = pd.Series(4.0, index=idx)
    a12.iloc[30] = 12.0  # pico da série
    pattern = [2, 2, 9, 9, 9, 2, 2, 2, 9, 9, 2, 9]  # últimos 12 meses: 6 acima do teto
    a12.iloc[-12:] = pattern
    monthly = pd.Series(0.3, index=idx)
    series = {433: monthly, 13522: a12}
    monkeypatch.setattr(bcb, "sgs", lambda code, start, end=None: series[code].copy())

    ds, _ = runner._build_one(REGISTRY["ipca"], NOW)
    k12, kmes, kacima = ds.kpis
    teto = sum(_target(idx[-1].year))
    assert 2 < teto < 9  # o padrão acima só faz sentido com o teto entre 2 e 9
    assert k12.value == 9.0 and k12.status == "serious"
    assert k12.delta and k12.delta.value == pytest.approx(7.0)
    assert k12.range and k12.range.hi == pytest.approx(teto)
    assert kmes.value == pytest.approx(0.3) and kmes.spark_kind == "bars"
    assert kacima.value == 6 and kacima.dots == [v > teto for v in pattern]

    labels = [h.label for h in ds.highlights]
    assert labels[1] == "1 mês acima do teto"  # só o último mês da sequência mais recente
    peak = ds.highlights[-1]
    assert peak.at == idx[30].strftime("%Y-%m-%d") and "12,00" in peak.text


# ----------------------------------------------------------------------------- Estudo


def test_estudo_dengue_clima_resume_o_backtest_de_cada_capital() -> None:
    ds, csv = runner._build_one(REGISTRY["estudo-dengue-clima"], NOW)
    table = pd.read_csv(io.StringIO(csv))
    assert table["cidade"].nunique() == 6
    assert (table.loc[table["modelo"] == "Ingênuo", "ganho_vs_ingenuo"] == 0).all()
    best, helped, effect = ds.kpis
    assert best.status in {"good", "warning"}
    assert helped.dots is not None and helped.value == sum(helped.dots)
    assert helped.dot_labels == ["RJ", "SP", "MG", "DF", "GO", "PR"]
    gains = {i.label: i.value for i in ds.charts[0].items}
    assert best.value == pytest.approx(max(gains.values()), abs=0.06)


# ----------------------------------------------------------------------------- Runner


def test_execucao_completa_publica_catalogo_e_status(tmp_path: Path) -> None:
    assert runner.run(tmp_path) == 0
    status = json.loads((tmp_path / "status.json").read_text())
    assert all(d["ok"] for d in status["datasets"])
    catalog = json.loads((tmp_path / "catalog.json").read_text())
    assert {d["slug"] for d in catalog["datasets"]} == set(REGISTRY)


def failing(slug: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom():
        raise http.FetchError("fonte fora do ar")

    monkeypatch.setitem(REGISTRY, slug, replace(REGISTRY[slug], build=boom))


def test_falha_mantem_a_versao_anterior_marcada_como_desatualizada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.run(tmp_path, only=["selic"])
    before = (tmp_path / "datasets" / "selic.json").read_text()
    failing("selic", monkeypatch)
    runner.run(tmp_path, only=["selic"])
    assert (tmp_path / "datasets" / "selic.json").read_text() == before
    st = next(
        d
        for d in json.loads((tmp_path / "status.json").read_text())["datasets"]
        if d["slug"] == "selic"
    )
    assert not st["ok"] and st["stale"] and "fonte fora do ar" in st["error"]


def test_sem_versao_anterior_usa_a_copia_versionada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built, snapshots, fresh = tmp_path / "built", tmp_path / "snap", tmp_path / "fresh"
    runner.run(built, only=["populacao-uf"])
    runner.save_snapshot("populacao-uf", built, snapshots)
    monkeypatch.setattr(runner, "SNAPSHOT_DIR", snapshots)
    failing("populacao-uf", monkeypatch)

    runner.run(fresh, only=["populacao-uf"])
    assert (fresh / "datasets" / "populacao-uf.json").exists()
    assert (fresh / "csv" / "populacao-uf.csv").exists()
    catalog = json.loads((fresh / "catalog.json").read_text())
    entry = next(d for d in catalog["datasets"] if d["slug"] == "populacao-uf")
    assert entry["stale"] is True


def test_sem_versao_anterior_nem_copia_nao_publica_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "SNAPSHOT_DIR", tmp_path / "vazio")
    failing("dolar", monkeypatch)
    runner.run(tmp_path / "out", only=["dolar"])
    assert not (tmp_path / "out" / "datasets" / "dolar.json").exists()
    status = json.loads((tmp_path / "out" / "status.json").read_text())
    assert status["datasets"][0]["ok"] is False and status["datasets"][0]["stale"] is False
