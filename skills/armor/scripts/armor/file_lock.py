"""Stdlib-only cross-platform exclusive file locking and atomic write helpers."""

from __future__ import annotations

import contextlib
import os
import tempfile
import threading
from pathlib import Path
from typing import Iterator

try:
    import msvcrt  # type: ignore[import-not-found]
except ImportError:
    msvcrt = None  # type: ignore[assignment]

try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:
    fcntl = None  # type: ignore[assignment]

_INPROC_LOCK_REGISTRY: dict[str, threading.Lock] = {}
_REGISTRY_GUARD = threading.Lock()


def _inproc_lock(key: str) -> threading.Lock:
    with _REGISTRY_GUARD:
        lock = _INPROC_LOCK_REGISTRY.get(key)
        if lock is None:
            lock = threading.Lock()
            _INPROC_LOCK_REGISTRY[key] = lock
        return lock


def _lock_path_for(target: Path) -> Path:
    resolved = target.resolve()
    safe_name = resolved.name.replace(":", "_")
    return resolved.parent / f"{safe_name}.lock"


@contextlib.contextmanager
def exclusive_lock(target: Path | str) -> Iterator[None]:
    """Acquire an in-process and cross-process exclusive lock on a sibling .lock file."""
    target_path = Path(target).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file_path = _lock_path_for(target_path)
    inproc = _inproc_lock(str(lock_file_path))

    with inproc:
        f = open(lock_file_path, "a+b")
        try:
            f.seek(0)
            if f.tell() == 0:
                f.write(b"\0")
                f.flush()
            f.seek(0)
            if msvcrt is not None:
                for attempt in range(600):
                    try:
                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                        break
                    except OSError:
                        if attempt == 599:
                            raise
            elif fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if msvcrt is not None:
                    try:
                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                elif fcntl is not None:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        finally:
            f.close()


def locked_write(path: Path | str, text: str, encoding: str = "utf-8") -> None:
    """Atomically write text to path under exclusive_lock."""
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(target):
        fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding=encoding) as tmp_file:
                tmp_file.write(text)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_name, target)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def locked_append(path: Path | str, text: str, encoding: str = "utf-8") -> None:
    """Append text to path under exclusive_lock and fsync."""
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(target):
        with open(target, "a", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
