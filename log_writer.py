#!/usr/bin/env python3
import os
import json
import time
import datetime as dt
from typing import Dict, Any, Iterable


LOG_DIR = "/data/logs"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _jsonl_path(prefix: str, ts: dt.datetime) -> str:
    if prefix == "hourly":
        return os.path.join(LOG_DIR, f"hourly_{ts:%Y%m%d}.jsonl")
    if prefix == "nowcast":
        return os.path.join(LOG_DIR, f"nowcast_{ts:%Y%m%d}.jsonl")
    if prefix == "daily":
        return os.path.join(LOG_DIR, f"daily_{ts:%Y}.jsonl")
    return os.path.join(LOG_DIR, f"{prefix}_{ts:%Y%m%d}.jsonl")


def append_jsonl(prefix: str, record: Dict[str, Any], ts_field: str = "ts_utc") -> None:
    ensure_dir(LOG_DIR)
    # Choose date by record timestamp (or today if missing)
    try:
        ts = dt.datetime.fromisoformat(str(record.get(ts_field, "")).replace("Z", "+00:00"))
    except Exception:
        ts = dt.datetime.utcnow()
    path = _jsonl_path(prefix, ts)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def cleanup_logs(retention_days: int) -> None:
    if retention_days <= 0:
        return
    ensure_dir(LOG_DIR)
    now = time.time()
    for name in os.listdir(LOG_DIR):
        p = os.path.join(LOG_DIR, name)
        try:
            st = os.stat(p)
            age_days = (now - st.st_mtime) / 86400.0
            if age_days > retention_days:
                os.remove(p)
        except Exception:
            continue

