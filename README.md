# Podcast Automation — Script + TTS + Audio Assembly (+ Studio)

Current scope: `topic` → structured two-speaker dialogue script (Gemini, with
fallback chain) → per-line synthesized audio (Kokoro, free/local) → one
mastered episode audio file — runnable from the **CLI** or from the **Studio**
web UI (FastAPI + Next.js + Celery), with a topic queue, scheduled automation,
LLM topic discovery, and Telegram notifications.

**Built:** audio pipeline end-to-end, Studio UI, topic queue + Run next,
Celery Beat automation, Telegram alerts, LLM topic suggestions.

**Deferred (by design):** full-length video validation, YouTube OAuth upload,
WhatsApp / Discord inbound bots. Video stage exists but Studio defaults to
audio-only (`skip_video=true`); use CLI `--with-video` when you explicitly
want the video stage.

---

## 1. Setup

### 1.1 Install dependencies

```bash
cd podcast-automation

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Kokoro also needs `espeak-ng` as a system dependency:

```bash
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y espeak-ng

# macOS
brew install espeak-ng
```

`ffmpeg` is required by the audio assembly stage (via `pydub`). Most
systems have it already; if not:

```bash
# Debian/Ubuntu
sudo apt-get install -y ffmpeg

# macOS
brew install ffmpeg
```

Frontend (Studio UI):

```bash
cd frontend && npm install && cd ..
```

Redis (Celery broker + live log pub/sub):

```bash
docker compose up -d
```

### 1.2 Secrets — `.env` file (not shell exports)

Copy the template and fill in your key(s):

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your-actual-gemini-key
GROQ_API_KEY=your-actual-groq-key

# Optional — Telegram notifications (Studio Automation → Send test)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

- Gemini (free, no card): https://aistudio.google.com/apikey
- Groq (free, no card): https://console.groq.com/keys — used as an automatic
  fallback when Gemini's free quota is exhausted (see §7 below)
- Telegram: create a bot with [@BotFather](https://t.me/BotFather), message it,
  then set `TELEGRAM_CHAT_ID` to your chat id

`.env` is loaded automatically by every entrypoint (via
`core/config_loader.py`) — no `export` or `.bashrc` editing needed, and
`.env` is gitignored so keys never get committed.

Optional frontend API base (defaults to `http://127.0.0.1:8000`):

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### 1.3 First Kokoro run will download model weights

The first time `KokoroTTSEngine` runs, it downloads the model (~few hundred
MB) from Hugging Face Hub automatically. Needs internet once; runs fully
offline after that. No extra setup needed — just don't be surprised by the
first-run delay.

---

## 2. Run locally (Studio)

You need **Redis** plus up to **four processes**. Use separate terminals
(venv activated in each Python terminal).

```bash
# Terminal 1 — API
source venv/bin/activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Celery worker (one heavy job at a time)
source venv/bin/activate
celery -A backend.celery_app worker --concurrency=1 --loglevel=info

# Terminal 3 — Celery Beat (scheduled automation + queue refill discovery)
source venv/bin/activate
celery -A backend.celery_app beat --loglevel=info

# Terminal 4 — Next.js Studio
cd frontend && npm run dev
```

| Service | URL |
|---------|-----|
| Studio UI | http://127.0.0.1:3000 |
| API docs | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/health |

**Without Beat**, you can still create episodes and use **Topics → Run next**
or **Automation → Run now**. Beat is required for hands-off scheduled runs.

### Typical Studio flow

1. **Config** — speakers, duration, script provider.
2. **Topics** — add focus areas → **Suggest topics** (or add manually) → approve drafts.
3. **Automation** — interval / min queue depth → **Start** (needs worker + beat).
4. **Episodes** — watch jobs; open an episode for live logs + audio player.
5. Telegram pings on episode start/finish, topic suggest/approve, automation
   start/stop, queue-low discovery, etc.

---

## 3. CLI usage (same pipeline, no UI)

### Run a new episode end-to-end (script → TTS → assembled audio)

```bash
source venv/bin/activate
python run_pipeline.py --topic "The history of mechanical keyboards"
```

By default this is **audio-only**. Add `--with-video` to include the video
stage.

This will:
1. Generate an outline (6 segments by default, see `config/config.yaml`)
2. Generate dialogue chunk-by-chunk for each segment
3. Synthesize each dialogue line as a separate `.wav` file
4. Normalize, add natural pauses, stitch, and master into one final
   episode file: `data/jobs/{job_id}/04_final_audio.wav`

### Resuming a failed/interrupted job

If the process crashes or a TTS line fails partway through, just re-run
with the same job ID:

```bash
python run_pipeline.py --resume 20260620_the-history-of-mechanical-keyb_a1b2c3
```

It will skip any already-completed stage/lines and only redo what's
missing or failed. If earlier TTS failures left gaps in the previously
assembled audio, and the retry resolves them, **assembly automatically
re-runs** to fill the gaps — you don't need to force this manually.

Job IDs are printed at the start of each run and are also the folder name
under `data/jobs/`.

### Custom job ID

```bash
python run_pipeline.py --topic "..." --job-id my-episode-01
```

Studio / Celery use the same `run_job` path; EpisodeConfig overrides from the
UI (duration, segments, model, skip_video) are merged in the worker before
stages run.

---

## 4. Output structure

```
data/jobs/{job_id}/
├── 01_outline.json            # segment-by-segment outline
├── 02_script.json             # full dialogue script, structured
├── 03_audio_lines/
│   ├── line_0000_A.wav
│   ├── line_0001_B.wav
│   └── ...
├── 03_tts_results.json        # per-line synthesis results (success/fail, paths)
├── 04_final_audio.wav         # final assembled, mastered episode
├── 04_assembly_manifest.json  # which lines made it in, any gaps, final duration
└── 05_video.mp4               # only if video stage ran
```

`02_script.json` format:

```json
[
  {"speaker": "A", "text": "...", "emotion": "curious", "segment_index": 1, "line_index": 0},
  {"speaker": "B", "text": "...", "emotion": "thoughtful", "segment_index": 1, "line_index": 1}
]
```

---

## 5. Job status values

Checkable via `JobStateDB.get_job(job_id)["status"]` or the Studio Episodes UI:

| Status | Meaning |
|--------|---------|
| `pending` | Created / queued, worker not started yet |
| `in_progress` | Currently running |
| `completed` | Fully succeeded, no gaps in final audio |
| `completed_with_warnings` | Final audio exists but has gaps — one or more TTS lines failed and weren't retried yet. Check `04_assembly_manifest.json` → `skipped_line_indices`, or `data/logs/{job_id}.log` |
| `failed` | A stage errored out entirely (e.g. script generation failed, bad API key) — no usable final audio |

Topic queue statuses (separate from jobs): `draft` → `approved` →
`queued` / `running` → `done` / `failed` / `skipped`. Topic “success”
treats job `completed` and `completed_with_warnings` as done.

Stuck `in_progress` jobs from a crashed worker are marked failed on worker
startup (orphan recovery).

---

## 6. Configuration

- `config/config.yaml` — provider selection, episode length/segment count,
  Gemini params, Kokoro params, pause durations, anti-repetition
  filler-phrase list, daily soft limits
- `config/speakers.yaml` — speaker names, personas, voice IDs. Keep these
  stable across episodes for channel identity. Available Kokoro voices:
  https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- `.env` — secrets only (`GEMINI_API_KEY`, `GROQ_API_KEY`, `TELEGRAM_*`,
  optional `REDIS_URL`)
- Studio **Config** page — edits the same YAML-backed settings via the API
  (never put Telegram tokens in UI config JSON)

To swap providers later (e.g. to paid Claude/ElevenLabs), you'll only
need to: (1) write a new class implementing `ScriptGenerator` or
`TTSEngine` in `core/providers/`, (2) register it in
`core/provider_factory.py`, (3) flip the value in `config.yaml`. Nothing
in `run_pipeline.py` or the pipeline stages needs to change.

Project layout:

```
podcast-automation/
├── backend/           # FastAPI + Celery + discovery + Telegram
├── frontend/          # Next.js Studio
├── core/              # Pipeline stages + providers
├── config/            # config.yaml, speakers.yaml
├── data/
│   ├── jobs/
│   ├── logs/
│   ├── state/         # jobs.db, provider_usage.db
│   └── assets/
├── docs/              # plans
├── docker-compose.yml # Redis
└── run_pipeline.py
```

---

## 7. Free-tier rate limits & the fallback chain

Free LLM tiers are tight — Gemini's free tier in particular can be as low
as ~20 requests/day depending on your account, and one episode costs at
least `1 + num_segments` calls (1 outline + 1 per segment, 7 calls at the
default 6-segment config). That's only 2-3 episodes/day of headroom even
on a perfect run.

To handle this, `script_generation` supports a **fallback chain**:

```yaml
providers:
  script_generator: "fallback_chain"

script_generation:
  fallback_chain:
    - "gemini"
    - "gemini_lite"
    - "groq"
```

How it behaves:
- Tries Gemini (`gemini-2.5-flash`) first. On quota, overload (503), or other
  failure after that provider's internal retries, it falls through to
  `gemini_lite` (`gemini-2.5-flash-lite`, separate quota pool, higher RPD),
  then Groq.
- Once a fallback succeeds, **the run sticks with it** for the rest of that
  episode — it won't bounce back to an earlier provider mid-episode (which
  would otherwise waste calls retrying an exhausted provider, and could cause
  jarring dialogue-style shifts mid-script).
- Groq (https://console.groq.com) is free, no credit card, and its
  free-tier daily request limits are typically far higher than Gemini's.
  The default Groq model is `openai/gpt-oss-20b`, which supports Groq
  **Structured Outputs** (`json_schema`). Older Llama models (e.g.
  `llama-3.3-70b-versatile`) do **not** support `json_schema` — use
  `structured_output_mode: "json_object"` or `"auto"` in config if you
  switch to one of those.
- If every provider in the chain fails, the script stage fails with a
  clear error listing what was tried (including error category:
  quota / transient / config).

**Pre-emptive daily budget check**: each provider also tracks its own call
count locally (`data/state/provider_usage.db`) against a configurable
`daily_limit`. If local tracking shows you're at/near that limit, the
provider fails fast *before* making a network call — skipping straight to
the next provider in the chain rather than wasting a call on a near-certain
429. Set `script_generation.gemini.daily_limit` to a little under your
actual observed RPD (check https://aistudio.google.com/rate-limit) — set
to `0` to disable the pre-check and rely only on reacting to live 429s.

Automation and topic discovery share the same usage DB: the Beat tick skips
starting a new episode (and discovery leaves headroom for one episode) when
near the Gemini daily limit, and can notify via Telegram
(`llm_quota_exhausted`).

**To use a single provider instead of the chain** (e.g. if you have a paid
Gemini tier and don't need a fallback), set
`providers.script_generator: "gemini"` (or `"groq"`) directly — the
single-provider path still works exactly as before.

**Other free script-generation options** worth knowing about, if you want
to extend the chain further:
- `gemini-2.5-flash-lite` — already wired as `gemini_lite` in the default
  fallback chain; higher free RPD than flash, slightly lower quality.
- Groq Structured Outputs models — `openai/gpt-oss-20b` (default),
  `openai/gpt-oss-120b`, `meta-llama/llama-4-scout-17b-16e-instruct`.
  See https://console.groq.com/docs/structured-outputs#supported-models.
  For models without `json_schema` support, set
  `script_generation.groq.structured_output_mode` to `json_object` or `auto`.
- A local model via Ollama would also fit the existing `ScriptGenerator`
  interface if you want a fully offline option later, at the cost of
  needing a capable enough local machine and writing one more provider
  class — not built yet since it's a bigger lift than an API swap.

---

## 8. Audio assembly details

The assembly stage (`core/pipeline/assembly_stage.py`):
- **Per-line loudness normalization** to -20 LUFS before stitching — TTS
  calls vary in volume/energy line to line; this makes them consistent
- **Pauses**: 400ms between turns within a segment, 900ms at segment
  boundaries (configurable) — this is what makes it sound like a
  conversation rather than a wall of audio
- **Final mastering pass**: normalizes the whole stitched episode to -16
  LUFS (a reasonable conversational-podcast loudness target) with peak
  limiting to avoid clipping
- **Gracefully skips** lines with missing/failed audio rather than
  crashing — produces a best-effort episode and records exactly which
  lines were skipped in `04_assembly_manifest.json`

---

## 9. Automation & notifications (summary)

See [`docs/automation_plan.md`](docs/automation_plan.md) for the full plan.

- **Topics** — priority queue; approve then Run next / Beat dequeue
- **Automation** — Redis single-job lock + worker `--concurrency=1`;
  interval gate; quota-aware tick
- **Discovery** — when draft+approved depth &lt; `min_queue_depth`, LLM
  suggests titles per enabled focus area (`source=auto`)
- **Telegram** — episode started/completed/failed, automation start/stop,
  topic added/approved, topics suggested, queue low, quota exhausted
  (secrets stay in `.env` only)

---

## 10. Troubleshooting

**"GEMINI_API_KEY not set"** — make sure `.env` exists (copy from
`.env.example`) and contains a real key. The pipeline fails fast with a
clear error rather than partially running.

**API / UI can’t connect** — uvicorn on port 8000; if you set
`NEXT_PUBLIC_API_URL`, it must match.

**Jobs stay `pending`** — Celery worker isn’t running, or Redis isn’t up
(`docker compose up -d`).

**Automation never starts episodes** — need worker **and** beat, Automation
**Start**ed in Studio, and **approved** topics in the queue.

**Telegram test works but episode alerts don’t** — restart the Celery
worker after changing `.env` or notify code so the worker reloads.

**A TTS line keeps failing** — check `data/logs/{job_id}.log` for the specific
error. Common cause: unusual characters/symbols in generated text that
Kokoro's phonemizer chokes on. You can manually inspect/edit
`data/jobs/{job_id}/02_script.json` and delete the job's row from `data/state/jobs.db`
`tts_lines` table for that line index, then `--resume`.

**Final audio has a gap / silence where a line should be** — check
`data/jobs/{job_id}/04_assembly_manifest.json` → `skipped_line_indices`. That
line's TTS failed and wasn't successfully retried before assembly ran.
`--resume` the job to retry it; assembly will automatically re-run and
fill the gap once the retry succeeds.

**Hitting Gemini rate limits / "RESOURCE_EXHAUSTED" errors** — make sure
`providers.script_generator` is set to `"fallback_chain"` in `config.yaml`
(not just `"gemini"`), and that `GROQ_API_KEY` is set in `.env`. See §7 for
how the fallback chain works. If you're still hitting limits with the
chain active, check the job log — it'll show which provider was tried, the
error category (`quota`, `transient`, `config`), and why it fell back.

**Groq "does not support response format json_schema"** — your configured
Groq model doesn't support Structured Outputs. Either switch to
`openai/gpt-oss-20b` in `script_generation.groq.model` (recommended), or set
`structured_output_mode: "auto"` to downgrade to JSON-object mode.

**Script generation feels repetitive** — tune
`script_generation.forbidden_phrases` in `config.yaml`, or increase
`num_segments` (more, shorter chunks = more variation), or raise
`temperature` slightly.

**Checking job status without re-running:**

```python
from core.state_db import JobStateDB
db = JobStateDB("data/state/jobs.db")
print(db.get_job("your-job-id"))
print(db.get_all_stages("your-job-id"))
```

---

## 11. Docs & deferred next steps

- [`docs/ops_runbook.md`](docs/ops_runbook.md) — daily checklist, recommended settings, E2E soak
- [`docs/web_implementation_plan.md`](docs/web_implementation_plan.md) — Studio / API architecture
- [`docs/automation_plan.md`](docs/automation_plan.md) — queue, Beat, Telegram, discovery

**Ops health** (API must be running):

```bash
source venv/bin/activate
python scripts/check_ops.py
# or open Studio → Automation → Ops health
# or curl -s http://127.0.0.1:8000/api/ops/status | python -m json.tool
```

Suggested daily defaults: `interval_minutes=1440`, `min_queue_depth=3`,
`default_skip_video=true`, Gemini `daily_limit≈18` in `config.yaml`.

**Deferred:**
- Full-length video validation (keep `default_skip_video=true` until proven)
- YouTube OAuth upload
- Discord webhook / inbound Telegram commands (`/pause`, `/status`, …)
- RSS / Trends / YouTube popularity ranking for discovery v2+
