// Identidade do site e URLs que respeitam o `base` (ex.: /DataAn/ se publicado em subpasta).

export const SITE = {
  name: 'DataAn',
  tagline: 'Dados públicos do Brasil, explicados em gráficos',
  description:
    'Plataforma aberta de visualização de dados públicos do Brasil: economia, saúde, meio ambiente, clima e demografia, atualizados automaticamente a partir de fontes oficiais.',
  repo: 'https://github.com/AknoLeonel/DataAn',
  locale: 'pt_BR',
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
