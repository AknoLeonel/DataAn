# Arquitetura: decisões e alternativas

## ADR-001: Site estático + pipeline agendado, sem backend

**Contexto.** Os dados públicos usados mudam no máximo uma vez por dia. O projeto
precisa ser barato (idealmente custo zero), seguro, rápido no celular e indexável.

**Decisão.** Um pipeline Python gera JSON/CSV validados durante o build e um site
estático (Astro) é construído a partir deles. Hospedagem: ver ADR-005.

**Consequências.**
- Custo zero, sem servidor para manter nem banco para proteger.
- O HTML já vem com os números e gráficos: bom para SEO, acessibilidade e conexões lentas.
- Os próprios arquivos de dados viram uma API pública (CDN, CORS liberado).
- Limite: atualização no máximo a cada execução agendada. Para dados em tempo real,
  seria preciso uma função serverless ou um backend (ver "Evolução").

**Alternativas descartadas.**
- *Streamlit/Dash*: rápido para protótipo, mas exige servidor sempre ligado, tem SEO
  fraco e carrega pesado no celular.
- *FastAPI + React SPA*: mais flexível, porém com custo, superfície de ataque e
  complexidade desnecessários para dados diários.

## ADR-002: Fallback pela versão publicada, sem commitar dados

Em vez de o robô fazer commit dos dados todos os dias (poluindo o histórico e gerando
conflitos), o pipeline baixa a versão já publicada (`--seed-from`) antes de rodar. Se
uma fonte falha, o arquivo anterior permanece e é marcado como `stale`. O histórico
de execuções fica em `status.json`.

## ADR-003: Gráficos em SVG próprio, sem biblioteca

Bibliotecas como ECharts ou Plotly somam centenas de KB e renderizam só no
navegador. Os renderizadores em `web/src/lib/charts` são funções puras: geram SVG no
build (funciona sem JS e é indexável) e o mesmo código redesenha no navegador na
largura real, com interação. O JS total da página de dataset fica em ~15 KB.

## ADR-004: Contrato de dados explícito

`models.py` (Pydantic, `extra="forbid"`) é a única definição do formato publicado; o
TypeScript espelha esses tipos. Isso permite que uma pessoa adicione um dataset sem
tocar no frontend e garante que nada malformado chegue ao site.

## ADR-005: Hospedagem na Vercel (serviço único), não no GitHub Pages

**Decisão.** Um projeto Vercel com um serviço `web` (Astro). O pipeline roda como
etapa do build desse serviço (`scripts/vercel-build.sh`); um workflow diário do
GitHub Actions chama um deploy hook para atualizar os dados.

**Por quê.** Cabeçalhos HTTP de segurança configuráveis, domínio na raiz, preview por
PR e repositório pode ser privado. O pipeline **não** é um serviço Vercel separado:
é um job em lote cujo resultado o site lê do disco no build. Um serviço Python na
Vercel exige um app ASGI/WSGI e bindings só funcionam em tempo de execução, então não
se aplicam a essa dependência de build.

**Quando separar em serviços.** Se surgir uma API dinâmica (ex.: filtros sob demanda,
FastAPI em `/api/`), ela vira um segundo serviço com rewrite próprio.

## Evolução prevista

1. Testes automatizados do pipeline com respostas gravadas das APIs (fixtures).
2. Mapas coropléticos por UF/município (GeoJSON simplificado do IBGE).
3. Páginas por cidade (dengue, ar, clima) geradas a partir do mesmo contrato.
4. Imagens Open Graph por dataset geradas no build.
5. Armazenamento histórico em Parquet (ex.: Cloudflare R2) quando o volume crescer.
6. Alertas (e-mail/Telegram) quando um indicador cruzar um limite, via GitHub Actions.
