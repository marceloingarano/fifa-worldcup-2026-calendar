# Operações — FIFA World Cup 2026 Calendar

Guia de procedimentos para manter o calendário atualizado durante a Copa do Mundo.

## Pré-requisitos

1. Python 3.12+ instalado
2. Dependências: `pip install -r requirements.txt`
3. API de scores: OpenLigaDB (gratuita, sem autenticação, sem rate limit)

## Arquitetura de dados

```
matches.json          ← Estático: schedule, estádios, TV, streaming
                         Fonte: fetch_matches.py (scrape Wikipedia)
                         Quando atualizar: só se FIFA mudar horários/estádios

scores.json           ← Dinâmico: apenas resultados dos jogos
                         Fonte: update_scores.py (OpenLigaDB)
                         Quando atualizar: durante e após os jogos

generate_calendar.py  → Merge(matches + scores) → docs/fifa-worldcup-2026.ics
                         Rodar após qualquer atualização de scores
```

## Procedimentos diários (dias com jogos)

### 1. Durante os jogos — Atualização ao vivo

```bash
python update_scores.py --live
python generate_calendar.py
git add scores.json docs/fifa-worldcup-2026.ics && git commit -m "Live scores update" && git push
```

**Frequência:** a cada 10 minutos durante a janela de jogos.

**Janela de jogos típica:** primeiro kick-off até último jogo + 30min de margem (prorrogação/penalidades).

**O que faz:** busca todos os jogos na OpenLigaDB e atualiza scores.json com jogos em andamento e finalizados.

### 2. Após os jogos — Consolidação final

```bash
python update_scores.py --final
python generate_calendar.py
git add scores.json docs/fifa-worldcup-2026.ics && git commit -m "Final scores consolidation" && git push
```

**Frequência:** uma vez por dia, após todos os jogos do dia terminarem.

**O que faz:** busca todos os jogos finalizados (FT, AET, PEN) e garante que o scores.json está completo e correto.

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

### Novo time classificado (knockout)

Os placeholders ("Winner Group C", etc.) serão resolvidos automaticamente pela API quando os jogos acontecerem. Alternativamente, editar matches.json manualmente.

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
# Todos os testes (unit + E2E)
python -m pytest tests/ -v

# Só testes unitários (rápido, sem rede)
python -m pytest tests/ --ignore=tests/test_e2e_consistency.py

# Só E2E (valida .ics contra Wikipedia, requer internet)
python -m pytest tests/test_e2e_consistency.py -v

# E2E com mais amostras (default: 5 jogos aleatórios)
E2E_SAMPLE_SIZE=15 python -m pytest tests/test_e2e_consistency.py -v
```

### O que os testes garantem

**Unitários (94 testes):**
- Integridade de matches.json (104 jogos, 6 por grupo, datas válidas, sem duplicatas)
- Formato correto dos títulos (com/sem placar, bandeiras, nomes PT-BR)
- Merge scores não corrompe dados
- Rate limit funciona corretamente
- Normalização de nomes de times cobre variantes da API
- Match por data + times funciona em ambas as direções (home/away invertido)

**E2E (8 testes):**
- Pega jogos aleatórios do .ics e valida contra Wikipedia
- Compara: datas, horários, estádios, nomes dos times, placares
- Detecta drift entre nossos dados e a fonte oficial
- Falha se o .ics tiver placar divergente do Wikipedia

## Referências

| Recurso | URL |
|---|---|
| OpenLigaDB API | https://api.openligadb.de |
| GitHub Pages | https://marceloingarano.github.io/fifa-worldcup-2026-calendar/ |
| Calendar URL | https://marceloingarano.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics |
| Wikipedia schedule | https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_A |
