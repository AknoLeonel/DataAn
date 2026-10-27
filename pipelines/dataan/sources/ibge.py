"""IBGE — API de agregados (SIDRA).

Documentação: https://servicodados.ibge.gov.br/api/docs/agregados?versao=3
O IBGE expõe os mesmos dados em dois servidores. O `servicodados` às vezes não
responde fora do Brasil (ex.: servidores de build nos EUA) ou responde vazio; nesse
caso usamos o `apisidra` (https://apisidra.ibge.gov.br), cujo formato traz uma
primeira linha de cabeçalho com o nome de cada coluna.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from dataan import http

log = logging.getLogger(__name__)

URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{agregado}/periodos/{periodos}/variaveis/{variavel}"
SIDRA_API = (
    "https://apisidra.ibge.gov.br/values/t/{agregado}/{nivel}/{sel}/v/{variavel}/p/{periodos}"
)
SIDRA = "https://sidra.ibge.gov.br/tabela/{agregado}"
COLUMNS = ["localidade_id", "localidade", "periodo", "valor"]

# Nome da coluna de localidade no cabeçalho do apisidra, por nível territorial.
NIVEIS = {"1": "Brasil", "2": "Grande Região", "3": "Unidade da Federação", "6": "Município"}
# Quantas localidades uma resposta completa tem (para detectar respostas parciais).
ESPERADO = {"N1[all]": 1, "N2[all]": 5, "N3[all]": 27}
PERIODOS = ("Ano", "Mês", "Trimestre", "Trimestre Móvel", "Semestre")

UF_SIGLAS = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}  # fmt: skip


def _check_servicodados(data: object) -> str | None:
    if not isinstance(data, list) or not data:
        return f"esperada lista de variáveis, veio {str(data)[:120]}"
    if not all(isinstance(v, dict) and isinstance(v.get("resultados"), list) for v in data):
        return f"variável sem 'resultados': {str(data)[:120]}"
    return None


def _check_apisidra(data: object) -> str | None:
    if not isinstance(data, list) or len(data) < 2 or not all(isinstance(r, dict) for r in data):
        return f"esperado cabeçalho + linhas, veio {str(data)[:120]}"
    return None


def _servicodados(agregado: int, variavel: int, periodos: str, localidades: str) -> pd.DataFrame:
    data = http.get_json(
        URL.format(agregado=agregado, periodos=periodos, variavel=variavel),
        params={"localidades": localidades},
        retries=3,
        validate=_check_servicodados,
    )
    rows = []
    for var in data:
        for res in var["resultados"]:
            for serie in res.get("series") or []:
                loc = serie.get("localidade") or {}
                for periodo, valor in (serie.get("serie") or {}).items():
                    rows.append([str(loc.get("id")), loc.get("nome"), str(periodo), valor])
    return pd.DataFrame(rows, columns=COLUMNS)


def _sidra_path(localidades: str, periodos: str) -> tuple[str, str, str, str]:
    """Traduz a sintaxe do servicodados para a do apisidra: N3[all] -> n3/all, -2 -> last 2."""
    m = re.fullmatch(r"N(\d+)\[([^\]]+)\]", localidades)
    if not m:
        raise ValueError(f"Localidades não suportadas no apisidra: {localidades}")
    nivel, sel = m.group(1), m.group(2)
    if re.fullmatch(r"-\d+", periodos):
        p = f"last {periodos[1:]}"
    elif re.fullmatch(r"[\d|]+", periodos):
        p = periodos.replace("|", ",")
    else:
        raise ValueError(f"Períodos não suportados no apisidra: {periodos}")
    return f"n{nivel}", sel, p, nivel


def _apisidra(agregado: int, variavel: int, periodos: str, localidades: str) -> pd.DataFrame:
    nivel_path, sel, p, nivel = _sidra_path(localidades, periodos)
    # O apisidra responde JSON por padrão e não aceita parâmetros de query.
    data = http.get_json(
        SIDRA_API.format(
            agregado=agregado, nivel=nivel_path, sel=sel, variavel=variavel, periodos=p
        ),
        retries=2,
        validate=_check_apisidra,
    )
    header, *body = data
    by_label = {str(label): key for key, label in header.items()}
    nome = NIVEIS.get(nivel)
    periodo_label = next((lb for lb in PERIODOS if f"{lb} (Código)" in by_label), None)
    needed = {
        "codigo": by_label.get(f"{nome} (Código)"),
        "nome": by_label.get(nome or ""),
        "periodo": by_label.get(f"{periodo_label} (Código)") if periodo_label else None,
        "valor": by_label.get("Valor"),
    }
    missing = [k for k, v in needed.items() if v is None]
    if missing:
        raise http.FetchError(f"apisidra {agregado}: cabeçalho sem {', '.join(missing)}")
    rows = [
        [
            str(r.get(needed["codigo"])),
            r.get(needed["nome"]),
            str(r.get(needed["periodo"])),
            r.get(needed["valor"]),
        ]
        for r in body
        if all(r.get(k) is not None for k in needed.values())
    ]
    return pd.DataFrame(rows, columns=COLUMNS)


def _clean(df: pd.DataFrame, localidades: str, agregado: int) -> pd.DataFrame:
    """Converte valores e rejeita respostas vazias ou parciais (para tentar o outro servidor)."""
    df = df.assign(valor=pd.to_numeric(df["valor"], errors="coerce")).dropna(subset=["valor"])
    if df.empty:
        raise http.FetchError(f"IBGE {agregado}: sem valores", reason="sem valores")
    expected = ESPERADO.get(localidades)
    got = df["localidade_id"].nunique()
    if expected and got < expected:
        raise http.FetchError(
            f"IBGE {agregado}: só {got} de {expected} localidades",
            reason=f"resposta parcial ({got} de {expected} localidades)",
        )
    return df


def agregado(
    agregado: int, variavel: int, periodos: str = "-1", localidades: str = "N3[all]"
) -> pd.DataFrame:
    """Valores em formato longo: localidade_id, localidade, periodo, valor."""
    try:
        return _clean(
            _servicodados(agregado, variavel, periodos, localidades), localidades, agregado
        )
    except http.FetchError as first:
        log.warning("IBGE servicodados falhou (%s); tentando apisidra", first.reason)
        try:
            return _clean(
                _apisidra(agregado, variavel, periodos, localidades), localidades, agregado
            )
        except http.FetchError as second:
            raise http.FetchError(
                f"IBGE indisponível nos dois servidores — servicodados: {first.reason} | "
                f"apisidra: {second.reason}",
                reason=f"servicodados: {first.reason} | apisidra: {second.reason}",
            ) from second
