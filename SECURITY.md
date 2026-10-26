# Política de segurança

## Como reportar uma vulnerabilidade

Não abra issue pública. Use **Security → Report a vulnerability** neste repositório
(GitHub Private Vulnerability Reporting). Respondemos em até 7 dias.

## Modelo de ameaça e defesas

| Superfície | Defesa |
|---|---|
| Site | Estático, sem backend, sem formulários, sem cookies. CSP restrita com hashes gerados pelo Astro (`script-src 'self'`, sem `unsafe-inline`), `object-src 'none'`, `base-uri 'self'`. |
| Conteúdo vindo das fontes | Todo texto de dados é escapado no SVG e inserido com `textContent` no navegador (nunca `innerHTML` com dado bruto). JSON embutido tem `<` escapado. |
| Pipeline | Dados validados por contrato (Pydantic, `extra="forbid"`) antes de publicar; slugs restritos a `[a-z0-9-]` (sem path traversal); limite de tamanho de resposta e timeouts. |
| Supply chain | Dependências com faixas de versão, `package-lock.json` versionado, Dependabot semanal para pip, npm e Actions. |
| GitHub Actions | `permissions: contents: read` por padrão; só o job de deploy recebe `pages: write` e `id-token: write`; `persist-credentials: false`; nenhum segredo necessário. |

Cabeçalhos HTTP extras (HSTS, `frame-ancestors`, `Permissions-Policy`) estão em
`web/public/_headers` e são aplicados automaticamente em hosts compatíveis (Cloudflare
Pages, Netlify). O GitHub Pages não permite cabeçalhos customizados.
