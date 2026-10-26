// Gráfico de linhas (séries temporais) com faixa de intervalo, referência e marcador.
import { formatDate, formatTick, formatValue, parseDate } from '../format';
import type { LineChart } from '../types';
import { clamp, esc, linear, nice, r1, svgOpen, textWidth, timeTicks, type Rendered, type TipRow } from './common';

export interface LineOptions {
  height?: number;
  compact?: boolean;
}

interface Prepared {
  key: string;
  name: string;
  color: number;
  dashed: boolean;
  pts: [number, number | null][];
  band?: [number, number, number][];
}

function pathFor(pts: [number, number | null][], x: (t: number) => number, y: (v: number) => number, step: boolean): string {
  let d = '';
  let open = false;
  for (const [t, v] of pts) {
    if (v === null) {
      open = false;
      continue;
    }
    const px = r1(x(t));
    const py = r1(y(v));
    if (!open) {
      d += `M${px},${py}`;
      open = true;
    } else if (step) {
      d += `H${px}V${py}`;
    } else {
      d += `L${px},${py}`;
    }
  }
  return d;
}

/** Valor da série em t: exato ou, em séries em degrau, o último valor até t. */
function valueAt(s: Prepared, t: number, step: boolean): number | null {
  let lo = 0;
  let hi = s.pts.length - 1;
  if (hi < 0 || t < s.pts[0][0] || (!step && t > s.pts[hi][0])) return null;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (s.pts[mid][0] <= t) lo = mid;
    else hi = mid - 1;
  }
  const [pt, v] = s.pts[lo];
  if (pt === t || step) return v;
  return null;
}

export function renderLine(spec: LineChart, width: number, opts: LineOptions = {}): Rendered {
  const compact = opts.compact ?? false;
  const height = opts.height ?? (compact ? 180 : Math.round(clamp(width * 0.55, 220, 340)));
  const series: Prepared[] = spec.series.map((s) => ({
    key: s.key,
    name: s.name,
    color: s.color,
    dashed: s.style === 'dashed',
    pts: s.points.map(([d, v]) => [parseDate(d), v]),
    band: s.band?.map(([d, lo, hi]) => [parseDate(d), lo, hi]),
  }));

  let t0 = Infinity, t1 = -Infinity, v0 = Infinity, v1 = -Infinity;
  for (const s of series) {
    for (const [t, v] of s.pts) {
      t0 = Math.min(t0, t);
      t1 = Math.max(t1, t);
      if (v !== null) {
        v0 = Math.min(v0, v);
        v1 = Math.max(v1, v);
      }
    }
    for (const [, lo, hi] of s.band ?? []) {
      v0 = Math.min(v0, lo);
      v1 = Math.max(v1, hi);
    }
  }
  for (const r of spec.reference) {
    v0 = Math.min(v0, r.value);
    v1 = Math.max(v1, r.value);
  }
  if (spec.y_zero) {
    v0 = Math.min(0, v0);
    v1 = Math.max(0, v1);
  }
  const yScale = nice(v0, v1, compact ? 3 : height > 260 ? 5 : 4);
  const tickLabels = yScale.ticks.map((t) => formatTick(t, spec.format, yScale.step));

  // Rótulo de valor na ponta só quando há uma série (com mais, legenda + tooltip).
  const solid = series.filter((s) => !s.dashed);
  const single = series.length === 1 && !compact;
  let endLabel = '';
  let endPoint: [number, number] | null = null;
  if (single) {
    const last = [...series[0].pts].reverse().find(([, v]) => v !== null);
    if (last) {
      endPoint = [last[0], last[1] as number];
      endLabel = formatValue(last[1] as number, spec.format, { unit: false });
    }
  }

  const m = {
    top: spec.marker ? 22 : 10,
    right: single ? textWidth(endLabel) + 14 : 10,
    bottom: 24,
    left: Math.max(...tickLabels.map((l) => textWidth(l, 11))) + 10,
  };
  const plotL = m.left, plotR = width - m.right, plotT = m.top, plotB = height - m.bottom;
  const x = linear(t0, t1, plotL, plotR);
  const y = linear(yScale.min, yScale.max, plotB, plotT);

  const parts: string[] = [];
  // Grade e eixo Y (hairlines recessivas)
  yScale.ticks.forEach((t, i) => {
    const py = r1(y(t));
    parts.push(`<line class="${t === 0 && yScale.min < 0 ? 'axis' : 'grid'}" x1="${plotL}" x2="${r1(plotR)}" y1="${py}" y2="${py}"/>`);
    parts.push(`<text class="tick" x="${plotL - 6}" y="${py}" dy="0.32em" text-anchor="end">${esc(tickLabels[i])}</text>`);
  });
  parts.push(`<line class="axis" x1="${plotL}" x2="${r1(plotR)}" y1="${r1(plotB)}" y2="${r1(plotB)}"/>`);

  // Eixo X
  const maxTicks = Math.max(2, Math.floor((plotR - plotL) / (compact ? 64 : 72)));
  for (const tk of timeTicks(t0, t1, maxTicks)) {
    const px = x(tk.t);
    const w = textWidth(tk.label, 11);
    const anchor = px - w / 2 < 0 ? 'start' : px + w / 2 > width ? 'end' : 'middle';
    parts.push(`<line class="axis" x1="${r1(px)}" x2="${r1(px)}" y1="${r1(plotB)}" y2="${r1(plotB + 4)}"/>`);
    parts.push(`<text class="tick" x="${r1(px)}" y="${height - 6}" text-anchor="${anchor}">${esc(tk.label)}</text>`);
  }

  // Referências (ex.: diretriz da OMS)
  for (const ref of spec.reference) {
    const py = r1(y(ref.value));
    parts.push(`<line class="ref" x1="${plotL}" x2="${r1(plotR)}" y1="${py}" y2="${py}"/>`);
    parts.push(`<text class="ref-label" x="${r1(plotR - 2)}" y="${py - 5}" text-anchor="end">${esc(ref.label)} ${esc(formatValue(ref.value, spec.format, { unit: false }))}</text>`);
  }

  // Faixas (intervalos de previsão)
  for (const s of series) {
    if (!s.band?.length) continue;
    const top = s.band.map(([t, , hi]) => `${r1(x(t))},${r1(y(hi))}`);
    const bottom = s.band.map(([t, lo]) => `${r1(x(t))},${r1(y(lo))}`).reverse();
    parts.push(`<polygon class="band s${s.color}" points="${[...top, ...bottom].join(' ')}"/>`);
  }

  // Marcador vertical (ex.: "hoje" / início da previsão)
  if (spec.marker) {
    const px = r1(x(parseDate(spec.marker[0])));
    parts.push(`<line class="marker" x1="${px}" x2="${px}" y1="${plotT - 4}" y2="${r1(plotB)}"/>`);
    parts.push(`<text class="marker-label" x="${px}" y="${plotT - 8}" text-anchor="middle">${esc(spec.marker[1])}</text>`);
  }

  // Linhas
  for (const s of series) {
    const d = pathFor(s.pts, x, y, spec.step);
    if (d) parts.push(`<path class="line s${s.color}${s.dashed ? ' dashed' : ''}" d="${d}"/>`);
  }

  // Ponto final de cada série sólida (com anel da cor da superfície)
  for (const s of solid) {
    const last = [...s.pts].reverse().find(([, v]) => v !== null);
    if (!last) continue;
    parts.push(`<circle class="dot s${s.color}" cx="${r1(x(last[0]))}" cy="${r1(y(last[1] as number))}" r="4"/>`);
  }
  if (endPoint) {
    parts.push(`<text class="end-label" x="${r1(x(endPoint[0]) + 8)}" y="${r1(y(endPoint[1]))}" dy="0.32em">${esc(endLabel)}</text>`);
  }

  const lastSolid = solid[0] ? [...solid[0].pts].reverse().find(([, v]) => v !== null) : undefined;
  const aria = `${spec.title}. Gráfico de linhas${lastSolid ? `; último valor de ${solid[0].name}: ${formatValue(lastSolid[1] as number, spec.format)} em ${formatDate(new Date(lastSolid[0]).toISOString().slice(0, 10), spec.x_kind)}` : ''}.`;
  const svg = svgOpen(width, height, aria) + parts.join('') + '</svg>';

  // Interação: crosshair que encontra o X mais próximo e lista todas as séries.
  const allX = Array.from(new Set(series.flatMap((s) => s.pts.map(([t]) => t)))).sort((a, b) => a - b);
  const pxs = allX.map((t) => x(t));
  const at = (i: number) => series.map((s) => ({ s, v: valueAt(s, allX[i], spec.step) }));
  return {
    svg,
    height,
    interaction: {
      kind: 'x',
      plot: { left: plotL, right: plotR, top: plotT, bottom: plotB },
      xs: pxs,
      title: (i) => formatDate(new Date(allX[i]).toISOString().slice(0, 10), spec.x_kind),
      rows: (i) =>
        at(i)
          .filter(({ v }) => v !== null)
          .map(({ s, v }): TipRow => {
            const band = s.band?.find(([t]) => t === allX[i]);
            const extra = band && band[1] !== band[2] ? ` (${formatValue(band[1], spec.format, { unit: false })}–${formatValue(band[2], spec.format, { unit: false })})` : '';
            return { name: s.name, value: formatValue(v as number, spec.format) + extra, color: `s${s.color}`, dashed: s.dashed };
          }),
      dots: (i) => at(i).filter(({ v }) => v !== null).map(({ s, v }) => ({ y: y(v as number), color: `s${s.color}` })),
    },
  };
}
