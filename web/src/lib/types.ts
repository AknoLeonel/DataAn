// Espelho do contrato em pipelines/dataan/models.py. Mudou lá, muda aqui.

export type StatusLevel = 'good' | 'warning' | 'serious' | 'critical';

export interface Fmt {
  kind: 'number' | 'percent' | 'currency';
  decimals: number;
  unit?: string;
  compact: boolean;
  grouping?: boolean;
}

export interface Source {
  name: string;
  url: string;
  license?: string;
}

export interface RefLine {
  value: number;
  label: string;
}

export interface Series {
  key: string;
  name: string;
  points: [string, number | null][];
  style: 'solid' | 'dashed';
  band?: [string, number, number][];
  color: number;
}

export interface Badge {
  status: StatusLevel;
  label: string;
}

export interface LineChart {
  type: 'line';
  id: string;
  title: string;
  subtitle?: string;
  format: Fmt;
  series: Series[];
  x_kind: 'date' | 'week' | 'month' | 'year';
  step: boolean;
  y_zero: boolean;
  reference: RefLine[];
  marker?: [string, string];
  badge?: Badge;
  note?: string;
}

export interface BarItem {
  label: string;
  value: number;
  highlight: boolean;
  note?: string;
}

export interface BarChart {
  type: 'bar';
  id: string;
  title: string;
  subtitle?: string;
  format: Fmt;
  items: BarItem[];
  reference: RefLine[];
  highlight_label?: string;
  note?: string;
}

export interface ColumnChart {
  type: 'column';
  id: string;
  title: string;
  subtitle?: string;
  format: Fmt;
  items: BarItem[];
  diverging: boolean;
  note?: string;
}

export interface GridChart {
  type: 'grid';
  id: string;
  title: string;
  subtitle?: string;
  charts: LineChart[];
  note?: string;
}

export type Chart = LineChart | BarChart | ColumnChart | GridChart;
export type SingleChart = LineChart | BarChart | ColumnChart;

export interface Delta {
  value: number;
  format: Fmt;
  period: string;
  good: 'up' | 'down' | 'neutral';
}

export interface KpiRange {
  min: number;
  max: number;
  lo?: number;
  hi?: number;
  mark?: number;
  label?: string;
}

export interface Kpi {
  label: string;
  value: number;
  format: Fmt;
  delta?: Delta;
  spark?: number[];
  spark_kind?: 'line' | 'bars';
  as_of?: string;
  status?: StatusLevel;
  status_label?: string;
  range?: KpiRange;
  dots?: boolean[];
  dot_labels?: string[];
  dot_legend?: [string, string];
}

export interface Highlight {
  text: string;
  chart: string;
  start: string;
  end: string;
  at: string;
  label: string;
}

export interface ModelInfo {
  name: string;
  target: string;
  horizon: string;
  baseline: string;
  mae: number;
  mae_baseline: number;
  skill: number;
  notes?: string;
}

export interface Column {
  name: string;
  description: string;
}

export interface Dataset {
  schema_version: number;
  slug: string;
  title: string;
  summary: string;
  description: string;
  category: string;
  tags: string[];
  sources: Source[];
  frequency: string;
  coverage?: string;
  updated_at: string;
  data_until?: string;
  kpis: Kpi[];
  charts: Chart[];
  insights: string[];
  highlights?: Highlight[];
  methodology: string[];
  model?: ModelInfo;
  columns: Column[];
  rows: number;
}

export interface Category {
  slug: string;
  name: string;
  description: string;
  count: number;
}

export interface CatalogEntry {
  slug: string;
  title: string;
  summary: string;
  category: string;
  tags: string[];
  frequency: string;
  updated_at: string;
  data_until?: string;
  stale: boolean;
  sources: string[];
  headline?: Kpi;
}

export interface Catalog {
  schema_version: number;
  generated_at: string;
  categories: Category[];
  datasets: CatalogEntry[];
}

export interface DatasetStatus {
  slug: string;
  title: string;
  ok: boolean;
  stale: boolean;
  error?: string;
  duration_s: number;
  rows: number;
  updated_at?: string;
  data_until?: string;
}

export interface RunSummary {
  at: string;
  ok: number;
  failed: number;
  results: Record<string, boolean>;
}

export interface Status {
  schema_version: number;
  generated_at: string;
  run_url?: string;
  duration_s: number;
  datasets: DatasetStatus[];
  history: RunSummary[];
}
