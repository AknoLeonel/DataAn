# Divulgação

Um achado por post. Os números mudam a cada atualização, então os campos entre `[colchetes]`
são preenchidos na hora de publicar, copiando da página indicada (o site é a fonte).

## Roteiro

| Semana | Post | De onde vêm os números |
|---|---|---|
| 1 | O clima ajuda a prever a dengue? | [/dados/estudo-dengue-clima/](https://dataan.vercel.app/dados/estudo-dengue-clima/) |
| 2 | Quantos meses a inflação passou do teto | [/dados/ipca/](https://dataan.vercel.app/dados/ipca/) |
| 3 | Como construí um pipeline que não cai quando o governo cai | [/status/](https://dataan.vercel.app/status/) |
| 4 | Juro real: o quanto a Selic rende acima da inflação | [/dados/selic/](https://dataan.vercel.app/dados/selic/) |
| 5 | A capital que mais esquentou desde 1981 | [/dados/temperatura-capitais/](https://dataan.vercel.app/dados/temperatura-capitais/) |

Formato que funciona no LinkedIn: gancho em uma linha, 3 a 5 linhas com o achado, uma imagem
(print do gráfico do site) e o link **no primeiro comentário**, não no texto.

## Post 1 — estudo de caso

> Testei se o clima ajuda a prever a dengue. A resposta foi **[sim / não de forma consistente]**.
>
> Peguei 5 anos de casos semanais de 6 capitais (InfoDengue/Fiocruz) e comparei 5 modelos, cada
> um prevendo 4 semanas à frente só com o passado, em 52 semanas de teste.
>
> • O melhor modelo errou **[62]%** menos que "repetir a última semana".
> • Colocar temperatura e umidade melhorou a previsão em **[1] de 6** capitais.
> • O critério para trocar de modelo foi definido antes de ver os resultados.
>
> O estudo se recalcula sozinho toda semana, e o notebook roda no Colab em um clique.
>
> #CienciaDeDados #Python #SeriesTemporais #DadosAbertos

Primeiro comentário: link do estudo + link do notebook no Colab.

## Post 3 — engenharia

> APIs do governo caem, respondem 200 com erro dentro e bloqueiam servidores fora do Brasil.
> Construí o pipeline do DataAn para que nada disso derrube o site:
>
> • retentativa com backoff e servidor alternativo (IBGE: servicodados → apisidra);
> • contrato de dados (pydantic) antes de publicar qualquer número;
> • se a fonte falha, fica no ar a última versão válida, marcada como desatualizada;
> • página de status pública com o histórico de cada execução.
>
> Hoje: **[9/9]** fontes ok.

## Domínio próprio

1. Compre o domínio (ex.: Registro.br para `.com.br`, ou Cloudflare/Namecheap).
2. Vercel → projeto → **Settings → Domains → Add** e siga os registros DNS indicados
   (`A` para o domínio raiz, `CNAME` para `www`).
3. Vercel → **Settings → Environment Variables**: crie `SITE_URL=https://seu-dominio` em
   Production. Ela define o canonical, o sitemap e o Open Graph (`web/astro.config.mjs`).
4. Faça um novo deploy e confira o `canonical` em qualquer página.
5. Atualize os links do README e deste arquivo.

## Medir sem rastrear

O site usa o **Vercel Web Analytics** (contagens agregadas, sem cookies, servido pelo próprio
domínio). Para ativar: Vercel → projeto → **Analytics → Enable**. O script só entra no build da
Vercel e pode ser desligado com `DATAAN_ANALYTICS=0`. Acompanhe as páginas mais vistas e de onde
vêm as visitas a cada post.
