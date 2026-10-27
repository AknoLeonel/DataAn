"""Linha de comando: `python -m dataan run`, `python -m dataan list`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "web" / "public" / "data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dataan", description="Pipelines de dados do DataAn")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="coleta, valida e publica os datasets")
    p_run.add_argument("--only", nargs="+", metavar="SLUG", help="roda só estes datasets")
    p_run.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help=f"pasta de saída (padrão: {DEFAULT_OUT})"
    )
    p_run.add_argument(
        "--seed-from", metavar="URL", help="URL base dos dados já publicados (fallback)"
    )
    p_run.add_argument("--strict", action="store_true", help="falha se qualquer dataset falhar")
    p_run.add_argument("-v", "--verbose", action="store_true")

    sub.add_parser("list", help="lista os datasets registrados")

    p_snap = sub.add_parser(
        "snapshot", help="guarda a versão gerada de um dataset como cópia versionada (fallback)"
    )
    p_snap.add_argument("slug")
    p_snap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="pasta onde o run gravou")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.cmd == "list":
        import dataan.datasets  # noqa: F401
        from dataan.registry import REGISTRY

        for spec in REGISTRY.values():
            print(f"{spec.slug:28} {spec.category:15} {spec.title}")
        return 0

    if args.cmd == "snapshot":
        from dataan.runner import save_snapshot

        print(f"Cópia salva em {save_snapshot(args.slug, args.out)}. Faça commit desse arquivo.")
        return 0

    from dataan.runner import run

    return run(args.out, only=args.only, seed_from=args.seed_from, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
