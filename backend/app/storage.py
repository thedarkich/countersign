"""Create private request artifacts without overwriting files or leaving partial writes."""

import os
from pathlib import Path


def write_private_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Set permissions at creation, not after writing invoice contents. Keep open
    # outside the cleanup block: an existing file must never be removed on failure.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(data)
        finally:
            os.close(descriptor)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
