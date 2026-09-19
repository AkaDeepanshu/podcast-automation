# Automation Implementation Plan

Hands-off loop for podcast-automation: **topic queue → scheduled run → existing Celery pipeline (audio-first) → notify to upload**.

**Deferred (by design):** full-length video validation, YouTube OAuth upload, WhatsApp.

**Grounded in the current repo** (not the earlier gap report alone). Paths and defaults below match the live code as of the Studio/web stack.

---

## 1. Current codebase facts

### What already works
| Piece | Location |
|-------|----------|
| Pipeline stages | `run_pipeline.run_job` → script / TTS / assembly / video |
| Celery task | `backend.tasks.run_podcast_job(topic, job_id, skip_video)` |
| Redis broker | `backend/celery_app.py`, `docker-compose.yml` (Redis **exists**; Beat does **not**) |
| Job API | `POST/GET/DELETE /api/jobs`, retry, script/audio/video |
| UI | `frontend/src/` — Episodes `/`, Config `/config`, episode detail |
| State | SQLite `data/state/jobs.db` via **SQLAlchemy** (API) + **JobStateDB** sqlite3 (pipeline) |
| Quota soft-check | `data/state/provider_usage.db` via `ProviderUsageTracker` (inside providers, not scheduler) |

### Proven gaps (must fix or design around)
1. **`EpisodeConfig` is stored, never applied.**  
   `create_job` writes `episode_configs` (`target_duration_minutes`, `num_segments`, `model`, `skip_video`) then Celery only passes `skip_video`. `run_job` always uses `load_config()` / `config.yaml` for duration and segments. `EpisodeConfig.model` has **no defined semantics** today.
2. **`find_in_progress_jobs()` is dead code** (`core/state_db.py`) — never called. Crashed workers leave `jobs.status = in_progress`.
3. **`skip_video` defaults disagree:** UI `NewEpisodeForm` defaults **true**; API/`JobCreate`/Celery/CLI default **false**.
4. **Dual writers on `jobs.db`:** new tables must be SQLAlchemy models + `init_db()`, **not** only `JobStateDB.SCHEMA`.
5. **Personas / voice IDs** are **not** on `EpisodeConfig` — they live in `config/speakers.yaml` (`GET/PUT /api/config`).
6. Worker has `worker_prefetch_multiplier=1` but concurrency is not locked to 1 in ops docs — schedule must assume **one heavy job at a time**.

### Job status machine (do not change)
`pending` → `in_progress` → `completed` | `completed_with_warnings` | `failed`

Topic “success” must treat **`completed` and `completed_with_warnings`** as done.

---

## 2. Target end state (audio-first)

```
Focus areas + topic inbox
        │ approve (optional)
        ▼
  approved topics (priority queue)
        │ Celery Beat tick / Run next
        ▼
  enqueue_job()  →  same path as POST /api/jobs
        │
        ▼
  run_podcast_job  →  script → TTS → assembly  (video skipped by default)
        │
        ▼
  Telegram: episode ready / failed  →  human uploads to YouTube
```

Manual path stays: Studio UI + `run_pipeline.py` unchanged in role.

---

## 3. Topic vs job status (keep separate)

### Topics table status
```
draft ──approve──► approved ──dequeue──► queued ──dispatch──► running
                                                              │
                    ┌─────────────────────────────────────────┤
                    ▼                                         ▼
                  done                              failed / skipped
```

| Topic status | Meaning |
|--------------|---------|
| `draft` | Needs approval when `require_approval=true` |
| `approved` | Eligible for dequeue |
| `queued` | Reserved by tick (idempotent claim) |
| `running` | `job_id` set; Celery running |
| `done` | Linked job is `completed` or `completed_with_warnings` |
| `failed` | Linked job failed (after retry policy) |
| `skipped` | Manually skipped / focus area disabled — **not** the same as quota defer |

Quota defer: leave topic **`approved`**, skip tick, emit `llm_quota_exhausted` — do **not** mark failed.

### Schema (same `jobs.db`, SQLAlchemy)

**`focus_areas`**
- `id`, `name` (unique), `enabled`, `created_at`

**`topics`**
- `id`, `focus_area_id` (nullable FK), `title`, `source` (`manual` \| `auto` \| `rss`)
- `status`, `priority` (higher first), `created_at`, `updated_at`
- `job_id` (nullable FK → `jobs.job_id`), `error`, `attempt_count` (default 0)

**`automation_settings`** (singleton `id=1`)
- `enabled`, `require_approval`, `min_queue_depth`
- Schedule: prefer one `cron` string **or** (`cadence` + `weekday` + `time_local`) + `timezone` (default align with Celery `UTC`)
- `default_skip_video` (default **true**)
- `last_tick_at`, `last_run_job_id`, `last_error`

Secrets (**never** in UI config JSON): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in `.env`.

---

## 4. Phases

### Phase 0 — Harden core (do first)

**Goals**
1. Apply `EpisodeConfig` inside the worker before stages run.
2. Orphan recovery for stuck `in_progress` jobs.
3. Align `skip_video` defaults with the UI (API + recommended CLI).

**EpisodeConfig merge rules**
- Load row by `job_id` in `run_podcast_job` (so retry and future `run-next` stay consistent).
- Deep-copy `config` from `load_config()`, then if set:
  - `script_generation.target_duration_minutes`
  - `script_generation.num_segments`
  - `skip_video` from EpisodeConfig (authoritative over task arg when row exists)
- **`model` override (define and document):** if `EpisodeConfig.model` is set, write it to **`script_generation.gemini.model` only** when `providers.script_generator` is `gemini` or `fallback_chain`. Do **not** invent provider switching from a bare string in v1. (Optional later: `provider:model` syntax.)

**Orphans**
- On Celery worker process start (and/or each automation tick): jobs with `status=in_progress` older than a grace window (e.g. 10 minutes with no stage update) → mark `failed` with error `orphaned_worker`. Prefer fail over blind re-queue (partial TTS is messy).

**Files**
| File | Change |
|------|--------|
| `backend/tasks.py` | Load EpisodeConfig; merge; effective skip_video |
| `run_pipeline.py` | Accept merged config (already receives `config` dict — merge happens before call) |
| `backend/schemas.py` | `JobCreate.skip_video: bool = True` |
| `backend/models.py` | Default `EpisodeConfig.skip_video = True` |
| `backend/celery_app.py` or worker boot hook | Call orphan cleanup |
| `core/state_db.py` | Use `find_in_progress_jobs` **or** equivalent SQLAlchemy query |

**Verify:** create job via UI with duration=10 / segments=2 → outline length matches; API default skip_video true; kill worker mid-job → next start marks orphan failed.

---

### Phase 1 — Topic queue + Run next

**API (all under `/api/...`)**
- `GET/POST /api/focus-areas`, `PATCH/DELETE /api/focus-areas/{id}`
- `GET/POST /api/topics`, `PATCH/DELETE /api/topics/{id}`
- `POST /api/topics/{id}/approve` → `draft` → `approved`
- `POST /api/queue/run-next` → claim highest-priority `approved` topic → shared **`enqueue_job(topic, skip_video=settings.default_skip_video, ...)`** (extract from today’s `create_job`)

**Idempotency**
- Single SQLAlchemy transaction: `approved` → `queued` → create Job + EpisodeConfig → `running` + `job_id` → commit → then `delay(...)`.
- If dispatch fails after commit, mark topic `failed` and notify (Phase 3); do not leave forever `queued`.

**UI**
- Nav: add **Topics** in `AppShell` (`/topics`).
- Page: list, add topic, approve, delete, priority, **Run next** button; Focus Areas editor (simple).

**Files**
| File | Change |
|------|--------|
| `backend/models.py` | `FocusArea`, `Topic` |
| `backend/schemas.py` | DTOs |
| `backend/services/enqueue.py` (new) | Shared create-job + Celery dispatch |
| `backend/routers/jobs.py` | Refactor to use `enqueue_job` |
| `backend/routers/topics.py` (new) | CRUD, approve, run-next |
| `backend/main.py` | Include router |
| `frontend/src/components/AppShell.tsx` | Nav |
| `frontend/src/app/topics/page.tsx` | UI |
| `frontend/src/lib/api.ts`, `types.ts` | Clients |

**Verify:** add topic → approve → Run next → worker completes → topic `done`, job visible on Episodes.

**Note:** “Approve gate” is **part of this phase** (`require_approval` can default true; settings UI in Phase 2). Not a separate later schema.

---

### Phase 2 — Scheduler + automation control

**Runtime**
- Add **Celery Beat** process (same Redis). Document:
  ```bash
  celery -A backend.celery_app worker --concurrency=1 --loglevel=info
  celery -A backend.celery_app beat --loglevel=info
  ```
- Task `automation_tick`: if `automation_settings.enabled` and lock free → same logic as `run-next`.
- **Single-job lock:** Redis `SET automation:lock NX EX <ttl>` (TTL > worst-case episode, e.g. 2–3h) **and** skip if any job `in_progress`. Release lock in task `finally` when topic leaves `running`.

**Quota-aware tick**
- Before dequeue, call `ProviderUsageTracker` for the primary Gemini model vs `script_generation.gemini.daily_limit`.
- If near limit: skip start, set `last_error`, emit `llm_quota_exhausted` (Phase 3). Leave topics `approved`.

**API**
- `GET/PUT /api/automation`
- `POST /api/automation/start` | `/stop` | `/run-now`

**UI**
- Nav **Automation** (`/automation`): enable toggle, schedule, timezone, require_approval, min_queue_depth, default_skip_video, last tick/run status.

**Files**
| File | Change |
|------|--------|
| `backend/models.py` | `AutomationSettings` |
| `backend/locks.py` (new) | Redis lock helper |
| `backend/tasks.py` | `automation_tick` |
| `backend/celery_app.py` | Beat schedule entry (static interval OK v1; dynamic cron later) |
| `backend/routers/automation.py` (new) | Settings + start/stop/run-now |
| `frontend/src/app/automation/page.tsx` | UI |
| Ops note in README | Worker concurrency=1 + beat |

**Verify:** enable automation → Beat fires → one job → second tick no-ops while lock held.

---

### Phase 3 — Notifications (Telegram first)

**Interface**
```python
class Notifier(Protocol):
    def send(self, event: str, payload: dict) -> None: ...
```

**Events (v1)**
- `episode_completed` — job_id, topic, audio path/URL hint
- `episode_failed` — job_id, stage, error
- `queue_low` — depth &lt; min_queue_depth
- `llm_quota_exhausted`

**Implementation**
- `TelegramNotifier` via Bot API (one HTTP POST).
- Hook **after** `run_job` in `run_podcast_job` (success / exception) and update linked `topics` row.
- `POST /api/notifications/test`
- Env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Add `.env.example` entries (no secrets).

**Later in this phase (optional stretch)**
- Discord webhook notifier.
- Inbound Telegram commands (`/pause`, `/resume`, `/status`, `/runnow`, `/addtopic`) = **separate** long-poll or webhook process — not Beat. Defer if it blocks the hands-off loop.

**Files**
| File | Change |
|------|--------|
| `backend/notify/base.py`, `telegram.py` | Interface + Telegram |
| `backend/tasks.py` | Emit events; sync topic status |
| `backend/routers/notifications.py` | Test send |
| `.env.example` | Token placeholders |
| Automation UI | Channel enabled + test button |

**Verify:** complete a short episode → Telegram message received; fail script → failure message.

---

### Phase 4 — Topic discovery (after queue + notify)

1. `TopicDiscovery` interface; **v1:** LLM generates N titles per enabled focus area; dedupe against `topics.title` + recent `jobs.topic` (simple normalized string match; embeddings optional later).
2. Beat/helper `discover_topics` when queue depth &lt; `min_queue_depth` → insert as `draft` (or `approved` if `require_approval=false`).
3. Notify `topics_suggested` with titles.
4. **v2:** RSS / Reddit / Trends ranking.
5. **v3:** YouTube Data API popularity — only when upload strategy exists.

**Files:** `backend/discovery/`, new Celery task, reuse script LLM providers carefully (quota!).

---

### Phase 5 — Deferred

| Item | Notes |
|------|--------|
| Full-length video validation | Fix A/V duration; keep `default_skip_video=true` until proven |
| YouTube OAuth upload | New publish stage; credentials in env; optional auto vs remind-only flag |
| WhatsApp | Twilio / Cloud API last (heaviest setup) |

---

## 5. Build order

| # | Deliverable | Depends on | Outcome |
|---|-------------|------------|---------|
| 1 | Phase 0 core fixes | — | Overrides + orphans + skip_video aligned |
| 2 | Phase 1 topic queue + run-next | 1 | Manual queue → automated pipeline |
| 3 | Phase 2 Beat + lock + settings | 2 | Scheduled hands-off runs |
| 4 | Phase 3 Telegram hooks | 3 (or 2 for manual run-next) | Phone/chat updates |
| 5 | Phase 4 LLM topic suggestions | 2 + 4 | Queue refills itself |
| 6 | Discord / inbound bot / RSS | 4–5 | Nice-to-have |
| 7 | Video + YouTube upload | — | Explicitly later |

**Items 1–4 = full hands-off audio loop** (you still upload to YouTube manually after Telegram ping).

---

## 6. Design rules (non-negotiable)

1. **Quota-aware scheduling** — ~7+ Gemini calls/episode vs `daily_limit` ~18; tick checks usage **before** dequeue.
2. **Idempotent claim** — topic `approved` → `queued`/`running` in one DB transaction before Celery `delay`.
3. **Failure policy** — one automatic topic retry (`attempt_count`), then `failed`, notify, continue queue; do not stall on one bad topic.
4. **Secrets in env** — never returned by `GET /api/config` or stored in `automation_settings` plaintext for tokens.
5. **One Kokoro job at a time** — Redis lock + worker `--concurrency=1`.
6. **Additive APIs** — existing `/api/jobs` and CLI keep working; extract shared `enqueue_job` instead of duplicating create logic.
7. **Do not claim “zero schema change”** — Phase 0 changes EpisodeConfig behavior; Phase 1 adds tables via SQLAlchemy `create_all`.

---

## 7. Out of scope for this plan’s v1 success criteria

- YouTube upload or scheduling on YouTube
- Guaranteed 30‑minute video renders
- WhatsApp
- Changing Kokoro / paying for ElevenLabs
- Replacing SQLite with Postgres (not required until multi-host)

---

## 8. Suggested first PR

**Phase 0 only** — small, testable, unblocks every later phase:

1. Merge EpisodeConfig in `run_podcast_job`.
2. Flip API `skip_video` default to `True`.
3. Orphan `in_progress` cleanup on worker start.

Then open Phase 1 (Topics UI + `/api/queue/run-next`).
