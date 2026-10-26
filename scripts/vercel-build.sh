#!/usr/bin/env bash
# Build do serviço `web` na Vercel: roda o pipeline Python (gera web/public/data)
# e depois o Astro. Executado a partir de web/ (raiz do serviço).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${REPO}/.venv-build"

PY="$(command -v python3.13 || command -v python3.12 || command -v python3 || true)"
if [[ -z "${PY}" ]]; then
  echo "Erro: Python 3.11+ não encontrado no ambiente de build." >&2
  exit 1
fi
if ! "${PY}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Erro: o pipeline precisa de Python 3.11+; encontrado $("${PY}" --version)." >&2
  exit 1
fi

"${PY}" -m venv "${VENV}"
"${VENV}/bin/pip" install --quiet --disable-pip-version-check "${REPO}/pipelines"

# A versão em produção serve de fallback se alguma fonte estiver fora do ar.
SEED_ARGS=()
if [[ -n "${DATAAN_SEED_URL:-}" ]]; then
  SEED_ARGS=(--seed-from "${DATAAN_SEED_URL}")
elif [[ -n "${VERCEL_PROJECT_PRODUCTION_URL:-}" ]]; then
  SEED_ARGS=(--seed-from "https://${VERCEL_PROJECT_PRODUCTION_URL}/data")
fi

"${VENV}/bin/python" -m dataan run --out "${REPO}/web/public/data" ${SEED_ARGS[@]+"${SEED_ARGS[@]}"}

cd "${REPO}/web"
npx astro build
