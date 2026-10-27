// Leitura do status do pipeline para o site (página de status, chip "ao vivo", cards indisponíveis).
import type { DatasetStatus, Status } from './types';

export interface Health {
  total: number;
  ok: number;
  stale: DatasetStatus[];
  missing: DatasetStatus[];
  level: 'good' | 'warning' | 'critical';
}

export function health(status: Status | null): Health | null {
  if (!status) return null;
  const ds = status.datasets;
  const stale = ds.filter((d) => !d.ok && d.stale);
  const missing = ds.filter((d) => !d.ok && !d.stale);
  return {
    total: ds.length,
    ok: ds.filter((d) => d.ok).length,
    stale,
    missing,
    level: missing.length ? 'critical' : stale.length ? 'warning' : 'good',
  };
}

/** Explica o erro técnico em português simples. */
export function explainError(error: string | undefined): string {
  if (!error) return 'A coleta falhou.';
  const e = error.toLowerCase();
  const attempts = /(\d+)\s*tentativas/.exec(e)?.[1];
  if (e.includes('timed out') || e.includes('timeout')) return 'A fonte não respondeu a tempo.';
  if (e.includes('resposta inesperada')) return 'A fonte respondeu num formato inesperado.';
  if (e.includes('403') || e.includes('forbidden')) return 'A fonte recusou o acesso.';
  if (e.includes('404')) return 'O endereço da fonte não foi encontrado.';
  if (e.includes('dataqualityerror') || e.includes('mínimo') || e.includes('dias (máx')) return 'Os dados chegaram, mas não passaram nas checagens de qualidade.';
  return attempts ? `A coleta falhou após ${attempts} tentativas.` : 'A coleta falhou.';
}

/** Próxima execução agendada (todo dia às 09:17 UTC = 06:17 em Brasília). */
export function nextRun(fromIso: string): Date {
  const from = new Date(fromIso);
  const next = new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate(), 9, 17));
  if (next <= from) next.setUTCDate(next.getUTCDate() + 1);
  return next;
}
