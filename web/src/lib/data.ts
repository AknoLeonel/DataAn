// Leitura dos arquivos gerados pelo pipeline (public/data) durante o build.
import fs from 'node:fs';
import path from 'node:path';
import type { Catalog, Dataset, Status } from './types';

const DATA_DIR = path.resolve(process.cwd(), 'public', 'data');

function readJson<T>(rel: string): T | null {
  const file = path.join(DATA_DIR, rel);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf-8')) as T;
}

let catalog: Catalog | null | undefined;
export function getCatalog(): Catalog | null {
  if (catalog === undefined) catalog = readJson<Catalog>('catalog.json');
  return catalog;
}

const datasets = new Map<string, Dataset>();
export function getDataset(slug: string): Dataset {
  let ds = datasets.get(slug);
  if (!ds) {
    const loaded = readJson<Dataset>(`datasets/${slug}.json`);
    if (!loaded) throw new Error(`Dataset ausente: ${slug}`);
    ds = loaded;
    datasets.set(slug, ds);
  }
  return ds;
}

export function getStatus(): Status | null {
  return readJson<Status>('status.json');
}

export function categoryName(slug: string): string {
  return getCatalog()?.categories.find((c) => c.slug === slug)?.name ?? slug;
}
