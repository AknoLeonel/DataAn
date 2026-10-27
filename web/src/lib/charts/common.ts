// Primitivas dos gráficos: escalas, ticks, medição aproximada de texto e escape.
// Tudo puro (sem DOM), para rodar igual no build e no navegador.
import { monthShort } from '../format';

export const FONT = 12;
export const DAY = 86_400_000;

export const esc = (s: string): string =>
  s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

/** Largura aproximada (px) de um texto na fonte de sistema, suficiente para layout. */
export function textWidth(s: string, size = FONT): number {
  let w = 0;
  for (const ch of s) {
    if (/[0-9]/.test(ch)) w += 0.58;
    else if (/[ .,:;|il1'!]/.test(ch)) w += 0.3;
    else if (/[A-ZMW%mw]/.test(ch)) w += 0.75;
    else w += 0.55;
  }
  return w * size;
}

export const clamp = (v: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, v));
export const r1 = (v: number): number => Math.round(v * 10) / 10;

export function linear(d0: number, d1: number, r0: number, r1_: number): (v: number) => number {
  const k = d1 === d0 ? 0 : (r1_ - r0) / (d1 - d0);
  return (v) => r0 + (v - d0) * k;
}

export interface NiceScale {
  min: number;
  max: number;
  step: number;
  ticks: number[];
}

function niceStep(span: number, count: number): number {
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  return step * mag;
}

/** Domínio "redondo" com ~count marcas, como no d3.nice(). */
export function nice(min: number, max: number, count = 5): NiceScale {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1, step: 1, ticks: [0, 1] };
  if (min === max) {
    const pad = Math.abs(min) * 0.1 || 1;
    min -= pad;
    max += pad;
  }
  const step = niceStep(max - min, count);
  const lo = Math.floor(min / step + 1e-9) * step;
  const hi = Math.ceil(max / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toPrecision(12)));
  return { min: lo, max: hi, step, ticks };
}

export interface TimeTick {
  t: number;
  label: string;
}

/** Marcas de tempo legíveis: anos, meses ou dias, conforme o intervalo e o espaço disponível. */
export function timeTicks(t0: number, t1: number, maxTicks: number): TimeTick[] {
  const spanDays = (t1 - t0) / DAY;
  const start = new Date(t0);
  const out: TimeTick[] = [];
  if (spanDays > 365 * 2.5) {
    const y0 = start.getUTCFullYear();
    const y1 = new Date(t1).getUTCFullYear();
    const steps = [1, 2, 5, 10, 20, 50];
    const step = steps.find((s) => (y1 - y0) / s <= maxTicks) ?? 50;
    for (let y = Math.ceil(y0 / step) * step; y <= y1; y += step) {
      const t = Date.UTC(y, 0, 1);
      if (t >= t0 && t <= t1) out.push({ t, label: String(y) });
    }
    return out;
  }
  if (spanDays > 75) {
    const months = spanDays / 30.4;
    const steps = [1, 2, 3, 6, 12];
    const step = steps.find((s) => months / s <= maxTicks) ?? 12;
    let y = start.getUTCFullYear();
    let m = start.getUTCMonth();
    for (let i = 0; i < 400; i++) {
      const t = Date.UTC(y, m, 1);
      if (t > t1) break;
      if (t >= t0 && m % step === 0) {
        const showYear = m === 0 || out.length === 0 || step >= 6;
        out.push({ t, label: showYear ? `${monthShort(m)}/${String(y).slice(2)}` : monthShort(m) });
      }
      m += 1;
      if (m === 12) {
        m = 0;
        y += 1;
      }
    }
    return out;
  }
  const steps = [1, 2, 7, 14, 28];
  const step = steps.find((s) => spanDays / s <= maxTicks) ?? 28;
  const first = Math.ceil(t0 / DAY) * DAY;
  for (let t = first; t <= t1; t += step * DAY) {
    const d = new Date(t);
    out.push({ t, label: `${d.getUTCDate()} ${monthShort(d.getUTCMonth())}` });
  }
  return out;
}

/** Retângulo com cantos arredondados só na ponta dos dados (base reta), como pede o guia de marcas. */
export function barPath(
  x: number,
  y: number,
  w: number,
  h: number,
  end: 'top' | 'bottom' | 'left' | 'right',
  radius = 4,
): string {
  if (w <= 0 || h <= 0) return '';
  const r = Math.min(radius, end === 'top' || end === 'bottom' ? w / 2 : h / 2, end === 'top' || end === 'bottom' ? h : w);
  const X = r1(x), Y = r1(y), W = r1(w), H = r1(h), R = r1(r);
  switch (end) {
    case 'top':
      return `M${X},${Y + H}V${Y + R}Q${X},${Y} ${X + R},${Y}H${X + W - R}Q${X + W},${Y} ${X + W},${Y + R}V${Y + H}Z`;
    case 'bottom':
      return `M${X},${Y}H${X + W}V${Y + H - R}Q${X + W},${Y + H} ${X + W - R},${Y + H}H${X + R}Q${X},${Y + H} ${X},${Y + H - R}Z`;
    case 'right':
      return `M${X},${Y}H${X + W - R}Q${X + W},${Y} ${X + W},${Y + R}V${Y + H - R}Q${X + W},${Y + H} ${X + W - R},${Y + H}H${X}Z`;
    case 'left':
      return `M${X + W},${Y}V${Y + H}H${X + R}Q${X},${Y + H} ${X},${Y + H - R}V${Y + R}Q${X},${Y} ${X + R},${Y}Z`;
  }
}

// --- Modelo de interação devolvido pelos renderizadores (usado só no navegador) ---

export interface TipRow {
  name: string;
  value: string;
  color: string; // classe da série: s1..s8, pos, neg, dim
  dashed?: boolean;
}

export interface XInteraction {
  kind: 'x';
  plot: { left: number; right: number; top: number; bottom: number };
  xs: number[];
  title(i: number): string;
  rows(i: number): TipRow[];
  dots(i: number): { y: number; color: string }[];
}

export interface BandInteraction {
  kind: 'band';
  orientation: 'vertical' | 'horizontal';
  bands: { from: number; to: number; anchorX: number; anchorY: number }[];
  title(i: number): string;
  rows(i: number): TipRow[];
}

export type Interaction = XInteraction | BandInteraction;

export interface Rendered {
  svg: string;
  height: number;
  interaction: Interaction;
}

export function svgOpen(width: number, height: number, label: string, animate = false): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(label)}" class="viz-svg${animate ? ' anim' : ''}">`;
}

/** Trecho de um gráfico de linha em destaque (vem de `Dataset.highlights`). */
export interface Focus {
  start: string;
  end: string;
  at: string;
  label: string;
}
