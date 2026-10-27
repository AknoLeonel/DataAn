import type { SingleChart } from '../types';
import { renderBar } from './bar';
import { renderColumn } from './column';
import type { Focus, Rendered } from './common';
import { renderLine } from './line';

export type { Focus, Interaction, Rendered, TipRow } from './common';

/** Largura usada no HTML gerado no build (mobile-first); o navegador redesenha na largura real. */
export const SSR_WIDTH = 380;

export interface RenderOptions {
  compact?: boolean;
  /** Animação de entrada (só no navegador, ao entrar na tela). */
  animate?: boolean;
  focus?: Focus | null;
}

export function render(spec: SingleChart, width: number, opts: RenderOptions = {}): Rendered {
  const w = Math.max(240, Math.floor(width));
  switch (spec.type) {
    case 'line':
      return renderLine(spec, w, { compact: opts.compact, animate: opts.animate, focus: opts.focus });
    case 'bar':
      return renderBar(spec, w, opts.animate);
    case 'column':
      return renderColumn(spec, w, opts.animate);
  }
}

const YEAR = 365.25 * 86_400_000;

/** Recorta as séries de um gráfico de linha para os últimos `years` anos (null = tudo). */
export function sliceYears<T extends SingleChart>(spec: T, years: number | null): T {
  if (spec.type !== 'line' || years === null) return spec;
  const last = Math.max(...spec.series.flatMap((s) => s.points.map(([d]) => Date.parse(d))));
  const from = last - years * YEAR;
  const keep = (d: string) => Date.parse(d) >= from;
  const fromIso = new Date(from).toISOString().slice(0, 10);
  return {
    ...spec,
    series: spec.series.map((s) => {
      const points = s.points.filter(([d]) => keep(d));
      // Em degrau (ex.: Selic), o valor vigente no início do recorte precisa aparecer.
      const before = s.points.filter(([d]) => !keep(d)).pop();
      if (spec.step && before && (!points.length || points[0][0] !== fromIso)) points.unshift([fromIso, before[1]]);
      return { ...s, points, band: s.band?.filter(([d]) => keep(d)) };
    }),
  } as T;
}

/** Períodos que fazem sentido para a extensão da série (em anos). */
export function rangeOptions(spec: SingleChart): { label: string; years: number | null }[] {
  if (spec.type !== 'line' || spec.x_kind === 'week') return [];
  const ts = spec.series.flatMap((s) => s.points.map(([d]) => Date.parse(d)));
  const span = (Math.max(...ts) - Math.min(...ts)) / YEAR;
  if (span < 2.5) return [];
  const opts: { label: string; years: number | null }[] = [{ label: '1A', years: 1 }];
  if (span > 6) opts.push({ label: '5A', years: 5 });
  if (span > 12) opts.push({ label: '10A', years: 10 });
  opts.push({ label: 'Máx', years: null });
  return opts;
}
