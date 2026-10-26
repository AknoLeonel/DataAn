import type { SingleChart } from '../types';
import { renderBar } from './bar';
import { renderColumn } from './column';
import type { Rendered } from './common';
import { renderLine } from './line';

export type { Interaction, Rendered, TipRow } from './common';

/** Largura usada no HTML gerado no build (mobile-first); o navegador redesenha na largura real. */
export const SSR_WIDTH = 380;

export function render(spec: SingleChart, width: number, compact = false): Rendered {
  const w = Math.max(240, Math.floor(width));
  switch (spec.type) {
    case 'line':
      return renderLine(spec, w, { compact });
    case 'bar':
      return renderBar(spec, w);
    case 'column':
      return renderColumn(spec, w);
  }
}
