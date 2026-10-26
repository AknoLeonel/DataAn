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
| GitHub Actions | CI com `permissions: contents: read` e `persist-credentials: false`; o agendamento diário roda com `permissions: {}` e usa um único secret (`VERCEL_DEPLOY_HOOK`), que só dispara um novo deploy. |

Cabeçalhos HTTP (HSTS, `X-Frame-Options`, `frame-ancestors`, `Permissions-Policy`,
`X-Content-Type-Options`, COOP) são aplicados pela Vercel a partir do `vercel.json`.
Previews de PR recebem `noindex` automaticamente da Vercel.
