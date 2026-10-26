// Formatação pt-BR compartilhada entre o build (SSR) e o navegador.
import type { Fmt } from './types';

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const MINUS = '−';
const cache = new Map<string, Intl.NumberFormat>();

function nf(opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = JSON.stringify(opts);
  let f = cache.get(key);
  if (!f) {
    f = new Intl.NumberFormat('pt-BR', opts);
    cache.set(key, f);
  }
  return f;
}

export interface FormatOptions {
  signed?: boolean;
  unit?: boolean;
  compact?: boolean;
  decimals?: number;
}

/** Formata um valor segundo o `Fmt` do contrato. */
export function formatValue(v: number, f: Fmt, o: FormatOptions = {}): string {
  const decimals = o.decimals ?? f.decimals;
  const compact = o.compact ?? f.compact;
  const abs = Math.abs(v);
  let body: string;
  if (f.kind === 'currency') {
    body = nf({ style: 'currency', currency: 'BRL', minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(abs);
  } else if (compact && abs >= 1000) {
    body = nf({ notation: 'compact', maximumFractionDigits: abs >= 100_000 && abs < 1_000_000 ? 0 : 1 }).format(abs);
  } else {
    body = nf({ minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: f.grouping !== false }).format(abs);
  }
  if (f.kind === 'percent') body += '%';
  const showUnit = (o.unit ?? true) && f.unit;
  if (showUnit) body += `${f.kind === 'percent' ? ' ' : ' '}${f.unit}`;
  const isZero = Number(abs.toFixed(decimals)) === 0;
  if (v < 0 && !isZero) return MINUS + body;
  if (o.signed && v > 0 && !isZero) return '+' + body;
  return body;
}

/** Rótulo curto para eixos: compacto, sem unidade. */
export function formatTick(v: number, f: Fmt, step: number): string {
  const decimals = step >= 1 || step === 0 ? 0 : Math.min(3, Math.ceil(-Math.log10(step)));
  if (f.kind === 'currency') {
    return 'R$ ' + nf({ minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(v).replace('-', MINUS);
  }
  const abs = Math.abs(v);
  const body =
    abs >= 1000
      ? nf({ notation: 'compact', maximumFractionDigits: 1 }).format(abs)
      : nf({ minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(abs);
  const sign = v < 0 ? MINUS : '';
  return sign + body + (f.kind === 'percent' ? '%' : '');
}

export function parseDate(s: string): number {
  const [y, m, d] = s.split('-').map(Number);
  return Date.UTC(y, (m || 1) - 1, d || 1);
}

/** "2026-10-18" -> "18 out 2026" (ou "out 2026" para séries mensais). */
export function formatDate(s: string, kind: 'date' | 'week' | 'month' | 'year' = 'date'): string {
  const dt = new Date(parseDate(s));
  const y = dt.getUTCFullYear();
  const m = MESES[dt.getUTCMonth()];
  if (kind === 'year') return String(y);
  if (kind === 'month') return `${m} ${y}`;
  const d = dt.getUTCDate();
  return kind === 'week' ? `sem. de ${d} ${m} ${y}` : `${d} ${m} ${y}`;
}

export function monthShort(monthIndex: number): string {
  return MESES[monthIndex];
}

/** Data/hora ISO (UTC) -> "26/10/2026, 06:17" no horário de Brasília. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'America/Sao_Paulo',
  }).format(new Date(iso));
}

export function formatInt(v: number): string {
  return nf({ maximumFractionDigits: 0 }).format(v);
}

/** "há 3 horas" relativo a `now`. */
export function relativeTime(iso: string, now = Date.now()): string {
  const diff = (new Date(iso).getTime() - now) / 1000;
  const rtf = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, secs] of units) {
    if (Math.abs(diff) >= secs) return rtf.format(Math.round(diff / secs), unit);
  }
  return 'agora';
}
