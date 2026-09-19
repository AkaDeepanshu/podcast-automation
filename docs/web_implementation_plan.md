

# FastAPI + Next.js Web App — Full Implementation Plan

## Folder structure (what gets added)

```
podcast-automation/
├── core/                    ← untouched, all pipeline code stays here
├── config/                  ← shared YAML (CLI + API)
├── data/                    ← runtime / generated / uploads
│   ├── jobs/
│   ├── logs/
│   ├── state/               ← SQLite (jobs.db, provider_usage.db)
│   └── assets/              ← speaker/logo PNGs
├── backend/                 ← new
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── celery_app.py
│   ├── tasks.py
│   └── routers/
│       ├── jobs.py
│       ├── config.py
│       ├── assets.py
│       └── ws.py
├── frontend/                ← new (Next.js app)
│   ├── src/
│   │   ├── app/             ← Next.js app router
│   │   │   ├── page.jsx           (Dashboard)
│   │   │   ├── episodes/[id]/
│   │   │   │   └── page.jsx       (Episode detail)
│   │   │   └── config/
│   │   │       └── page.jsx       (Config editor)
│   │   ├── components/
│   │   │   ├── StageTracker.jsx
│   │   │   ├── LogStream.jsx
│   │   │   ├── MediaPlayer.jsx
│   │   │   └── NewEpisodeForm.jsx
│   │   └── lib/
│   │       └── api.js             (axios client)
│   └── package.json
├── docker-compose.yml       ← redis only (no postgres yet)
├── .env
└── run_pipeline.py          ← still works unchanged
```

---

## Backend — what each file does

### `database.py`
SQLAlchemy engine pointing at `data/state/jobs.db` (SQLite now). Single `get_db()` dependency injected into every route. When you go to cloud, change one connection string here — nothing else changes.

### `models.py`
SQLAlchemy ORM versions of your existing SQLite tables: `Job`, `Stage`, `TtsLine`, `ProviderUsage`. Plus a new `EpisodeConfig` table — stores per-job config overrides (duration, model, voices) that the UI lets you set per episode rather than editing `config.yaml`.

### `schemas.py`
Pydantic models for request/response validation. Keeps the API contract explicit and gives you automatic FastAPI docs.

### `celery_app.py`
Celery instance configured with Redis as broker. One file, ~15 lines.

### `tasks.py`
The Celery task that wraps `run_job()`. The key addition over the plain CLI: it installs a custom logging handler that publishes each log line to a Redis pub/sub channel `logs:{job_id}` as it's emitted — this is what drives the live log stream in the browser.

### `routers/jobs.py`
```
POST   /api/jobs                    create job, dispatch Celery task, return job_id
GET    /api/jobs                    list all jobs (id, topic, status, created_at)
GET    /api/jobs/{id}               job detail + all stage statuses
POST   /api/jobs/{id}/retry         reset a stage, re-dispatch
GET    /api/jobs/{id}/script        return 02_script.json
GET    /api/jobs/{id}/audio         stream 04_final_audio.wav
GET    /api/jobs/{id}/video         stream 05_video.mp4
DELETE /api/jobs/{id}               delete job + all outputs
```

### `routers/ws.py`
WebSocket endpoint `/ws/jobs/{id}/logs`. On connect, subscribes to the Redis pub/sub channel for that job and pushes each message to the browser. Also replays the last N lines from the log file so the browser catches up if you open the page mid-run.

### `routers/config.py`
```
GET /api/config        return current config.yaml as JSON
PUT /api/config        write back to config.yaml
```

### `routers/assets.py`
```
POST /api/assets/speaker_a    upload PNG → saves to data/assets/speaker_a.png
POST /api/assets/speaker_b    upload PNG → saves to data/assets/speaker_b.png
POST /api/assets/logo         upload PNG → saves to data/assets/logo.png
GET  /api/assets/{name}       serve the image (for preview in UI)
```

---

## Frontend — what each page does

### Dashboard (`/`)
- Grid of episode cards: topic, status badge (pending/running/completed/failed), created date, duration
- "New Episode" button → opens a modal with the episode creation form
- Episode creation form: topic input + expandable "Advanced" section with config overrides (duration, model, num_segments)

### Episode detail (`/episodes/[id]`)
Three panels:

**Stage Tracker** — horizontal row of stages with status badges:
```
[script ✓] → [tts ✓] → [assembly ✓] → [video ✗]
                                              ↑
                                    [Retry this stage]
```
Each failed stage shows its error message inline. Retry button calls `POST /api/jobs/{id}/retry?from_stage=video`.

**Log Stream** — scrollable terminal-style panel. WebSocket connection to `/ws/jobs/{id}/logs`. Auto-scrolls to bottom. Shows timestamps and level (INFO/WARNING/ERROR) with color coding. Reconnects automatically if the connection drops.

**Outputs panel** — shows when available:
- Script: expandable dialogue viewer showing each line with speaker label
- Audio: HTML5 audio player
- Video: HTML5 video player
- Download buttons for each output file

### Config (`/config`)
Form with all fields from `config.yaml`: model selection dropdowns (gemini/groq), duration slider, segment count, voice IDs for both speakers, pause durations, forbidden phrases list. Saves via `PUT /api/config`.

---

## Build order — 6 steps, each ships something usable

**Step 1 — Redis + Celery (day 1)**
```bash
docker run -d -p 6379:6379 redis:alpine
```
Write `celery_app.py` and `tasks.py`. Test that `run_job.delay(topic, job_id, ...)` actually runs the pipeline in the background. At the end of this step: pipeline runs async.

**Step 2 — FastAPI core API (day 1-2)**
`main.py` + `database.py` + `models.py` + `schemas.py` + `routers/jobs.py`. No frontend — verify with curl. At end: can create jobs, check status, get output files via API.

**Step 3 — WebSocket log streaming (day 2)**
Modify `tasks.py` to publish log lines to Redis. Write `routers/ws.py`. Test with `wscat -c ws://localhost:8000/ws/jobs/{id}/logs`. At end: live logs stream out of running jobs.

**Step 4 — Next.js scaffold + Dashboard (day 2-3)**
Create Next.js app, axios client, Dashboard page, NewEpisodeForm. At end: can create and monitor jobs from browser.

**Step 5 — Episode detail page (day 3)**
StageTracker component, LogStream (WebSocket), retry button, media players. At end: full episode management in browser.

**Step 6 — Config + Assets (day 4)**
Config editor form. Asset upload. At end: no more manual file editing for normal usage.

---

## The one non-obvious technical piece — log streaming

The chain is: `Celery worker → Redis pub/sub → FastAPI WebSocket → Browser`. The tricky part is that Celery tasks run in a separate process from FastAPI, so you can't share an in-memory queue. Redis pub/sub solves this cleanly.

In `tasks.py` the logging handler looks like:

```python
class RedisLogHandler(logging.Handler):
    def __init__(self, redis_client, job_id):
        super().__init__()
        self.redis = redis_client
        self.channel = f"logs:{job_id}"

    def emit(self, record):
        self.redis.publish(self.channel, json.dumps({
            "level": record.levelname,
            "msg": self.format(record),
            "ts": record.created,
        }))
```

The existing `get_job_logger()` in `logging_setup.py` gets one more handler added to it. No other pipeline code changes.

---

## Dependencies to add

**Backend (`requirements.txt` additions):**
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
celery[redis]>=5.3.0
redis>=5.0.0
sqlalchemy>=2.0.0
python-multipart>=0.0.9    # for file uploads
```

**Frontend (`package.json` key deps):**
```json
{
  "next": "^14",
  "react": "^18",
  "axios": "^1.6",
  "tailwindcss": "^3"
}
```

---

## What does NOT change

- Every file under `core/` — untouched
- `run_pipeline.py` — still works as a CLI
- `config.yaml` and `speakers.yaml` — still the config source, just editable via UI
- `.env` — same secrets file, FastAPI reads it via the existing `load_dotenv` in `config_loader.py`
- The stage checkpointing and resume logic — the web retry button just calls the same resume mechanism that `--resume` already uses

---