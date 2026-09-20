# Ops runbook — daily hands-off audio loop

Use this after Phases 0–4 are in place. Goal: one (or a few) reliable
episodes per day without babysitting the pipeline.

## Processes that must be up

| Process | Command | Why |
|---------|---------|-----|
| Redis | `docker compose up -d` | Celery broker + live logs |
| API | `uvicorn backend.main:app --reload --port 8000` | Studio + webhooks |
| Worker | `celery -A backend.celery_app worker --concurrency=1 --loglevel=info` | Runs episodes (exactly concurrency 1) |
| Beat | `celery -A backend.celery_app beat --loglevel=info` | Tick + discovery when queue low |
| Frontend | `cd frontend && npm run dev` | Optional if you only care about automation |

Quick check (API must be up):

```bash
source venv/bin/activate
python scripts/check_ops.py
# or
curl -s http://127.0.0.1:8000/api/ops/status | python -m json.tool
```

Studio **Automation** page also shows an Ops health panel.

## Recommended settings (audio-first)

| Setting | Where | Suggested | Notes |
|---------|--------|-----------|--------|
| `interval_minutes` | Automation UI | `1440` | ~1 episode / day |
| `min_queue_depth` | Automation UI | `3` | Keep 3 draft+approved in buffer |
| `require_approval` | Automation UI | `true` at first | Review discovered titles; set `false` when you trust discovery |
| `default_skip_video` | Automation UI | `true` | Video still deferred |
| `script_generation.gemini.daily_limit` | `config/config.yaml` | `18` (or slightly under your real RPD) | Soft pre-check; automation skips near limit |
| Worker concurrency | CLI | `1` | Never raise while Kokoro is local/heavy |
| Focus areas | Topics UI | ≥1 enabled | Discovery needs them |

Timezone is recorded for display; Beat schedule is still a fixed 60s poll
plus `interval_minutes` gate (not cron yet).

## First E2E soak (do this once)

1. Redis + API + worker + beat running; `python scripts/check_ops.py` shows workers ≥ 1.
2. Automation → **Send test** (Telegram).
3. Topics → enable a focus area → **Suggest topics** → approve 1–2 titles.
4. Automation → set interval to something short for the test (e.g. `5`) → **Start** → or **Run now**.
5. Confirm Telegram: episode started → (wait) completed/failed.
6. Set `interval_minutes` back to `1440` for production-ish pacing.
7. Leave automation **Start**ed overnight; next morning check Episodes + `last_tick_at` / `last_run_at`.

## Daily checklist (2 minutes)

- [ ] `python scripts/check_ops.py` — Redis ok, workers online
- [ ] Automation enabled if you want hands-off runs
- [ ] Approved (or buffer) depth ≥ `min_queue_depth`, or discovery will refill
- [ ] Gemini usage not near daily limit (panel / ops status)
- [ ] Telegram got last episode completed (or investigate failed)
- [ ] No orphaned `in_progress` jobs (worker restart cleans old ones)

## When something stalls

| Symptom | Likely fix |
|---------|------------|
| Jobs stuck `pending` | Worker down or Redis down |
| Automation on but no runs | Beat down, or `too_soon` (interval), or no approved topics, or quota |
| Discovery never refills | No enabled focus areas; lock held; quota; or buffer already ≥ min |
| Telegram test OK, episode silent | Restart **worker** after `.env` / notify code changes |
| Lock held forever | Job crashed before sync; restart worker (orphan cleanup) or wait TTL (~3h) |

## Quota math (keep in mind)

One episode ≈ `1 + num_segments` Gemini calls (default 7). With
`daily_limit: 18` you have room for ~2 episodes plus a little discovery.
Discovery costs ~1 call per enabled focus area per refill. Ops status
reports `headroom_needed` = segments + 2 so an episode can still finish.
