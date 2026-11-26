# Deployment Information

## Public URL

https://day14-agent-xchc.onrender.com

## Platform

Render Free. The Blueprint in `06-lab-complete/render.yaml` builds the Part 6 Dockerfile as the `day14-agent` Web Service. It connects to the Redis-compatible `day14-redis` Key Value instance over Render's private network. Both services are configured for Singapore and the Free plan. [Blueprint](06-lab-complete/render.yaml)

## Test Commands

Run in a Mac terminal. Enter the current Render key when prompted.

```zsh
BASE='https://day14-agent-xchc.onrender.com'
printf 'Render API key: '
read -rs AGENT_API_KEY
printf '\n'

printf 'GET /health          '
curl -sS --max-time 120 -o /dev/null -w '%{http_code}\n' "$BASE/health"

printf 'GET /ready           '
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

printf 'POST /ask without key '
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'

printf 'POST /ask with key    '
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'

unset AGENT_API_KEY
```

The HTTPS checks on 26 November 2026 returned the following responses.

| Request | Verified result |
|---|---|
| `GET /health` | `200 OK`, JSON status `ok` |
| `GET /ready` | `200 OK`, JSON status `ready` |
| `POST /ask` without a key | `401 Unauthorized` |
| `POST /ask` with a valid key | `200 OK`, JSON contains the question and an answer |

## Environment Variables

| Variable | Configuration |
|---|---|
| `AGENT_API_KEY` | Set in the Render dashboard |
| `REDIS_URL` | Private connection string from `day14-redis` |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` for mock LLM usage |
| `PORT` | Provided by Render |

## Screenshots

- [Blueprint resources](screenshots/dashboard.png)
- [Web service deployment](screenshots/running.png)
- [HTTP test results](screenshots/test.png)
