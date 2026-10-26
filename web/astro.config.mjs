// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// URL canônica: SITE_URL explícita (domínio próprio) > domínio de produção da Vercel > local.
// Previews da Vercel também apontam o canonical para produção (evita conteúdo duplicado).
const vercelProd = process.env.VERCEL_PROJECT_PRODUCTION_URL;
const site = process.env.SITE_URL || (vercelProd ? `https://${vercelProd}` : 'http://localhost:4321');
const base = process.env.BASE_PATH || '/';

export default defineConfig({
  site,
  base,
  trailingSlash: 'always',
  output: 'static',
  build: {
    format: 'directory',
    inlineStylesheets: 'never',
  },
  integrations: [sitemap({ filter: (page) => !page.includes('/404') })],
  security: {
    csp: {
      directives: [
        "default-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        'upgrade-insecure-requests',
      ],
    },
  },
  markdown: { syntaxHighlight: false },
  devToolbar: { enabled: false },
});
