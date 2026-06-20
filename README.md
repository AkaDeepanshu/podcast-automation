# Podcast Automation — Phase 1 (Script Generation + TTS)

Current scope: `topic` → structured two-speaker dialogue script (Gemini) →
per-line synthesized audio (Kokoro, free/local).

**Not yet built:** audio assembly into one file, video muxing, topic
queue/auto-generation, cron wrapper. This is Phase 1 of the full plan —
script + TTS only, as requested.

---

## 1. Setup

### 1.1 Install dependencies

```bash
cd podcast-automation
pip install -r requirements.txt --break-system-packages
```

Kokoro also needs `espeak-ng` as a system dependency:

```bash
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y espeak-ng

# macOS
brew install espeak-ng
```

### 1.2 Get a Gemini API key

Free tier, generous limits: https://aistudio.google.com/apikey

```bash
export GEMINI_API_KEY="your-key-here"
```

Add this to your `~/.bashrc` / `~/.zshrc` so you don't have to re-export it
every session.

### 1.3 First Kokoro run will download model weights

The first time `KokoroTTSEngine` runs, it downloads the model (~few hundred
MB) from Hugging Face Hub automatically. Needs internet once; runs fully
offline after that. No extra setup needed — just don't be surprised by the
first-run delay.

---

## 2. Usage

### Run a new episode end-to-end (script + TTS)

```bash
python run_pipeline.py --topic "The history of mechanical keyboards"
```

This will:
1. Generate an outline (6 segments by default, see `config/config.yaml`)
2. Generate dialogue chunk-by-chunk for each segment
3. Write `jobs/{job_id}/01_outline.json` and `02_script.json`
4. Synthesize each dialogue line as a separate `.wav` file under
   `jobs/{job_id}/03_audio_lines/`

### Resuming a failed/interrupted job

If the process crashes or a TTS line fails partway through, just re-run
with the same job ID:

```bash
python run_pipeline.py --resume 20260619_the-history-of-mechanical-keyb_a1b2c3
```

It will skip any already-completed stage/lines and only redo what's
missing or failed. Job IDs are printed at the start of each run and are
also the folder name under `jobs/`.

### Custom job ID

```bash
python run_pipeline.py --topic "..." --job-id my-episode-01
```

---

## 3. Output structure

```
jobs/{job_id}/
├── 01_outline.json       # segment-by-segment outline
├── 02_script.json        # full dialogue script, structured
└── 03_audio_lines/
    ├── line_0000_A.wav
    ├── line_0001_B.wav
    ├── line_0002_A.wav
    └── ...
```

`02_script.json` format:
```json
[
  {"speaker": "A", "text": "...", "emotion": "curious", "segment_index": 1, "line_index": 0},
  {"speaker": "B", "text": "...", "emotion": "thoughtful", "segment_index": 1, "line_index": 1}
]
```

---

## 4. Configuration

- `config/config.yaml` — provider selection, episode length/segment count,
  Gemini params, Kokoro params, anti-repetition filler-phrase list
- `config/speakers.yaml` — speaker names, personas, voice IDs. Keep these
  stable across episodes for channel identity. Available Kokoro voices:
  https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md

To swap providers later (e.g. to paid Claude/ElevenLabs), you'll only
need to: (1) write a new class implementing `ScriptGenerator` or
`TTSEngine` in `core/providers/`, (2) register it in
`core/provider_factory.py`, (3) flip the value in `config.yaml`. Nothing
in `run_pipeline.py` or the pipeline stages needs to change.

---

## 5. Troubleshooting

**"GEMINI_API_KEY not set"** — export it (see §1.2). The pipeline fails
fast with a clear error rather than partially running.

**A TTS line keeps failing** — check `logs/{job_id}.log` for the specific
error. Common cause: unusual characters/symbols in generated text that
Kokoro's phonemizer chokes on. You can manually inspect/edit
`jobs/{job_id}/02_script.json` and delete the job's row from `state/jobs.db`
`tts_lines` table for that line index, then `--resume`.

**Script generation feels repetitive** — tune
`script_generation.forbidden_phrases` in `config.yaml`, or increase
`num_segments` (more, shorter chunks = more variation), or raise
`temperature` slightly.

**Checking job status without re-running:**
```python
from core.state_db import JobStateDB
db = JobStateDB("state/jobs.db")
print(db.get_job("your-job-id"))
print(db.get_all_stages("your-job-id"))
```

---

## 6. Next steps (not yet built)

- Audio assembly stage (pauses, loudness normalization, concatenation into
  one file)
- Video muxing (ffmpeg, static image or waveform + final audio)
- Topic queue / auto-topic-generation
- Cron wrapper with locking + failure notification

Say the word when you want to move to the next stage.
