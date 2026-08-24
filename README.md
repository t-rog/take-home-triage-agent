# Triage Agent

A prototype that classifies, enriches, and routes inbound client enquiries —
replacing the ~8 hours/week a junior analyst currently spends reading,
tagging, and routing them by hand. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for
the full build spec and the scope decisions behind it.

## Setup

```bash
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env to enable live classification
docker compose up --build
```

- API: http://localhost:5000
- Frontend: http://localhost:5173
- The database is seeded automatically on first boot (`SEED_ON_START=true` in
  `.env.example`) with 6 teams, an "Intake Desk" default team, and 18 sample
  enquiries — already classified with hand-written results, not a live model
  call, so the queue is populated within a couple of seconds even before you
  add an API key.

### What works without an API key

- The seeded queue and review/correct/retry flows — none of the
  seed data requires a model call.
- `backend/tests/test_router.py` and `backend/tests/test_classifier_schema.py`
  — pure functions and schema validation, no network or database access.
- `backend/tests/test_api.py` mocks the classifier, so it needs a reachable
  Postgres but not a key.

What doesn't work without a key: submitting a *new* enquiry through
`/submit` still runs the pipeline synchronously, so it will retry once and
then land in the Failed tab with a clean `error_message` — it fails
gracefully rather than crashing, which is itself one of the documented
failure modes (see below).

### Running the tests

```bash
docker compose exec api pytest -q
```

`test_router.py` and `test_classifier_schema.py` are safe to run any time.
`test_api.py` drops and recreates all tables against whatever `DATABASE_URL`
is configured — point it at a disposable database, not one with seed data
you want to keep. Running it against the compose `db` service will wipe the
seeded demo data; restart the `api`/`db` services (or `docker compose down -v
&& docker compose up`) afterward to get a fresh, seeded queue back.

### Running the eval script

```bash
docker compose exec api python -m evals.run_eval
```

Requires `ANTHROPIC_API_KEY`. Runs classification over
`backend/evals/golden.jsonl` (15 hand-labelled examples, including an
ambiguous case and an insufficient-information case) and prints service
line / complexity accuracy plus a confidence correct-vs-incorrect split.

## Architecture

```
 browser                      api (Flask)                  Postgres
┌─────────┐   POST /enquiries ┌──────────────────┐        ┌──────────┐
│ Submit  │ ────────────────► │ pipeline.process  │        │  team    │
│ Queue   │                   │  1. classify() ───┼──► Claude API    │
└─────────┘ ◄──────────────── │  2. router.route() │        │ enquiry  │
   Vite dev    GET /enquiries │  3. gate → status  │───────►│(2 tables)│
   server, proxies /api       │  4. insert row      │        └──────────┘
   to api:5000                └──────────────────┘
```

**Request walkthrough (`POST /api/enquiries`):** Pydantic validates the form
body → `classifier.classify()` calls Claude with a Pydantic output schema and
normalises the result → `router.route()` matches the classification against
an ordered list of rules in code and returns a team → the confidence gate
decides `routed` vs `needs_review` → one row is inserted into `enquiry` with
everything: the submission, the classification, and the routing outcome. The
response is the finished row, not a job id — the client waits for the real
result. If classification fails (after one retry), the row is still
inserted, with `status='failed'` and `error_message` set, so it's visible in
the Failed tab rather than only in the container logs.