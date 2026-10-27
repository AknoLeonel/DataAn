// Barras horizontais (rankings). Mobile-first: em telas estreitas o rótulo vai acima da barra.
import { formatTick, formatValue } from '../format';
import type { BarChart } from '../types';
import { barPath, esc, linear, nice, r1, svgOpen, textWidth, type Rendered } from './common';

const NARROW = 520;

export function renderBar(spec: BarChart, width: number, animate = false): Rendered {
  const narrow = width < NARROW;
  const items = spec.items;
  const anyHighlight = items.some((i) => i.highlight);
  const values = items.map((i) => i.value);
  let lo = Math.min(0, ...values);
  let hi = Math.max(0, ...values);
  for (const r of spec.reference) {
    lo = Math.min(lo, r.value);
    hi = Math.max(hi, r.value);
  }
  const scale = nice(lo, hi, 4);
  const valueLabels = items.map((i) => formatValue(i.value, spec.format, { unit: false }));
  const maxValueW = Math.max(...valueLabels.map((l) => textWidth(l)));

  const barH = narrow ? 14 : 18;
  const rowH = narrow ? 42 : 30;
  const labelW = narrow ? 0 : Math.min(Math.max(...items.map((i) => textWidth(i.label))) + 12, width * 0.34);
  const top = spec.reference.length ? 22 : 6;
  const height = top + rowH * items.length + 4;
  const plotL = labelW;
  const plotR = width - maxValueW - 10;
  const x = linear(scale.min, scale.max, plotL, plotR);
  const x0 = x(0);

  const parts: string[] = [];
  // Linha de base no zero
  parts.push(`<line class="axis" x1="${r1(x0)}" x2="${r1(x0)}" y1="${top - 2}" y2="${height - 2}"/>`);

  const bands: { from: number; to: number; anchorX: number; anchorY: number }[] = [];
  items.forEach((it, i) => {
    const rowTop = top + i * rowH;
    const barY = narrow ? rowTop + 20 : rowTop + (rowH - barH) / 2;
    const xv = x(it.value);
    const left = Math.min(x0, xv);
    const w = Math.abs(xv - x0);
    const cls = anyHighlight && !it.highlight ? 'dim' : 's1';
    if (narrow) {
      parts.push(`<text class="cat" x="${r1(plotL)}" y="${rowTop + 13}">${esc(it.label)}</text>`);
    } else {
      parts.push(`<text class="cat" x="${r1(labelW - 10)}" y="${r1(barY + barH / 2)}" dy="0.32em" text-anchor="end">${esc(it.label)}</text>`);
    }
    parts.push(`<path class="bar h ${cls}${it.value < 0 ? ' rev' : ''}" data-i="${i}" d="${barPath(left, barY, Math.max(w, 1), barH, it.value >= 0 ? 'right' : 'left')}"/>`);
    const tipX = it.value >= 0 ? xv + 6 : xv - 6;
    parts.push(`<text class="value" x="${r1(tipX)}" y="${r1(barY + barH / 2)}" dy="0.32em" text-anchor="${it.value >= 0 ? 'start' : 'end'}">${esc(valueLabels[i])}</text>`);
    bands.push({ from: rowTop, to: rowTop + rowH, anchorX: xv, anchorY: barY });
  });

  for (const ref of spec.reference) {
    const px = r1(x(ref.value));
    parts.push(`<line class="ref" x1="${px}" x2="${px}" y1="${top - 4}" y2="${height - 2}"/>`);
    parts.push(`<text class="ref-label" x="${px}" y="${top - 8}" text-anchor="middle">${esc(ref.label)} ${esc(formatTick(ref.value, spec.format, scale.step))}</text>`);
  }

  const first = items[0];
  const aria = `${spec.title}. Gráfico de barras com ${items.length} itens; maior: ${first.label}, ${formatValue(first.value, spec.format)}.`;
  return {
    svg: svgOpen(width, height, aria, animate) + parts.join('') + '</svg>',
    height,
    interaction: {
      kind: 'band',
      orientation: 'horizontal',
      bands,
      title: (i) => items[i].label,
      rows: (i) => [
        {
          name: items[i].note ?? spec.subtitle ?? '',
          value: formatValue(items[i].value, spec.format),
          color: anyHighlight && !items[i].highlight ? 'dim' : 's1',
        },
      ],
    },
  };
}
