# Intake Triage Agent — Build Specification (MVP)

> Revised scope. The original draft of this spec built a small production
> system (background worker, append-only audit tables, calibration eval
> harness, 5-page frontend). The brief asks for "a functioning prototype of
> the core classification/routing logic — the most basic version that covers
> the vital functionality." This revision cuts everything that doesn't serve
> that sentence, while keeping Postgres as explicitly requested. A metrics
> dashboard was built and later removed for the same reason — it wasn't part
> of "the core classification/routing logic" and only added surface area
> unrelated to the brief.

---

## 1. Context

A professional services firm receives 40–60 inbound enquiries per week through
a web form. Each has a free-text description, plus industry, company size,
and urgency. A junior analyst currently reads every one, tags it by service
line, estimates complexity, and routes it to a team lead — roughly 8 hours a
week, and error-prone.

Build a working prototype that classifies, enriches, and routes these
automatically, with a human in the loop where the model is unsure.

---

## 2. Non-goals — do not build these

- Authentication, user accounts, roles, or sessions
- A message broker, task queue, or background worker thread — classification
  runs synchronously in the request. At 40–60/week there is no throughput
  problem to solve.
- Alembic or any migration tool — three tables, created once via
  `metadata.create_all()` or a single `init.sql`
- Append-only / audit-history tables (`classification`, `agent_run`,
  `review`, `enquiry_history`) — corrections overwrite the enquiry row in
  place. See §8 for the one exception (`was_corrected`).
- A `routing_rule` database table — rules are a Python list of dicts,
  version-controlled with the code. See §12.
- WebSockets, SSE, or aggressive polling — the frontend fetches on load and
  on a manual refresh / simple interval
- Multi-tenancy, soft deletes
- Admin CRUD screens for teams or rules
- Kubernetes, CI pipelines, cloud deployment, Terraform
- Streaming responses from the model
- A secondary/tertiary service line taxonomy beyond §7
- Prompt-chaining, agentic loops, multi-turn conversations — one stateless
  call per enquiry
- Retrieval, embeddings, a vector store
- Keyboard-driven review UI, a separate detail page, a separate review page —
  folded into the queue view (§15)
- Confusion matrices, confidence-calibration buckets, margin-calibration
  tables, model-comparison tooling — the eval script (§14) reports plain
  accuracy against a small golden set, nothing more

If a feature is not described in this document, it is out of scope.

---

## 3. Locked decisions

**3.1 — Claude classifies. A rules list routes.**
The model returns `service_line`, `complexity`, `confidence`, `rationale`,
and extracted signals. It never chooses a team. Team assignment is a
deterministic, ordered match over a Python list of rules (§12). Routing must
be testable with no API key and no database.

**3.2 — Classification runs synchronously in the request.**
`POST /api/enquiries` validates the form, calls the classifier, computes
routing, and inserts one row with the final `status`. If the model call
fails after one retry, the row is still inserted, with `status='failed'` and
`error_message` set — failure must be visible in the UI, not just the logs.

**3.3 — No history tables. One correction flag.**
Human corrections overwrite `service_line` / `complexity` / `team_id` on the
enquiry row directly. If the correction changes any of those from the
model's original values, set `was_corrected = true` — a full audit trail
isn't required by the brief and isn't built.

---

## 4. Stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Vite, plain CSS or Tailwind |
| Backend | Python 3.12 + Flask |
| DB access | SQLAlchemy 2.x, `metadata.create_all()` — no Alembic |
| Validation | Pydantic v2 |
| DB | Postgres 16 |
| Model API | `anthropic` Python SDK |
| Orchestration | Docker Compose (`db`, `api`, `web`) |
| Tests | pytest — router and schema validation covered |

---

## 5. Repository layout

```
triage-agent/
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py          # create_app()
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py            # enquiry, team (§8)
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── enquiries.py
│   │   │   └── reference.py     # teams, service lines
│   │   ├── services/
│   │   │   ├── classifier.py    # only file that imports anthropic (§10)
│   │   │   ├── router.py        # rules list + matching (§12)
│   │   │   └── pipeline.py      # classify → route → gate, one function
│   │   └── seed.py              # teams + sample enquiries (§9)
│   ├── evals/
│   │   ├── golden.jsonl         # ~15 hand-labelled examples
│   │   └── run_eval.py
│   └── tests/
│       ├── test_router.py
│       ├── test_classifier_schema.py
│       └── test_api.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── main.tsx
        ├── api/client.ts
        ├── types.ts              # mirrors backend enums
        └── pages/
            ├── SubmitPage.tsx
            └── QueuePage.tsx     # list + inline review/correct
```

---

## 6. Docker Compose

Three services, same as before, minus migration/seed complexity:

- `db` — `postgres:16`, named volume, healthcheck on `pg_isready`.
- `api` — depends on `db` healthy. On start: `metadata.create_all()`, seed if
  `SEED_ON_START=true`, serve. No worker thread — classification happens
  inline per request.
- `web` — Vite dev server, proxies `/api` to `api:5000`.

`docker compose up` must produce a working, seeded application with no
further commands.

`.env.example`: `ANTHROPIC_API_KEY=`, `DATABASE_URL`, `MODEL_ID`,
`CONFIDENCE_THRESHOLD`, `SEED_ON_START`. Never commit `.env`.

---

## 7. Enums

```python
INDUSTRY      = financial_services | healthcare | manufacturing | retail |
                public_sector | technology | professional_services | other
COMPANY_SIZE  = size_1_50 | size_51_250 | size_251_1000 | size_1000_plus
URGENCY       = exploring | within_month | immediate
SERVICE_LINE  = data_analytics | risk_compliance | operations |
                technology_transformation | people_change | finance_advisory
COMPLEXITY    = simple | moderate | complex
STATUS        = routed | needs_review | failed | closed
FLAG          = insufficient_information | out_of_scope | spam |
                multiple_service_lines
```

`STATUS` has no `received`/`processing` — since classification is
synchronous, a row is only ever inserted once the outcome is known.

---

## 8. Data model — two tables

**`team`**
`id`, `name`, `service_line` (enum, nullable for the default team),
`lead_name`, `lead_email`, `is_default` (bool).
Exactly one row has `is_default = true`.

**`enquiry`**
`id`, `submitted_at`, `contact_name`, `contact_email`, `company_name`,
`industry` (enum), `industry_other` (text, nullable), `company_size` (enum),
`urgency` (enum), `description` (text),
`service_line` (enum, nullable), `complexity` (enum, nullable),
`confidence` (numeric, nullable), `rationale` (text, nullable),
`runner_up_service_line` (enum, nullable),
`runner_up_confidence` (numeric, nullable),
`key_signals` (jsonb, nullable — array of strings),
`flags` (jsonb, nullable — array of enum strings),
`status` (enum), `team_id` FK (nullable — null only when `status='failed'`),
`matched_rule` (text, nullable — the rule's `name`, for display; see §12),
`error_message` (text, nullable),
`reviewed` (bool, default false — set true by any `/review` call, approve or
correct; distinguishes "auto-routed, never touched" from "reviewed and
confirmed" for the auto-route/override rate split),
`was_corrected` (bool, default false),
`created_at`, `updated_at`.

Index on `(status, created_at)` for the queue view.

`service_line`/`complexity` nullable so `insufficient_information` is stored
honestly rather than forced into a guess. No `attempts` column — one retry
happens inline within the request and isn't persisted as state.

---

## 9. Seed data

`seed.py`, idempotent:

- **6 teams**, one per service line, plus a 7th default "Intake Desk" team
  (`service_line = NULL`, `is_default = true`).
- **15–20 sample enquiries**, inserted already classified and routed (call
  the real pipeline at seed time, or hand-write plausible results) so the
  queue is populated immediately — include 2–3 spanning
  service lines, 1 near-empty description, 1 spam/out-of-scope, 1 with
  `industry='other'`.

---

## 10. Claude integration — `services/classifier.py`

Unchanged from the original spec — this is the part the brief actually
tests, and it was already well-scoped.

### 10.1 Model
Default `MODEL_ID=claude-sonnet-5`.

### 10.2 Structured output
Use `client.messages.parse()` with a Pydantic `TriageResult` model via
`output_format`, not forced tool-use.

```python
class TriageResult(BaseModel):
    service_line: str | None
    complexity: str | None
    confidence: float
    rationale: str
    runner_up_service_line: str | None
    runner_up_confidence: float | None
    key_signals: list[str]
    flags: list[str]
```

### 10.3 Failure handling
- Normalise casing/whitespace on enum fields before mapping to the DB enum —
  structured outputs aren't guaranteed exact-case.
- `stop_reason == "refusal"` → terminal failure, do not retry.
- `stop_reason == "max_tokens"` → retry once with higher `max_tokens`.
- Any other exception (timeout, API error) → retry once.
- If the retry also fails: return a typed `ClassificationError` with a
  message. The caller sets `status='failed'`, `error_message=<message>`, and
  still inserts the enquiry row.

### 10.4 Prompt
Build the system prompt from the service-line list + complexity rubric.
Instruct the model to:
- classify by the work needed, not the client's industry
- judge complexity on scope/ambiguity/stakeholders, not urgency or size
- express confidence as "how often a senior analyst would agree" (tightens
  the distribution vs. asking for raw confidence)
- set `runner_up_service_line`/`runner_up_confidence` whenever a second line
  is plausible — margin is a useful uncertainty signal
- return `null` + `insufficient_information` rather than guessing on empty
  descriptions
- put verbatim phrases in `key_signals`

Include 2–3 worked examples, including one ambiguous case and one
insufficient-information case.

---

## 11. Pipeline — `services/pipeline.py`

One function, called synchronously from the `POST /api/enquiries` handler:

```
def process(enquiry_data) -> EnquiryResult:
    try:
        result = classifier.classify(enquiry_data)   # one retry inside
    except ClassificationError as e:
        return failed(error_message=e.message)

    team, rule_name = router.route(result)
    status = "needs_review" if gate(result) else "routed"
    return EnquiryResult(..., team_id=team.id, matched_rule=rule_name, status=status)
```

**Gate:** `needs_review` if `confidence < CONFIDENCE_THRESHOLD` (default
0.75) **or** `flags` is non-empty **or** `runner_up_confidence` is within
0.15 of `confidence`. Otherwise `routed`.

A `needs_review` enquiry still has a team assigned (the routing rules always
produce a proposal) — the UI shows it as provisional, never blank.

---

## 12. Routing — `services/router.py`

Pure function, no DB, no API calls:

```python
RULES = [
    {"name": "...", "priority": 1, "conditions": {...}, "team_service_line": "...", },
    ...
]

def route(result) -> tuple[Team, str | None]:
    ...  # first matching rule wins; falls back to default team, matched_rule=None
```

Rules live in code, not the database — they're seeded constants with no
admin UI to edit them, so a table would add a migration and seed step for no
behavioural benefit. `tests/test_router.py` covers: exact match, priority
ordering, partial conditions, no match → default team. These tests need
neither an API key nor a database connection.

8–12 rules, same guidance as before: at least one keyed on complexity, one
on urgency, one on industry, plus a catch-all per service line.

---

## 13. API contract

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/enquiries` | Validates, classifies, routes, inserts one row. Returns the full result (not `202` — the client waits for the real outcome). |
| `GET` | `/api/enquiries` | Filters: `status`, `service_line`, `complexity`, `urgency`, `team_id`, `q`. Paginated via `page`/`page_size` (default 10, max 50). Include `counts_by_status` (unfiltered — tab counts), `total`/`page`/`page_size`/`total_pages` (reflecting the current filters). |
| `POST` | `/api/enquiries/{id}/review` | Body `{reviewer, action: approve\|correct\|close, corrected_service_line?, corrected_complexity?, corrected_team_id?}`. On `correct`: update the row in place, set `was_corrected=true` if any value differs from the model's, set `status='routed'`. On `approve`: just set `status='routed'`. On `close`: set `status='closed'` — for enquiries that are spam, out of scope, or otherwise not worth routing; classification fields are left untouched. All three set `reviewed=true`. |
| `POST` | `/api/enquiries/{id}/retry` | Only valid when `status='failed'`. Re-runs the pipeline for that row and updates it in place (same id, no new row) — this is what the Failed tab's Retry button (§15) calls. |
| `GET` | `/api/teams` | |
| `GET` | `/api/service-lines` | For form dropdowns. |
| `GET` | `/api/health` | DB connectivity. |

---

## 14. Eval script — `evals/run_eval.py`

Small and optional-to-polish, not a research deliverable. `golden.jsonl`
holds ~15 hand-labelled examples (include the ambiguous and
insufficient-information cases). The script runs classification over the
set and prints:

- Service line accuracy (exact match)
- Complexity accuracy (exact match)
- Mean confidence, split by correct vs. incorrect predictions — enough to
  say whether `CONFIDENCE_THRESHOLD=0.75` is reasonable, without building a
  full calibration/bucketing system

No confusion matrix, no margin-calibration table, no model-comparison flag.

---

## 15. Frontend

Two routes. (A third, `/dashboard`, was built with metrics tiles and Recharts
volume/service-line charts, then removed — it wasn't part of "the core
classification/routing logic" the brief asks for, and a chart page running on
15-20 hand-seeded rows was more surface area to defend to a reviewer than
value it added. The Queue page's alert tiles already give at-a-glance
operational visibility; the eval script gives the accuracy story.)

**`/submit`** — the intake form. Description has a 40-character minimum. On
success, show the reference number only — nothing about the AI.

**`/queue`** — the primary operational view, and where review happens (no
separate detail/review page). Alert tiles across the top (Needs review,
Failed counts) act as tab shortcuts. Search box (`q`) and a service-line
filter sit above a dense table: client (company + truncated description),
service line badge, complexity, confidence bar, assigned team + lead
(provisional styling if `needs_review`), status pill. Filter tabs with
counts: `All`, `Needs review`, `Routed`, `Failed`, `Closed`. Paginated
(row count fits the viewport) rather than rendering the whole table.
Selecting a row opens a sticky detail panel (not an inline expand) showing
the full description, rationale, `key_signals` as chips, the runner-up
service line, the matched rule name, and who the enquiry is assigned to and
when. For `needs_review` rows: Approve / Correct / Close controls (dropdowns
pre-filled with the model's answer) — Close is for spam/out-of-scope
enquiries that shouldn't be routed at all. Failed rows show `error_message`
and a Retry button (re-runs the pipeline for that row) instead of the review
controls.

---

## 16. Build order

1. Compose up, Postgres healthy, `metadata.create_all()`, `/api/health`.
2. `seed.py` (teams + enquiries, no AI). `POST` + `GET /api/enquiries`
   against hand-inserted rows.
3. `router.py` + `tests/test_router.py`. No API key or DB needed for these
   tests.
4. `classifier.py` standalone CLI — classify one seeded enquiry, print the
   result. Iterate the prompt here.
5. Wire `pipeline.py` into the `POST` handler. Failure handling, retry.
6. Frontend: submit → queue (with inline review).
7. Eval script.
8. README.

---

## 17. Conventions

- Type hints everywhere in Python; `strict` TypeScript.
- No business logic in route handlers — they parse, delegate, serialise.
- One module owns the Anthropic client.
- Enum values are `snake_case` on the wire; display names live in the
  frontend.
- No `print` in application code.

---

## 18. README requirements

1. One-command setup, and what works without an API key (router tests,
   seeded data).
2. Architecture diagram + request walkthrough.
3. Design decisions and trade-offs — at minimum: why routing is a rules list
   rather than a model output; why classification is synchronous rather than
   queued at this volume; why corrections overwrite in place instead of
   versioning; why the rules live in code instead of a database table.
4. What `confidence` actually is: model self-reported, not a calibrated
   probability. The threshold is a starting estimate backed by the eval
   script's correct-vs-incorrect confidence split, not a precisely derived
   number — and would need revisiting after any prompt change.
5. What was deliberately left out and the threshold for adding it back: a
   background worker/queue (needed once volume or latency tolerance
   changes), an audit-history table (needed if compliance or dispute
   resolution requires seeing what the model originally said), and deeper
   calibration analysis (needed once there's enough labelled volume for
   buckets to be meaningful — not at n≈15).
6. Eval results.
7. Failure modes handled: malformed output, refusals, truncation, enum
   casing drift, enquiries too vague to classify.

The closing argument: a classifier at 88% accuracy with a working review
queue beats one at 94% with none.
