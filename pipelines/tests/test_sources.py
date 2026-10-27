"""Testes dos conectores com HTTP simulado (httpx.MockTransport): sem rede, determinísticos."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from urllib.parse import unquote

import httpx
import pytest

from dataan import http
from dataan.sources import bcb, ibge

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    bcb._sgs.cache_clear()


def use(handler: Handler) -> list[str]:
    """Liga o cliente HTTP a um handler simulado e devolve a lista de URLs pedidas."""
    calls: list[str] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(unquote(str(request.url)))
        return handler(request)

    http._client = httpx.Client(transport=httpx.MockTransport(wrapped))
    return calls


def sgs_rows(start: date, end: date, value: str = "5.0") -> list[dict]:
    return [
        {"data": f"01/{m:02d}/{y}", "valor": value}
        for y in range(start.year, end.year + 1)
        for m in range(1, 13)
        if date(y, m, 1) >= start and date(y, m, 1) <= end
    ]


def params_dates(request: httpx.Request) -> tuple[date, date]:
    def parse(s: str) -> date:
        d, m, y = (int(x) for x in s.split("/"))
        return date(y, m, d)

    q = request.url.params
    return parse(q["dataInicial"]), parse(q["dataFinal"])


# ----------------------------------------------------------------------------- BCB


def test_bcb_objeto_de_erro_com_200_e_repetido() -> None:
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(200, json={"erro": {"message": "Limite de requisições"}})
        return httpx.Response(200, json=sgs_rows(*params_dates(request)))

    use(handler)
    s = bcb.sgs(433, date(2020, 1, 1), date(2021, 6, 30))
    assert len(s) == 18
    assert state["n"] >= 2


def test_bcb_erro_persistente_mostra_a_mensagem_da_api() -> None:
    use(lambda r: httpx.Response(200, json={"erro": {"message": "janela inválida"}}))
    with pytest.raises(http.FetchError) as exc:
        bcb.sgs(1, date(2020, 1, 1), date(2021, 1, 1))
    assert "janela inválida" in exc.value.reason


def test_bcb_lacuna_no_meio_da_serie_nao_passa_em_silencio() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        start, end = params_dates(request)
        if start.year == 2015:  # bloco do meio some (404 transitório)
            return httpx.Response(404)
        return httpx.Response(200, json=sgs_rows(start, end))

    use(handler)
    with pytest.raises(http.FetchError, match="vazio no meio da série"):
        bcb.sgs(433, date(2006, 1, 1), date(2026, 6, 30))


def test_bcb_blocos_vazios_antes_do_inicio_sao_normais() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        start, end = params_dates(request)
        rows = [r for r in sgs_rows(start, end) if int(r["data"][-4:]) >= 2016]
        return httpx.Response(200, json=rows) if rows else httpx.Response(404)

    use(handler)
    s = bcb.sgs(433, date(2006, 1, 1), date(2020, 12, 31))
    assert s.index.min().year == 2016


# ----------------------------------------------------------------------------- IBGE

UFS = list(ibge.UF_SIGLAS)


def servicodados_payload(ufs: list[str]) -> list[dict]:
    series = [
        {"localidade": {"id": uf, "nome": f"UF {uf}"}, "serie": {"2024": "1000", "2025": "1010"}}
        for uf in ufs
    ]
    return [{"id": "9324", "resultados": [{"classificacoes": [], "series": series}]}]


def apisidra_payload() -> list[dict]:
    header = {
        "NC": "Nível Territorial (Código)", "NN": "Nível Territorial", "MC": "Unidade de Medida (Código)",
        "MN": "Unidade de Medida", "V": "Valor", "D1C": "Unidade da Federação (Código)",
        "D1N": "Unidade da Federação", "D2C": "Ano (Código)", "D2N": "Ano",
        "D3C": "Variável (Código)", "D3N": "Variável",
    }  # fmt: skip
    rows = [
        {
            "NC": "3",
            "MC": "45",
            "V": "2000",
            "D1C": uf,
            "D1N": f"UF {uf}",
            "D2C": ano,
            "D2N": ano,
            "D3C": "9324",
        }
        for uf in UFS
        for ano in ("2024", "2025")
    ]
    return [header, *rows]


def test_ibge_fallback_para_apisidra_sem_query_e_com_sintaxe_traduzida() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "servicodados" in request.url.host:
            raise httpx.ConnectTimeout("timed out", request=request)
        return httpx.Response(200, json=apisidra_payload())

    calls = use(handler)
    df = ibge.agregado(6579, 9324, periodos="-2")
    sidra = [c for c in calls if "apisidra" in c]
    assert sidra and sidra[0].endswith("/t/6579/n3/all/v/9324/p/last 2")
    assert "?" not in sidra[0]
    assert df["localidade_id"].nunique() == 27
    assert set(df["periodo"]) == {"2024", "2025"}


@pytest.mark.parametrize(
    "body",
    [
        servicodados_payload(UFS[:10]),  # resposta parcial
        [],  # vazia
        {"message": "erro interno"},  # objeto de erro com 200
    ],
)
def test_ibge_servicodados_incompleto_tambem_usa_o_alternativo(body: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "servicodados" in request.url.host:
            return httpx.Response(200, json=body)
        return httpx.Response(200, json=apisidra_payload())

    use(handler)
    df = ibge.agregado(6579, 9324, periodos="-2")
    assert df["localidade_id"].nunique() == 27


def test_ibge_os_dois_fora_mostram_as_duas_causas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "servicodados" in request.url.host:
            raise httpx.ConnectTimeout("timed out", request=request)
        return httpx.Response(400, text="Parâmetro inválido")

    use(handler)
    with pytest.raises(http.FetchError) as exc:
        ibge.agregado(6579, 9324, periodos="-2")
    msg = str(exc.value)
    assert "servicodados: timed out" in msg
    assert "apisidra:" in msg and "400" in msg
    assert len(msg) < 600  # cabe no status sem cortar a segunda causa


def test_ibge_sintaxe_de_periodos_e_niveis() -> None:
    assert ibge._sidra_path("N3[all]", "-2") == ("n3", "all", "last 2", "3")
    assert ibge._sidra_path("N1[all]", "2022|2024") == ("n1", "all", "2022,2024", "1")
    with pytest.raises(ValueError):
        ibge._sidra_path("N3[all]", "-")


def test_servicodados_preserva_o_periodo_como_codigo() -> None:
    use(lambda r: httpx.Response(200, json=servicodados_payload(UFS)))
    df = ibge.agregado(6579, 9324, periodos="-2")
    assert json.loads(df.to_json(orient="records"))[0]["periodo"] in {"2024", "2025"}
