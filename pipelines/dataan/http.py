"""Cliente HTTP resiliente para APIs públicas.

APIs governamentais oscilam: timeouts, 5xx e limites de taxa são normais.
Todo acesso à rede passa por `get_json`, que aplica timeout, retentativas com
backoff exponencial, limite de tamanho e um User-Agent identificável.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "DataAn/0.1 (+https://github.com/AknoLeonel/DataAn)"
MAX_BYTES = 60 * 1024 * 1024
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}

_client: httpx.Client | None = None


class FetchError(RuntimeError):
    """Falha definitiva ao buscar dados de uma fonte."""


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=httpx.Timeout(45.0, connect=15.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    return _client


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    retries: int = 4,
    backoff: float = 2.0,
    not_found_ok: bool = False,
) -> Any:
    """GET com retentativas. Retorna o JSON decodificado (ou None em 404 se permitido)."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = _get_client().get(url, params=params)
            if resp.status_code == 404 and not_found_ok:
                return None
            if resp.status_code in RETRY_STATUS:
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            if len(resp.content) > MAX_BYTES:
                raise FetchError(f"Resposta grande demais de {url} ({len(resp.content)} bytes)")
            return resp.json()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code not in RETRY_STATUS:
                break
        except (httpx.TransportError, ValueError) as exc:
            last_exc = exc
        if attempt < retries:
            wait = backoff * (2**attempt) + random.uniform(0, 1)  # noqa: S311 - jitter, não é cripto
            log.warning("Falha em %s (%s). Nova tentativa em %.1fs", url, last_exc, wait)
            time.sleep(wait)
    raise FetchError(f"Não foi possível obter {url}: {last_exc}") from last_exc


def get_text(url: str, *, timeout: float = 20.0) -> str | None:
    """GET simples, sem retentativa, para recursos opcionais (ex.: semear dados publicados)."""
    try:
        resp = _get_client().get(url, timeout=timeout)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200 or len(resp.content) > MAX_BYTES:
        return None
    return resp.text
