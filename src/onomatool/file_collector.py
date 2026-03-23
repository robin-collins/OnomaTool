"""File collection via glob pattern matching."""

import glob
import logging
import os

logger = logging.getLogger(__name__)


def collect_files(pattern: str) -> list[str]:
    """
    Collect files matching the given glob pattern.

    Only regular files are returned; symlinks, directories, FIFOs,
    sockets, and broken symlinks are filtered out with a warning.

    Args:
        pattern: Glob pattern to match files

    Returns:
        List of file paths matching the pattern
    """
    matches = glob.glob(pattern, recursive=True)
    result = []
    for path in matches:
        if os.path.isfile(path):
            result.append(path)
        else:
            logger.warning("Skipping non-regular file: %s", path)
    return result
