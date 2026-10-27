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
    `<path class="spark-line" pathLength="1" d="${d}"/><circle class="spark-dot" cx="${lx}" cy="${ly}" r="3"/></svg>`
  );
}

/** Mini colunas (ex.: variação mensal): zero como base, o período mais recente em destaque. */
export function minibars(values: number[], label: string, width = 112, height = 32): string {
  const vals = values.filter((v) => Number.isFinite(v));
  if (!vals.length) return '';
  const lo = Math.min(0, ...vals);
  const hi = Math.max(0, ...vals);
  const y = linear(lo, hi === lo ? lo + 1 : hi, height - 2, 2);
  const band = width / vals.length;
  const bw = Math.max(2, Math.min(10, band - 3));
  const y0 = y(0);
  const bars = vals
    .map((v, i) => {
      const yv = y(v);
      const top = Math.min(y0, yv);
      const h = Math.max(1.5, Math.abs(yv - y0));
      const cls = i === vals.length - 1 ? (v >= 0 ? 'pos' : 'neg') : 'mute';
      return `<rect class="mini-bar ${cls}${v < 0 ? ' rev' : ''}" x="${r1(i * band + (band - bw) / 2)}" y="${r1(top)}" width="${r1(bw)}" height="${r1(h)}" rx="1.5"/>`;
    })
    .join('');
  return (
    `<svg class="spark" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(label)}">` +
    `<line class="spark-zero" x1="0" x2="${width}" y1="${r1(y0)}" y2="${r1(y0)}"/>${bars}</svg>`
  );
}

export interface BulletInput {
  value: number;
  min: number;
  max: number;
  lo?: number;
  hi?: number;
  mark?: number;
  label?: string;
}

/** Régua de contexto: onde o valor cai entre min e max, com a faixa/marca de referência. */
export function bullet(b: BulletInput, fmt: (v: number) => string, aria: string, width = 300): string {
  const x = (v: number) => r1(Math.max(0, Math.min(width, ((v - b.min) / (b.max - b.min)) * width)));
  const parts: string[] = [`<rect class="bullet-track" x="0" y="18" width="${width}" height="10" rx="5"/>`];
  if (b.lo !== undefined && b.hi !== undefined) {
    parts.push(`<rect class="bullet-band" x="${x(b.lo)}" y="18" width="${r1(x(b.hi) - x(b.lo))}" height="10"/>`);
    parts.push(`<text class="bullet-tick" x="${x(b.lo)}" y="46" text-anchor="middle">${esc(fmt(b.lo))}</text>`);
    parts.push(`<text class="bullet-tick" x="${x(b.hi)}" y="46" text-anchor="middle">${esc(fmt(b.hi))}</text>`);
  }
  if (b.mark !== undefined) {
    const mx = x(b.mark);
    parts.push(`<line class="bullet-mark" x1="${mx}" x2="${mx}" y1="13" y2="33"/>`);
    parts.push(`<text class="bullet-mark-label" x="${mx}" y="9" text-anchor="middle">${esc(`${b.label ?? 'referência'} ${fmt(b.mark)}`)}</text>`);
  }
  const vx = x(b.value);
  parts.push(`<rect class="bullet-value" x="0" y="20" width="${vx}" height="6" rx="3"/>`);
  parts.push(`<circle class="bullet-dot" cx="${vx}" cy="23" r="7"/>`);
  return `<svg class="bullet" viewBox="0 0 ${width} 52" width="100%" role="img" aria-label="${esc(aria)}">${parts.join('')}</svg>`;
}
