import { esc, linear, r1 } from './common';

/** Sparkline de tendência para os KPIs: traço discreto e o período atual em destaque. */
export function sparkline(values: number[], label: string, width = 112, height = 32): string {
  const vals = values.filter((v) => Number.isFinite(v));
  if (vals.length < 2) return '';
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const pad = 4;
  const x = linear(0, vals.length - 1, pad, width - pad);
  const y = linear(min, max === min ? min + 1 : max, height - pad, pad);
  const d = vals.map((v, i) => `${i ? 'L' : 'M'}${r1(x(i))},${r1(y(v))}`).join('');
  const lx = r1(x(vals.length - 1));
  const ly = r1(y(vals[vals.length - 1]));
  return (
    `<svg class="spark" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(label)}">` +
    `<path class="spark-line" d="${d}"/><circle class="spark-dot" cx="${lx}" cy="${ly}" r="3"/></svg>`
  );
}
