from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path


def atomic_write_text(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
    create_backup: bool = False,
) -> Path | None:
    """Atomically replace a text file and optionally preserve its previous version."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup_path = destination.with_suffix(destination.suffix + ".bak")
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)

        if destination.exists():
            previous_mode = stat.S_IMODE(destination.stat().st_mode)
            os.chmod(temp_path, previous_mode)
            if create_backup:
                shutil.copy2(destination, backup_path)

        os.replace(temp_path, destination)
        temp_path = None
        return backup_path if create_backup and backup_path.exists() else None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
