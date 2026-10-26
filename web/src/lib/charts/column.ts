// Colunas verticais ao longo do tempo; modo divergente colore acima/abaixo de zero.
import { formatTick, formatValue } from '../format';
import type { ColumnChart } from '../types';
import { barPath, clamp, esc, linear, nice, r1, svgOpen, textWidth, type Rendered } from './common';

export function renderColumn(spec: ColumnChart, width: number): Rendered {
  const items = spec.items;
  const height = Math.round(clamp(width * 0.5, 210, 300));
  const values = items.map((i) => i.value);
  const scale = nice(Math.min(0, ...values), Math.max(0, ...values), height > 240 ? 5 : 4);
  const tickLabels = scale.ticks.map((t) => formatTick(t, spec.format, scale.step));
  const m = { top: 18, right: 8, bottom: 24, left: Math.max(...tickLabels.map((l) => textWidth(l, 11))) + 10 };
  const plotL = m.left, plotR = width - m.right, plotT = m.top, plotB = height - m.bottom;
  const y = linear(scale.min, scale.max, plotB, plotT);
  const y0 = y(0);
  const band = (plotR - plotL) / items.length;
  const gap = Math.max(2, band * 0.25);
  const barW = clamp(band - gap, 1, 24);

  const parts: string[] = [];
  scale.ticks.forEach((t, i) => {
    const py = r1(y(t));
    parts.push(`<line class="${t === 0 ? 'axis' : 'grid'}" x1="${plotL}" x2="${r1(plotR)}" y1="${py}" y2="${py}"/>`);
    parts.push(`<text class="tick" x="${plotL - 6}" y="${py}" dy="0.32em" text-anchor="end">${esc(tickLabels[i])}</text>`);
  });

  // Rotular só a última coluna e o maior valor absoluto (nunca todas).
  let extreme = 0;
  items.forEach((it, i) => {
    if (Math.abs(it.value) > Math.abs(items[extreme].value)) extreme = i;
  });
  const labeled = new Set([items.length - 1]);
  const lastW = textWidth(formatValue(items[items.length - 1].value, spec.format, { unit: false, signed: spec.diverging }));
  if ((items.length - 1 - extreme) * band > lastW + 12) labeled.add(extreme);

  // Rótulos do eixo X: da direita para a esquerda, pulando os que colidiriam.
  const xLabels: string[] = [];
  let nextRight = Infinity;
  const every = Math.max(1, Math.ceil(items.length / Math.max(2, Math.floor((plotR - plotL) / 56))));
  for (let i = items.length - 1; i >= 0; i -= every) {
    const cx = plotL + band * i + band / 2;
    const w = textWidth(items[i].label, 11);
    let left = cx - w / 2;
    let anchor = 'middle';
    if (cx + w / 2 > width) {
      left = cx - w;
      anchor = 'end';
    } else if (left < 0) {
      left = cx;
      anchor = 'start';
    }
    if (left + w + 8 > nextRight || left < 0) continue;
    nextRight = left;
    xLabels.push(`<text class="tick" x="${r1(cx)}" y="${height - 6}" text-anchor="${anchor}">${esc(items[i].label)}</text>`);
  }
  parts.push(...xLabels);
  const bands: { from: number; to: number; anchorX: number; anchorY: number }[] = [];
  const cls = (v: number) => (spec.diverging ? (v >= 0 ? 'pos' : 'neg') : 's1');

  items.forEach((it, i) => {
    const cx = plotL + band * i + band / 2;
    const yv = y(it.value);
    const top = Math.min(y0, yv);
    const h = Math.max(Math.abs(yv - y0), 1);
    parts.push(`<path class="bar ${cls(it.value)}" data-i="${i}" d="${barPath(cx - barW / 2, top, barW, h, it.value >= 0 ? 'top' : 'bottom')}"/>`);
    if (labeled.has(i)) {
      const ly = it.value >= 0 ? yv - 6 : yv + 14;
      const label = formatValue(it.value, spec.format, { unit: false, signed: spec.diverging });
      const lw = textWidth(label);
      const anchor = cx - lw / 2 < plotL ? 'start' : cx + lw / 2 > width ? 'end' : 'middle';
      parts.push(`<text class="value" x="${r1(cx)}" y="${r1(ly)}" text-anchor="${anchor}">${esc(label)}</text>`);
    }
    bands.push({ from: plotL + band * i, to: plotL + band * (i + 1), anchorX: cx, anchorY: top });
  });

  const last = items[items.length - 1];
  const aria = `${spec.title}. Gráfico de colunas com ${items.length} períodos; último (${last.label}): ${formatValue(last.value, spec.format)}.`;
  return {
    svg: svgOpen(width, height, aria) + parts.join('') + '</svg>',
    height,
    interaction: {
      kind: 'band',
      orientation: 'vertical',
      bands,
      title: (i) => items[i].label,
      rows: (i) => [
        {
          name: spec.subtitle ?? '',
          value: formatValue(items[i].value, spec.format, { signed: spec.diverging }),
          color: cls(items[i].value),
        },
      ],
    },
  };
}
