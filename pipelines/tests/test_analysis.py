"""Testes das análises com dados sintéticos de propriedades conhecidas."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dataan.analysis.experiment import HOLT, NAIVE, RIDGE, RIDGE_CLIMA, SEASONAL, backtest
from dataan.analysis.forecast import holt_forecast
from dataan.analysis.series import lttb, signed, to_points

WEEKS = 260


def weekly(values: np.ndarray, **cols: np.ndarray) -> pd.DataFrame:
    dates = pd.date_range("2021-01-03", periods=len(values), freq="7D")
    return pd.DataFrame({"date": dates, "casos_est": values, **cols})


def seasonal_cases(rng: np.random.Generator, n: int = WEEKS, noise: float = 0.1) -> np.ndarray:
    t = np.arange(n)
    season = np.exp(2.0 * np.cos((t - 14) / 52.18 * 2 * np.pi))
    return 40 * season * rng.lognormal(0, noise, n)


# ----------------------------------------------------------------------------- LTTB


def test_lttb_mantem_pontas_e_pico() -> None:
    y = np.zeros(1000)
    y[537] = 50.0
    idx = lttb(y, 60)
    assert len(idx) == 60
    assert idx[0] == 0 and idx[-1] == 999
    assert 537 in idx  # média simples apagaria o pico; LTTB não
    assert np.all(np.diff(idx) > 0)


def test_lttb_serie_curta_volta_inteira() -> None:
    assert list(lttb(np.arange(10.0), 50)) == list(range(10))


# ----------------------------------------------------------------------------- Holt


def test_holt_serie_constante_erro_zero() -> None:
    s = pd.Series(100.0, index=pd.date_range("2022-01-02", periods=80, freq="7D"))
    fc = holt_forecast(s, horizon=4)
    assert fc.mae == pytest.approx(0, abs=1e-6)
    np.testing.assert_allclose(fc.mean, 100.0, rtol=1e-6)
    assert list(fc.index) == list(pd.date_range("2023-07-16", periods=4, freq="7D"))


def test_holt_intervalo_contem_a_previsao_e_supera_ingenuo_em_tendencia() -> None:
    rng = np.random.default_rng(1)
    y = np.exp(np.linspace(2, 6, 90) + rng.normal(0, 0.03, 90))  # crescimento exponencial
    s = pd.Series(y, index=pd.date_range("2022-01-02", periods=90, freq="7D"))
    fc = holt_forecast(s, horizon=4)
    assert np.all(fc.lower <= fc.mean) and np.all(fc.mean <= fc.upper)
    assert fc.skill > 0.3  # tendência clara: Holt tem que bater "repetir o último"
    assert fc.mean[-1] > y[-1]


def test_holt_recusa_serie_curta() -> None:
    s = pd.Series(1.0, index=pd.date_range("2024-01-07", periods=30, freq="7D"))
    with pytest.raises(ValueError, match="curta"):
        holt_forecast(s)


# ----------------------------------------------------------------------------- Experimento


def test_experimento_sem_vazamento_do_futuro() -> None:
    """Mudar a última semana não pode mudar nenhuma previsão: todas as origens são anteriores."""
    rng = np.random.default_rng(2)
    cases = seasonal_cases(rng)
    temp = 25 + rng.normal(0, 1, WEEKS)
    base = backtest(weekly(cases, tempmed=temp, umidmed=temp * 3), origins=52)
    changed = cases.copy()
    changed[-1] *= 50
    other = backtest(weekly(changed, tempmed=temp, umidmed=temp * 3), origins=52)
    for model, preds in base.preds.items():
        pd.testing.assert_series_equal(preds, other.preds[model])
    assert other.mae[NAIVE] > base.mae[NAIVE]  # só o erro muda


def test_experimento_detecta_clima_que_antecede_os_casos() -> None:
    """Casos seguem a temperatura de semanas antes: o modelo com clima tem que ganhar."""
    rng = np.random.default_rng(3)
    n = WEEKS
    temp = 25 + np.cumsum(rng.normal(0, 0.6, n))  # sem sazonalidade: só o clima explica
    temp = 25 + (temp - temp.mean()) / temp.std() * 2
    log_cases = 3 + 0.8 * (np.roll(temp, 6) - 25)
    log_cases[:6] = 3
    cases = np.expm1(log_cases + rng.normal(0, 0.05, n))
    umid = 70 + rng.normal(0, 2, n)
    bt = backtest(weekly(cases, tempmed=temp, umidmed=umid), origins=52)
    assert bt.clima_ok
    assert bt.skill[RIDGE_CLIMA] > bt.skill[RIDGE] + 0.05


def test_experimento_sem_clima_pula_o_modelo_com_clima() -> None:
    rng = np.random.default_rng(4)
    bt = backtest(weekly(seasonal_cases(rng)), origins=52)
    assert not bt.clima_ok
    assert RIDGE_CLIMA not in bt.mae
    assert {NAIVE, SEASONAL, HOLT, RIDGE} <= set(bt.mae)
    assert bt.skill[NAIVE] == 0
    # Sazonalidade forte e regular: o sazonal ingênuo bate o ingênuo.
    assert bt.skill[SEASONAL] > 0


def test_experimento_clima_com_falhas_demais_nao_e_usado() -> None:
    rng = np.random.default_rng(5)
    temp = np.full(WEEKS, np.nan)
    temp[::3] = 25.0  # 2/3 faltando
    bt = backtest(weekly(seasonal_cases(rng), tempmed=temp, umidmed=temp), origins=52)
    assert not bt.clima_ok and RIDGE_CLIMA not in bt.mae


def test_experimento_recusa_serie_curta() -> None:
    rng = np.random.default_rng(6)
    with pytest.raises(ValueError, match="curta"):
        backtest(weekly(seasonal_cases(rng, n=120)), origins=52)


# ----------------------------------------------------------------------------- Utilitários


def test_to_points_ordena_e_trata_nulos() -> None:
    s = pd.Series([np.nan, 1.23456], index=pd.to_datetime(["2024-02-01", "2024-01-01"]))
    assert to_points(s, decimals=2) == [("2024-01-01", 1.23), ("2024-02-01", None)]


def test_textos_em_pt_br() -> None:
    assert signed(1234.5, 1) == "+1.234,5"
    assert signed(-4.4, 1) == "−4,4"  # sinal de menos tipográfico
    assert signed(0, 0) == "0"


@pytest.mark.parametrize(("n", "n_out"), [(10, 3), (11, 4), (1000, 60), (5432, 420)])
def test_lttb_indices_unicos_um_por_balde(n: int, n_out: int) -> None:
    rng = np.random.default_rng(n)
    idx = lttb(rng.normal(size=n), n_out)
    assert len(idx) == n_out and len(set(idx.tolist())) == n_out
    assert idx[0] == 0 and idx[-1] == n - 1
    assert np.all(np.diff(idx) > 0)
