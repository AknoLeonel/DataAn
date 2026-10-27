# Cópias versionadas (fallback)

Último recurso do pipeline: se a fonte de um conjunto falhar **e** ainda não existir
versão publicada no site, o runner usa `<slug>.json` / `<slug>.csv` daqui. O conjunto
aparece no site como **desatualizado**, com a data real dos dados.

Serve para dados que mudam pouco e cuja fonte bloqueia acessos de fora do Brasil
(caso do IBGE no build da Vercel, que roda nos EUA). Para atualizar, rode num
computador no Brasil:

```bash
.venv/bin/python -m dataan run --only populacao-uf
.venv/bin/python -m dataan snapshot populacao-uf
git add pipelines/snapshots/ && git commit -m "Atualiza cópia da população"
```
