# Observatório FIRST Brasil — FRC e FTC

O site estático tem uma página inicial em `/`, com dois ambientes independentes:

- `/frc/`: base FRC existente, sem etapas mundiais; dados em `web/data/`.
- `/ftc/`: FTCScout, equipes brasileiras, temporadas 2022–23 a 2025–26; dados em `web/ftc/`.

No FTC, 2023 é o ano de encerramento da temporada 2022–23 (season=2022 na API). Os índices não são comparáveis entre programas. O FTC considera Qualifier, SuperQualifier, Championship, FIRSTChampionship e Premier. Scrimmage, OffSeason, LeagueMeet e demais categorias não autorizadas são excluídas.

## Atualizar FTC

```sh
make ftc-data          # busca com cache e recalcula
python3 -m data.ftc.fetch --refresh  # renova as consultas
make ftc-build         # recalcula sem rede
make test
make serve
```

Coleta em `data/ftc/fetch.py`; normalização e score em `data/ftc/build.py`; pesos independentes em `data/ftc/config.py`. Requer Python 3 e curl. A API GraphQL pública não precisa de chave. O cache é separado, em `data/ftc/raw/`; respostas com erros interrompem a coleta em vez de substituir a base por dados parciais.

O FTC usa o percentil do OPR sem penalidades dentro de cada evento, média por temporada; prêmios de equipe ponderados por tipo e colocação; melhor playoff; aproveitamento das classificatórias. Não usa EPA. O índice FTC v2 usa faixas de progressão: seletivas 0–39, Nacional brasileiro 40–69, Mundial/Premier 70–100. O maior nível efetivamente alcançado na temporada determina a faixa; desempenho ponderado determina a posição dentro dela. Eventos têm pesos 1×/2×/3×, aplicados a OPR, prêmios, playoffs e aproveitamento. Mundial e Premier estão no mesmo nível. Uma simples inscrição futura não promove a equipe. Os pesos e faixas ficam em data/ftc/config.py. Títulos de competição não somam como prêmio julgado, evitando dupla contagem. Consulte a metodologia dentro do ambiente FTC para as limitações do percentil e da pontuação de double elimination.

A coleta inicial encontrou 144 cadastros brasileiros; 137 tiveram resultados nas categorias consideradas. Foram consultados 89 eventos/divisões. OPR disponível nas 333 temporadas-equipe. As demais equipes não recebem score artificial por falta de participação válida.

Para publicar ambos os ambientes, envie **toda a pasta `web/`**, com suas subpastas. Não publique `.env` nem `data/` do pipeline. O botão Início permite trocar de programa.

---

## Documentação do pipeline FRC

Regra atual: o score-base exclui o Mundial, portanto uma etapa mais difícil nunca derruba a temporada. Disputar o Mundial soma 2 pontos; performance, prêmios, playoff e aproveitamento mundiais somam até mais 8. Prêmios mundiais têm multiplicador 2×. O score final é limitado a 100. Estados mostram cada equipe e as medianas estadual e brasileira.

# FDI — Fator de Desenvolvimento · FRC Brasil

Sistema para medir e comparar a evolução das equipes brasileiras de FRC (First
Robotics Competition), de 2023 em diante. Combina métricas de performance (EPA do
Statbotics, OPR do TBA) com prêmios conquistados (ponderados por importância) e
profundidade nos playoffs, num índice único de 0 a 100 por temporada.

```
data/        pipeline em Python (só stdlib) que busca as APIs e gera o JSON
web/         site estático (HTML + JS, sem build) que consome web/data/data.json
```

## O que dá pra fazer no site

| Tela | Para quê |
|---|---|
| **Visão geral** | Ranking de todas as equipes numa temporada, Δ vs. ano anterior, filtro por estado, busca, ordenação. |
| **Equipe** | Ficha de uma equipe: score ao longo do tempo (por evento e por temporada), composição do score, prêmios, ranking nacional e estadual. |
| **Estado** | Evolução do score de cada equipe, mediana estadual e mediana brasileira, comparação entre estados, lista das equipes, ranking de estados. |
| **Comparar** | Sobrepõe o score de várias equipes no tempo e quebra os componentes lado a lado. |
| **Metodologia** | Pesos e regras usados no cálculo (lidos de `web/data/config.json`). |

## Como rodar

Pré-requisitos: **Python 3.9+** e uma **chave da API do The Blue Alliance**
(gratuita em <https://www.thebluealliance.com/account>). O Statbotics não precisa
de chave.

```bash
# 1. configure a chave
cp .env.example .env        # e edite, ou:  export TBA_AUTH_KEY=xxxxx

# 2. gere os dados (primeira vez demora ~3-6 min; depois usa cache em data/raw)
make data                   # -> web/data/data.json

# 3. suba o site
make serve                  # http://localhost:8765
```

Sem internet / para um passeio rápido:

```bash
make fixtures && make serve   # usa data/fixtures/sample_data.json
```

### Outros comandos

```bash
make data-fresh   # ignora o cache e rebusca tudo
make test         # testes das funções de scoring
make clean        # apaga o cache de APIs
```

## Como o score é calculado

Para cada equipe e cada temporada (2023–2026), quatro componentes normalizados em
0–1 formam o score-base. Depois, o Mundial soma um bônus exclusivamente positivo:

| Componente | Peso | Fonte | Resumo |
|---|---:|---|---|
| Performance | 52,63% | Statbotics EPA norm. + OPR | EPA normalizado (comparável entre jogos) mapeado de 1250 a 2000; mistura 15% do percentil de OPR. Cai para OPR se não houver EPA. |
| Prêmios | 21,05% | TBA | Cada prêmio do score-base vale conforme um tier (S/A/B/C); prêmios mundiais entram no bônus com multiplicador 2×. |
| Playoff | 18,95% | TBA | Melhor resultado de mata-mata na temporada, com bônus pela função na aliança: capitão +0,10; pick 1 +0,06; pick 2 +0,03; pick 3/reserva +0,01. A função vem do campo `alliance.pick` do status da equipe no evento. |
| Aproveitamento | 7,37% | Statbotics / TBA | Taxa de vitórias na classificatória. |

O Mundial soma 2 pontos por participação efetiva e até 8 pontos pelos mesmos
quatro componentes calculados apenas nos eventos mundiais. Assim, um desempenho
abaixo do esperado no Mundial nunca reduz o score-base. O resultado final tem teto 100.
Dentro do Mundial, a profundidade no playoff define faixas que não se sobrepõem:
campeão, finalista de divisão, semifinal, rodadas intermediárias, playoff inicial
e não classificado. Performance, prêmios e aproveitamento ordenam apenas dentro
da faixa. Portanto, um finalista de divisão sempre fica acima de uma equipe que
foi menos longe, mesmo que esta tenha rankeado melhor nas classificatórias.


Tudo é calibrável em **`data/config.py`** (pesos `W`, tiers de prêmios, faixas de
EPA, valores de playoff). Depois de editar, rode `make data` de novo — os valores
usados ficam registrados em `web/data/config.json` e aparecem na tela Metodologia.

### Tiers de prêmios (padrão)

- **S (1.00)** — Impact/Chairman's, Vencedor da etapa
- **A (0.70)** — Engineering Inspiration, Finalista, Impact Finalist, Campeão de distrito
- **B (0.45)** — Woodie Flowers/Leadership, Autonomous, Innovation in Control, Creativity, Engineering Excellence, Industrial Design, Quality
- **C (0.25)** — Rookie All-Star, Judges, Spirit, Imagery, Safety, Website, Volunteer, etc.

O mapeamento é por `award_type` do TBA, com fallback por texto do nome do prêmio.

## Dados

- **Descoberta de equipes**: união dos times inscritos nos eventos-âncora
  (`data/config.py → ANCHOR_EVENTS`): `2023brbr`, `2024brbr`, `2025brba`,
  `2025brsp`, `2026brba`, `2026brsp`. Times de fora do Brasil são descartados
  pelo país no TBA.
- **Eventos considerados por temporada**: regionais e demais eventos oficiais fora
  do Mundial formam o score-base. Divisões do Campeonato Mundial geram somente o
  bônus positivo. O evento "guarda-chuva" (ex.: `2025cmptx`) não gera ponto no
  gráfico quando não há participação em partidas, mas seus prêmios podem entrar
  no bônus mundial.
- **Cache**: toda resposta de API 200 é gravada em `data/raw/`. Reexecuções são
  rápidas. Use `make data-fresh` para forçar atualização (ex.: depois de um
  evento novo).
- **Avatares**: a API oficial da FIRST fornece PNGs codificados por temporada em
  `/:season/avatars`. Defina `FIRST_API_USERNAME` e `FIRST_API_AUTH_KEY` no `.env`;
  o build salva o avatar mais recente em `web/assets/avatars/`. Sem essas
  credenciais, o campo fica vazio e o restante do painel continua funcionando.

### Limitações conhecidas

- Se a API do Statbotics estiver instável, o pipeline segue sem o EPA: o
  componente de performance passa a usar só o percentil de OPR do TBA, e o
  aproveitamento é agregado das classificatórias no TBA. Para preencher só o EPA
  depois (sem rebuscar todo o TBA):

  ```bash
  rm -f data/raw/v3_team_year_* data/raw/v3_team_event_* data/raw/v3_teams*
  make data
  ```
- Equipes brasileiras que nunca disputaram um dos 6 eventos-âncora não entram na
  base. Para incluí-las, acrescente eventos em `ANCHOR_EVENTS` ou reative a
  descoberta via Statbotics (`data/build.py → discover_team_keys`).
- 2023 usa bracket de eliminação simples em alguns eventos; o mapeamento de
  profundidade de playoff trata os dois formatos, mas "rodada inicial" agrupa
  casos distintos.

## Deploy

O site é 100% estático. Basta publicar a pasta `web/` (com `web/data/data.json`
já gerado e versionado):

- **GitHub Pages**: aponte para `/web` na branch, ou mova o conteúdo para a raiz.
- **Vercel/Netlify**: diretório de publicação = `web`, sem build.

## Estrutura

```
data/
  config.py       pesos, tiers, constantes  (edite aqui)
  scoring.py      funções puras do índice     (testado)
  apiclient.py    HTTP + cache em disco (stdlib)
  statbotics.py   cliente Statbotics v3 (+ disjuntor se a API cair)
  tba.py          cliente The Blue Alliance v3
  build.py        orquestra tudo -> web/data/data.json
  test_scoring.py testes (python3 -m unittest)
  fixtures/       dataset de exemplo
web/
  index.html
  css/styles.css
  js/{app,lib,charts}.js
  data/{data.json,config.json}   (gerados por make data)
```


### Importação alternativa pelo site Statbotics

`python3 -m data.import_statbotics_site` baixa os arquivos públicos compactados usados pelo próprio site, sem consultar a API REST. Os snapshots em `data/raw/statbotics_site/` preservam URL de origem e data da coleta. Depois execute `python3 -m data.build --cached-only` para recalcular com esses snapshots e o cache TBA existente, sem rede.

A coleta de setembro de 2026 recuperou EPA para as 137 temporadas-equipe e 211 participações em eventos de 2025–2026 presentes no sistema. Os arquivos de 2023–2024 retornaram 404; esses anos continuam com OPR. A interface apresenta a cobertura por ano. EPA normalizado (`epa.norm`) e EPA sem unidade (`epa.unitless`) são campos distintos; o score continua usando o normalizado.


### Correções de classificação FTC e catálogo

`data/ftc/config.py` registra exceções explícitas por temporada/código, preservando o tipo original da fonte:
- `2024/BRCUS`: Scrimmage na fonte; considerado Qualifier por indicação do responsável. Ano de encerramento 2025.
- `2025/BRPIQ`: Qualifier na fonte; considerado Championship de nível Nacional (2×). Ano de encerramento 2026.

A coleta cruza participações das equipes com o catálogo brasileiro de eventos, em vez de depender só das participações. A tela Eventos mostra todas as temporadas, as correções e registros sem partidas. Outros Scrimmages e OffSeasons continuam excluídos. Na consulta atual, a temporada 2022–23 não tem qualifiers cadastrados; isso é uma limitação da fonte, não evidência de inexistência de seletivas.

Correção validada: `2023/BRBHS` (SESI MG CENTERSTAGE) é seletiva da temporada 2023–24, ano 2024 no painel. Os demais Scrimmages da lista auditada permanecem excluídos, conforme confirmação do responsável.
