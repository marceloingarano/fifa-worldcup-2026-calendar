# Operações — FIFA World Cup 2026 Calendar

Guia de procedimentos para manter o calendário atualizado durante a Copa do Mundo.

## Pré-requisitos

1. Python 3.12+ instalado
2. Dependências: `pip install -r requirements.txt`
3. API key configurada:
   ```bash
   echo "SUA_KEY" > .api_key
   ```
   Obtenha gratuitamente em: https://www.api-football.com/

## Arquitetura de dados

```
matches.json          ← Estático: schedule, estádios, TV, streaming
                         Fonte: fetch_matches.py (scrape Wikipedia)
                         Quando atualizar: só se FIFA mudar horários/estádios

scores.json           ← Dinâmico: apenas resultados dos jogos
                         Fonte: update_scores.py (API-Football)
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

**O que faz:** busca jogos com status 1H, HT, 2H, ET, P, FT, AET, PEN na API e atualiza scores.json.

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

## Limites da API

| Parâmetro | Valor |
|---|---|
| Limite diário (free tier) | 100 requests |
| Hard cap configurado | 85 requests/dia |
| Margem de segurança | 15 requests |
| Rate burst | 10 requests/min |
| Reset | Meia-noite UTC |

### Consumo estimado por cenário

| Cenário | Requests/dia |
|---|---|
| Dia com 4 jogos, janela 8h, a cada 10min | ~49 |
| Dia com jogos espalhados em 12h | ~73 |
| Dia sem jogos | 0 |
| Consolidação final | 1 |

### Se o limite for atingido

O script bloqueia automaticamente e mostra mensagem. Opções:
- Aguardar reset à meia-noite UTC
- Usar `--manual` para inserir scores manualmente:
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

```bash
python -m pytest tests/ -v
```

Roda automaticamente antes de cada commit (pre-commit hook) e em cada push (GitHub Actions).

### O que os testes garantem

- Integridade de matches.json (104 jogos, 6 por grupo, datas válidas, sem duplicatas)
- Formato correto dos títulos (com/sem placar, bandeiras, nomes PT-BR)
- Merge scores não corrompe dados
- Rate limit funciona corretamente
- Normalização de nomes de times cobre variantes da API
- Match por data + times funciona em ambas as direções (home/away invertido)

## Referências

| Recurso | URL |
|---|---|
| API-Football docs | https://www.api-football.com/documentation-v3 |
| API dashboard | https://dashboard.api-football.com/ |
| GitHub Pages | https://marceloingarano.github.io/fifa-worldcup-2026-calendar/ |
| Calendar URL | https://marceloingarano.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics |
| Wikipedia schedule | https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_A |
