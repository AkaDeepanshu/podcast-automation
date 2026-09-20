#!/usr/bin/env python3
"""Print ops status for local Studio stack. Run from repo root with venv active."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"


def main() -> int:
    url = f"{API}/api/ops/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"FAIL  API unreachable at {url}")
        print(f"      {exc}")
        print("      Start: uvicorn backend.main:app --reload --port 8000")
        return 1

    ok = data.get("ok")
    print("OK" if ok else "WARN", "— ops status")
    print(f"  redis:      {'ok' if data.get('redis_ok') else 'DOWN'}")
    print(f"  workers:    {data.get('workers_online')} {data.get('worker_names') or ''}")
    print(f"  telegram:   {'yes' if data.get('telegram_configured') else 'no'}")
    print(f"  automation: {'on' if data.get('automation_enabled') else 'off'}")
    print(
        f"  queue:       approved={data.get('approved_queue_depth')} "
        f"buffer={data.get('buffer_queue_depth')} "
        f"min={data.get('min_queue_depth')}"
    )
    print(f"  lock:       {'held' if data.get('lock_held') else 'free'}")
    print(f"  last_tick:  {data.get('last_tick_at') or '—'}")
    print(f"  last_run:   {data.get('last_run_at') or '—'}")
    if data.get("last_error"):
        print(f"  last_error: {data['last_error']}")
    q = data.get("gemini_quota") or {}
    if q:
        print(
            f"  gemini:     {q.get('used_today')}/{q.get('daily_limit')} "
            f"(need headroom {q.get('headroom_needed')})"
            + (" NEAR LIMIT" if q.get("near_limit") else "")
        )
    for line in data.get("recommendations") or []:
        print(f"  → {line}")
    print()
    print(data.get("beat_hint", ""))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
