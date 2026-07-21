# Operações — FIFA World Cup 2026 Calendar

Guia de procedimentos para manter o calendário atualizado durante a Copa do Mundo.

> **🏆 Torneio encerrado em 19/07/2026 (Espanha 1×0 Argentina).** A automação
> (`update-scores.yml` e `update-knockout.yml`) está **desativada** — os `schedule:`
> foram comentados, mantendo `workflow_dispatch` para runs manuais. O `.ics`
> permanece publicado como **arquivo histórico** (104/104 jogos com placar) e o
> refresh foi ampliado de 6h para 7 dias. Assinaturas existentes continuam
> funcionando. Os procedimentos abaixo valem para uma futura edição — para
> reativar, descomente os `schedule:` e ajuste o campo de mês / gate de data.

## Pré-requisitos

1. Python 3.12+ instalado
2. Dependências: `pip install -r requirements.txt`
3. APIs de scores (ambas gratuitas, sem autenticação): ESPN (primária, ao vivo) e OpenLigaDB (fallback, consolidação)

## Arquitetura de dados

```
matches.json          ← Estático: schedule, estádios, TV, streaming
                         Fonte: fetch_matches.py (scrape Wikipedia)
                         Quando atualizar: só se FIFA mudar horários/estádios

scores.json           ← Dinâmico: apenas resultados dos jogos
                         Fonte: update_scores.py (ESPN + OpenLigaDB)
                         Quando atualizar: durante e após os jogos

generate_calendar.py  → Merge(matches + scores) → docs/fifa-worldcup-2026.ics
                         Rodar após qualquer atualização de scores
```

### Fontes de score (pacote `score_sources/`)

O `update_scores.py` é só orquestração + CLI; toda a lógica de API vive em módulos isolados:

```
score_sources/
├── __init__.py     ← ScoreRecord (shape normalizado comum a todas as fontes)
├── espn.py         ← FONTE PRIMÁRIA: placar ao vivo em tempo real
├── openligadb.py   ← FALLBACK + consolidação de resultados finais
└── matching.py     ← casa ScoreRecord → match_number por times + instante UTC
```

**Por que ESPN é primária:** na abertura, a OpenLigaDB ficou horas sem reportar placar ao vivo (`results: 0`) enquanto a ESPN já mostrava o jogo em tempo real com minuto. ESPN é uma API não-documentada (pode mudar sem aviso) — por isso a OpenLigaDB permanece como fallback automático: se a ESPN não retornar nada, o `--live` cai para a OpenLigaDB.

**Janela ESPN:** o scoreboard só retorna o dia atual; o `espn.fetch()` busca **hoje + ontem (UTC)** para capturar jogos noturnos das Américas que "viram" para o dia UTC seguinte e ainda estão ao vivo.

**Matching robusto (corrige bug de data):** matches.json guarda data/hora **locais** do estádio; as APIs reportam **UTC**. 36 dos 104 jogos caem num dia UTC diferente do dia local (jogos noturnos nas Américas). O matcher antigo comparava strings de data e falhava para esses 36. O `score_sources/matching.py` converte cada jogo para o **instante UTC** real e casa por times + instante, então a virada de dia não importa.

## Procedimentos diários (dias com jogos)

### 1. Durante os jogos — Atualização ao vivo

```bash
python update_scores.py --live
python generate_calendar.py
git add scores.json docs/fifa-worldcup-2026.ics && git commit -m "Live scores update" && git push
```

**Frequência:** a cada 20 minutos, o dia inteiro (24h), durante junho e julho.

> **Nota sobre o cron (`9,29,49 * * 6-7 *`):**
> - **Por que 24h e não só horário de jogo:** os jogos cobrem 12 timezones e dão kickoff em toda a faixa 16:00–04:00 UTC. Rodar o dia todo elimina qualquer furo de cobertura e evita conta de timezone (o cron do GitHub é sempre UTC). O check de data dentro do job ainda limita o trabalho real à janela do torneio (11/Jun–19/Jul).
> - **Por que 20 min e não 10:** o scheduler do GitHub Actions é best-effort e descarta a maioria das execuções de alta frequência — o histórico de `*/10` entregou intervalos reais de 70–160+ min, não 10. Pedir menos slots (3/h) melhora a taxa de sucesso individual sem aumentar o total diário (~72/dia vs ~78/dia antes).
> - **Minutos desalinhados (`9,29,49`)** em vez de `*/20`: minutos "redondos" (`:00`, `:20`, `:40`) sofrem mais congestionamento. **Não reverter para `*/20` nem para `*/10`.**
> - Para placar ao vivo crítico, prefira o disparo manual (`workflow_dispatch`).

**Janela de jogos típica:** primeiro kick-off até último jogo + 30min de margem (prorrogação/penalidades).

**O que faz:** busca placar ao vivo na ESPN (fallback OpenLigaDB) e atualiza scores.json com jogos em andamento e finalizados.

### 2. Após os jogos — Consolidação final

```bash
python update_scores.py --final
python generate_calendar.py
git add scores.json docs/fifa-worldcup-2026.ics && git commit -m "Final scores consolidation" && git push
```

**Frequência:** uma vez por dia, após todos os jogos do dia terminarem.

**O que faz:** busca os jogos finalizados na OpenLigaDB (boa para resultado final) e garante que o scores.json está completo e correto.

### 3. Verificação de status

```bash
python update_scores.py --status
```

Mostra: requests usados hoje, limite restante, último call, total de scores.

## API de Scores — OpenLigaDB

| Parâmetro | Valor |
|---|---|
| URL | https://api.openligadb.de |
| Autenticação | Nenhuma |
| Rate limit | Sem limite documentado |
| League shortcut | `wm26` |
| Custo | Gratuito (Open Database License) |

A cada chamada `--live`, o script faz 8 requests (um por matchday/fase). Sem limite diário, pode rodar quantas vezes precisar.

### Fallback manual

Se a API estiver fora do ar:
```bash
python update_scores.py --manual <match_number> <score_home> <score_away>
```

## Procedimentos excepcionais

### Atualização manual de score

Quando a API estiver indisponível ou o limite for atingido:

```bash
python update_scores.py --manual 7 2 0
python generate_calendar.py
```

O `match_number` corresponde ao campo no matches.json (ex: jogo #7 = Brasil vs Marrocos).

### FIFA alterou horários ou estádios

```bash
python fetch_matches.py
python generate_calendar.py
```

Isso re-scrape o Wikipedia e regenera o matches.json. Os scores não são afetados (arquivo separado).

### Adicionar Globo/SBT a jogos específicos

Editar matches.json diretamente, campo `tv`:
```json
"tv": "CazéTV / Globo"
```
Depois: `python generate_calendar.py`

### Atualização de times do mata-mata (knockout)

Conforme a Copa avança, os placeholders ("Winner Group C", "Runner-up Group F") são substituídos pelos times reais.

**Automático (GitHub Actions):**
Roda diariamente às 03h BRT a partir de 18/Jun (meio da fase de grupos — os primeiros classificados são definidos antes do fim dela). Busca times reais via OpenLigaDB + Wikipedia fallback.

> **Nota:** a OpenLigaDB ainda expõe placeholders de posição (`2A`, `1C`...) durante a fase de grupos, então quem resolve de fato é o fallback da Wikipedia, e só os lados já definidos (ex.: `Winner Group X`). Os adversários são preenchidos incrementalmente conforme os grupos terminam.

**Manual:**
```bash
python update_knockout.py          # Auto: tenta OpenLigaDB, fallback Wikipedia
python update_knockout.py --api    # Só OpenLigaDB
python update_knockout.py --wiki   # Só Wikipedia
python generate_calendar.py        # Regenera .ics
```

**Como funciona o matching:**
- Identifica o jogo correto por **data + horário** (não só data)
- Só atualiza se o nome atual for placeholder (`is_placeholder()`)
- Nunca sobrescreve um time real
- Nunca modifica jogos da fase de grupos
- Preserva todos os outros campos (stadium, tv, streaming)

### Plano B — Restaurar placeholders do mata-mata

Se a atualização automática de knockout corromper o `matches.json` (time errado no jogo errado):

```bash
# 1. Restaurar matches.json completo do Wikipedia (volta aos placeholders originais)
python fetch_matches.py
python generate_calendar.py

# 2. Verificar que os scores não foram afetados
cat scores.json

# 3. Commit e push
git add matches.json docs/fifa-worldcup-2026.ics
git commit -m "Restore matches.json from Wikipedia (rollback knockout update)"
git push
```

**Por que funciona:** `fetch_matches.py` regenera o matches.json completo a partir do Wikipedia, com os placeholders originais do mata-mata. O `scores.json` é um arquivo separado e não é afetado — os placares continuam intactos.

**Alternativa mais cirúrgica:** reverter só o último commit que modificou matches.json:
```bash
git log --oneline matches.json     # Ver histórico
git checkout HEAD~1 -- matches.json  # Reverter para versão anterior
python generate_calendar.py
```

## Automação (GitHub Actions)

Dois workflows rodam automaticamente durante a Copa — zero intervenção necessária:

| Workflow | Frequência | Período | O que faz |
|---|---|---|---|
| `update-scores.yml` | A cada 20min, 24h | 11/Jun – 19/Jul (check de data no job) | Busca scores live + finais, regenera .ics, commit/push |
| `update-knockout.yml` | 1x/dia (03h BRT) | 18/Jun – 19/Jul | Resolve placeholders do mata-mata, regenera .ics, commit/push |

**Características:**
- Ambos verificam se estão dentro da janela do torneio antes de executar (skip fora do período)
- Só fazem commit se houve mudança real nos dados
- Commits automáticos assinados como `github-actions[bot]`
- Podem ser disparados manualmente via "Run workflow" no GitHub

**Trigger manual (teste ou emergência):**
- GitHub → Actions → selecionar workflow → "Run workflow"
- O trigger manual **ignora a verificação de data** — executa a qualquer momento independente da janela do torneio

**Pré-requisito:** Settings → Actions → Workflow permissions → **"Read and write permissions"** (necessário para o auto-commit/push)

**Custo:** zero para repos públicos (GitHub Actions é gratuito).

## Sincronização dos celulares

O `.ics` tem `REFRESH-INTERVAL: PT6H` — os apps de calendário buscam atualizações a cada 6 horas automaticamente.

Para forçar atualização imediata:
- **iPhone:** remover e re-adicionar a subscription
- **Google Calendar:** sem controle manual, respeita o intervalo
- **Outlook:** Calendar → atualizar manualmente

## Testes

Rodam automaticamente antes de cada commit (pre-commit hook) e em cada push (GitHub Actions).

### Comandos de execução

```bash
# Todos os testes (152 testes: unit + security + E2E)
python -m pytest tests/ -v

# Só testes unitários (rápido, sem rede)
python -m pytest tests/ --ignore=tests/test_e2e_consistency.py

# Só testes de segurança
python -m pytest tests/test_security.py -v

# Só E2E (valida .ics contra Wikipedia, requer internet)
python -m pytest tests/test_e2e_consistency.py -v

# E2E com mais amostras (default: 5 jogos aleatórios)
E2E_SAMPLE_SIZE=15 python -m pytest tests/test_e2e_consistency.py -v

# Validação de segurança standalone (escaneia o .ics gerado)
python -m security.validator
```

### O que os testes garantem

**Unitários + Knockout (67 testes):**
- Integridade de matches.json (104 jogos, 6 por grupo, datas válidas, sem duplicatas)
- Formato correto dos títulos (com/sem placar, bandeiras, BRASIL uppercase)
- Merge scores não corrompe dados
- Normalização de nomes de times cobre variantes da API
- Match por data + times funciona em ambas as direções (home/away invertido)
- Knockout: nunca sobrescreve time real, matching por data + horário

**Segurança (37 testes):**
- URLs só de domínios allowlisted (rejeita qualquer outro)
- CRLF injection bloqueada
- Propriedades proibidas (VALARM, ATTACH, ATTENDEE, TZURL) detectadas e bloqueadas
- .ics gerado escaneado contra todos os vetores de ataque
- matches.json escaneado contra URLs escondidas e script tags

**E2E (8 testes):**
- Pega jogos aleatórios do .ics e valida contra Wikipedia
- Compara: datas, horários, estádios, nomes dos times, placares
- Detecta drift entre nossos dados e a fonte oficial
- Falha se o .ics tiver placar divergente do Wikipedia

## Segurança

### Validação de segurança

Toda geração do .ics passa por duas camadas:
1. **Sanitizer** (`security/sanitizer.py`) — filtra cada evento antes de incluir no .ics
2. **Validator** (`security/validator.py`) — escaneia o .ics final antes de publicar

```bash
# Validar o .ics manualmente
python -m security.validator

# Rodar testes de segurança
python -m pytest tests/test_security.py -v
```

### Adicionar novo domínio de streaming

Editar `security/allowed_domains.json` e adicionar o domínio exato:
```bash
# Exemplo: adicionar sportv.globo.com
# Editar security/allowed_domains.json → adicionar "sportv.globo.com"
python generate_calendar.py
python -m security.validator
```

### Branch protection (GitHub)

Configurado em Settings → Branches → main:
- PRs obrigatórios para merge
- Status checks (testes) devem passar
- Force push bloqueado

## Referências

| Recurso | URL |
|---|---|
| OpenLigaDB API | https://api.openligadb.de |
| Calendar URL (primary) | https://copa2026.trakas.com.br/fifa-worldcup-2026.ics |
| Calendar URL (fallback) | https://marceloingarano.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics |
| Landing page | https://copa2026.trakas.com.br/ |
| GitHub Pages (origin) | https://marceloingarano.github.io/fifa-worldcup-2026-calendar/ |
| Cloudflare dashboard | https://dash.cloudflare.com/ → Workers → copa2026-calendar → Analytics |
| Wikipedia schedule | https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_A |
