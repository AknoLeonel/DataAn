// Identidade do site e URLs que respeitam o `base` (ex.: /DataAn/ se publicado em subpasta).

export const SITE = {
  name: 'DataAn',
  tagline: 'Dados públicos do Brasil, explicados em gráficos',
  description:
    'Plataforma aberta de visualização de dados públicos do Brasil: economia, saúde, meio ambiente, clima e demografia, atualizados automaticamente a partir de fontes oficiais.',
  repo: 'https://github.com/AknoLeonel/DataAn',
  locale: 'pt_BR',
  /** Códigos de verificação do Google Search Console (públicos por natureza: vão numa meta tag). */
  googleVerification: ['6o1N63MQlI27sN5KOYBcLrShKxn_CQOt473L8iYVfoo'],
};

const BASE = import.meta.env.BASE_URL.replace(/\/+$/, '');

/** Caminho interno com o prefixo do base: url('/dados/selic/') -> '/DataAn/dados/selic/'. */
export function url(p = '/'): string {
  const clean = p.startsWith('/') ? p : `/${p}`;
  return `${BASE}${clean}`;
}

/** URL absoluta (para canonical, Open Graph e JSON-LD). */
export function absolute(p = '/'): string {
  const site = (import.meta.env.SITE ?? 'http://localhost:4321').replace(/\/+$/, '');
  return `${site}${url(p)}`;
}

export const AUTHOR = {
  name: 'Akno Leonel',
  role: 'Cientista de Dados',
  linkedin: 'https://www.linkedin.com/in/aknoleonel/',
  github: 'https://github.com/AknoLeonel',
  portfolio: 'https://aknoleonel.github.io/',
};

/** Notebooks reproduzíveis do repositório, por conjunto de dados. */
export const NOTEBOOKS: Record<string, string> = {
  'estudo-dengue-clima': 'estudo-dengue-clima.ipynb',
};
export const API_NOTEBOOK = 'api-dataan.ipynb';

export function colabUrl(notebook: string): string {
  return `https://colab.research.google.com/github/AknoLeonel/DataAn/blob/main/notebooks/${notebook}`;
}

export function notebookUrl(notebook: string): string {
  return `${SITE.repo}/blob/main/notebooks/${notebook}`;
}
