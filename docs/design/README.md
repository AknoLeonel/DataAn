# Design: redesign "observatório" com motion

Fonte do redesign aprovado em 27/10/2026, implementado no site neste mesmo PR.

- **Canvas interativo:** https://claude.ai/artifact/T4mJutFxq4ZuwVqUDhMPda (privado; peça acesso ao dono do repositório).
- **Arquivos aqui:** `canvas.json` (disposição das telas) e um `.dc.html` por tela. Eles dependem do
  runtime do canvas (`support.js`), então não abrem sozinhos no navegador: servem de referência e
  histórico do design.

| Tela | Arquivo | O que define |
|---|---|---|
| Início | `Main.dc.html` | Chip "ao vivo", pulso com contagem até o valor, destaque com períodos, cards por área, fluxo animado |
| Página de dados (IPCA) | `Dataset.dc.html` | Régua da meta, pontos mês a mês, destaques ligados a trechos do gráfico |
| Status | `Status.dc.html` | Anel de saúde, linha do tempo da execução, erros em português simples (dados reais de 27/10) |
| Mobile (dengue) | `Mobile.dc.html` | Troca de capital, arraste no gráfico, nível de alerta com ícone + texto |
| Sistema de motion | `Motion.dc.html` | Durações, curvas e regras de "reduzir movimento" |

## Como o design virou código

| Design | Implementação |
|---|---|
| Paleta escura e tipografia Geist | `web/src/styles/global.css` (tokens) e `@fontsource-variable/geist` (fontes servidas pelo próprio site) |
| Motion (tempos e curvas) | variáveis `--t-*` e `--ease-*` em `global.css`; `web/src/scripts/motion.ts` |
| Linha que se desenha, barras que crescem | classe `anim` nos SVGs de `web/src/lib/charts/*` (só na primeira renderização, ao entrar na tela) |
| Destaques ligados ao gráfico | `Dataset.highlights` no pipeline (`models.py`) + `Chart.astro` + `scripts/charts.ts` |
| Régua da meta, pontos, mini colunas | `Kpi.range`, `Kpi.dots`, `Kpi.spark_kind` + `lib/charts/sparkline.ts` |
| Status com anel e linha do tempo | `web/src/pages/status.astro` + `web/src/lib/status.ts` |

Regras que valem para qualquer tela nova: nenhum número sem contexto (período, fonte, "dados até"),
texto e gráfico sempre derivados da mesma série, status sempre com ícone + texto, e tudo legível com
"reduzir movimento" ativado.
