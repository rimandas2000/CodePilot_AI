"""Atomic JSON writes with unique, closed temporary files for Windows."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path


# Imported once per server process, shared across Streamlit reruns/sessions.
_WRITE_LOCK = threading.RLock()


def atomic_write_json(path: Path, data: dict) -> None:
    """Commit a complete JSON snapshot, or raise without truncating the old file.

    Each writer owns its temporary file. Close it before os.replace(), since
    Windows cannot rename an open file. Retry short-lived permission/sharing
    errors; genuine permission failures remain visible to the caller.
    """
    path = Path(path)
    with _WRITE_LOCK:
        payload = json.dumps(data, indent=2)
        for attempt in range(5):
            temporary = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=path.parent,
                    prefix=f".{path.name}.", suffix=".tmp", delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        # A scanner may still hold the file. Cleanup must not
                        # hide the original error or undo a successful commit.
                        pass
            time.sleep(0.05 * (2 ** attempt))
