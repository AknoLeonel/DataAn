"""Orquestra a execução: roda cada dataset isolado, valida, publica e registra o status.

Garantias operacionais:
- Um dataset que falha não derruba os outros.
- Nada é publicado sem passar pelo contrato (Pydantic) e pelas checagens de qualidade.
- Em caso de falha, a última versão válida continua publicada e é marcada como desatualizada.
- Escritas são atômicas (arquivo temporário + rename): nunca fica JSON pela metade.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from dataan import http
from dataan.analysis.quality import check_dataset, require
from dataan.models import (
    Catalog,
    CatalogEntry,
    Category,
    Dataset,
    DatasetStatus,
    RunSummary,
    Status,
)
from dataan.registry import CATEGORIES, REGISTRY, DatasetSpec

log = logging.getLogger(__name__)
HISTORY_SIZE = 60


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        os.chmod(tmp, 0o644)  # mkstemp cria 0600; o site precisa ler
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _dump(model) -> str:
    data = model.model_dump(mode="json", exclude_none=True)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _load(path: Path, model):
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        log.warning("Ignorando %s: %s", path, exc)
        return None


def seed(out_dir: Path, base_url: str) -> int:
    """Baixa a última versão publicada como ponto de partida (fallback se uma fonte cair)."""
    base = base_url.rstrip("/")
    raw = http.get_text(f"{base}/catalog.json")
    if not raw:
        log.info("Nenhum catálogo publicado em %s; seguindo sem semente.", base)
        return 0
    try:
        catalog = Catalog.model_validate_json(raw)
    except ValidationError as exc:
        log.warning(
            "Catálogo publicado incompatível (%s); seguindo sem semente.", exc.error_count()
        )
        return 0
    seeded = 0
    for entry in catalog.datasets:  # slugs já validados pelo modelo: sem path traversal
        target = out_dir / "datasets" / f"{entry.slug}.json"
        if target.exists():
            continue
        body = http.get_text(f"{base}/datasets/{entry.slug}.json")
        if not body:
            continue
        try:
            Dataset.model_validate_json(body)
        except ValidationError:
            continue
        _write(target, body)
        csv = http.get_text(f"{base}/csv/{entry.slug}.csv")
        if csv:
            _write(out_dir / "csv" / f"{entry.slug}.csv", csv)
        seeded += 1
    status_path = out_dir / "status.json"
    if not status_path.exists():
        body = http.get_text(f"{base}/status.json")
        if body:
            try:
                Status.model_validate_json(body)
                _write(status_path, body)
            except ValidationError:
                pass
    log.info("Semeados %d datasets a partir de %s", seeded, base)
    return seeded


def _build_one(spec: DatasetSpec, now: datetime) -> tuple[Dataset, str]:
    b = spec.build()
    ds = Dataset(
        slug=spec.slug,
        title=spec.title,
        summary=spec.summary,
        description=spec.description,
        category=spec.category,
        tags=list(spec.tags),
        sources=list(spec.sources),
        frequency=spec.frequency,
        coverage=b.coverage,
        updated_at=now,
        data_until=b.data_until,
        kpis=b.kpis,
        charts=b.charts,
        insights=b.insights,
        highlights=b.highlights,
        methodology=[*spec.methodology, *b.methodology],
        model=b.model,
        columns=list(spec.columns),
        rows=len(b.table),
    )
    check_dataset(ds)
    require(len(b.table) > 0, "tabela vazia")
    if spec.columns:
        documented = [c.name for c in spec.columns]
        require(
            list(b.table.columns) == documented,
            f"colunas do CSV {list(b.table.columns)} diferem das documentadas {documented}",
        )
    return ds, b.table.to_csv(index=False)


def _github_report(statuses: list[DatasetStatus]) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    for st in statuses:
        if not st.ok:
            msg = (st.error or "erro").replace("\n", " ")
            print(f"::warning title=Dataset {st.slug} falhou::{msg}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [
            "## Pipeline de dados",
            "",
            "| Dataset | Status | Linhas | Tempo | Detalhe |",
            "|---|---|---|---|---|",
        ]
        for st in statuses:
            icon = "✅ ok" if st.ok else ("⚠️ desatualizado" if st.stale else "❌ falhou")
            detail = (st.error or "").replace("|", "/")[:120]
            lines.append(f"| `{st.slug}` | {icon} | {st.rows} | {st.duration_s:.1f}s | {detail} |")
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def run(
    out_dir: Path,
    only: list[str] | None = None,
    seed_from: str | None = None,
    strict: bool = False,
) -> int:
    import dataan.datasets  # noqa: F401  (registra os datasets)

    out_dir = out_dir.resolve()
    (out_dir / "datasets").mkdir(parents=True, exist_ok=True)
    (out_dir / "csv").mkdir(parents=True, exist_ok=True)
    if seed_from:
        seed(out_dir, seed_from)

    unknown = [s for s in only or [] if s not in REGISTRY]
    if unknown:
        raise SystemExit(f"Datasets desconhecidos: {', '.join(unknown)}")
    selected = [REGISTRY[s] for s in only] if only else list(REGISTRY.values())

    previous = None
    if (out_dir / "status.json").exists():
        previous = _load(out_dir / "status.json", Status)
    prev_by_slug = {d.slug: d for d in previous.datasets} if previous else {}

    started = time.perf_counter()
    now = datetime.now(UTC).replace(microsecond=0)
    results: dict[str, DatasetStatus] = {}
    for spec in selected:
        t0 = time.perf_counter()
        target = out_dir / "datasets" / f"{spec.slug}.json"
        log.info("▶ %s", spec.slug)
        try:
            ds, csv = _build_one(spec, now)
            _write(target, _dump(ds))
            _write(out_dir / "csv" / f"{spec.slug}.csv", csv)
            results[spec.slug] = DatasetStatus(
                slug=spec.slug,
                title=spec.title,
                ok=True,
                stale=False,
                duration_s=round(time.perf_counter() - t0, 2),
                rows=ds.rows,
                updated_at=now,
                data_until=ds.data_until,
            )
            log.info("✔ %s (%d linhas, %.1fs)", spec.slug, ds.rows, time.perf_counter() - t0)
        except Exception as exc:  # isolamento: qualquer erro fica restrito ao dataset
            log.exception("✘ %s", spec.slug)
            old = _load(target, Dataset) if target.exists() else None
            results[spec.slug] = DatasetStatus(
                slug=spec.slug,
                title=spec.title,
                ok=False,
                stale=old is not None,
                error=f"{type(exc).__name__}: {str(exc)[:600]}",
                duration_s=round(time.perf_counter() - t0, 2),
                rows=old.rows if old else 0,
                updated_at=old.updated_at if old else None,
                data_until=old.data_until if old else None,
            )

    # Datasets não executados nesta rodada (--only) mantêm o status anterior.
    statuses: list[DatasetStatus] = []
    for slug, spec in REGISTRY.items():
        if slug in results:
            statuses.append(results[slug])
        elif slug in prev_by_slug:
            statuses.append(prev_by_slug[slug])
        elif (out_dir / "datasets" / f"{slug}.json").exists():
            statuses.append(
                DatasetStatus(slug=slug, title=spec.title, ok=True, stale=False, duration_s=0)
            )

    status_by_slug = {s.slug: s for s in statuses}
    entries: list[CatalogEntry] = []
    for slug in REGISTRY:
        path = out_dir / "datasets" / f"{slug}.json"
        ds = _load(path, Dataset) if path.exists() else None
        if ds is None:
            continue
        st = status_by_slug.get(slug)
        entries.append(
            CatalogEntry(
                slug=ds.slug,
                title=ds.title,
                summary=ds.summary,
                category=ds.category,
                tags=ds.tags,
                frequency=ds.frequency,
                updated_at=ds.updated_at,
                data_until=ds.data_until,
                stale=bool(st and st.stale),
                sources=[s.name for s in ds.sources],
                headline=ds.kpis[0] if ds.kpis else None,
            )
        )
    order = list(CATEGORIES)
    entries.sort(key=lambda e: order.index(e.category))
    counts = {c: sum(1 for e in entries if e.category == c) for c in CATEGORIES}
    categories = [
        Category(**cat.model_dump(exclude={"count"}), count=counts[slug])
        for slug, cat in CATEGORIES.items()
        if counts[slug]
    ]
    _write(
        out_dir / "catalog.json",
        _dump(Catalog(generated_at=now, categories=categories, datasets=entries)),
    )

    ok = sum(1 for r in results.values() if r.ok)
    failed = len(results) - ok
    history = list(previous.history) if previous else []
    history.append(
        RunSummary(at=now, ok=ok, failed=failed, results={s: r.ok for s, r in results.items()})
    )
    run_url = None
    if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_REPOSITORY"):
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        run_url = (
            f"{server}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        )
    status = Status(
        generated_at=now,
        run_url=run_url,
        duration_s=round(time.perf_counter() - started, 2),
        datasets=statuses,
        history=history[-HISTORY_SIZE:],
    )
    _write(out_dir / "status.json", _dump(status))
    _github_report(list(results.values()))

    log.info("Concluído: %d ok, %d com falha, %d no catálogo", ok, failed, len(entries))
    if strict and failed:
        return 1
    return 1 if results and ok == 0 and not entries else 0
