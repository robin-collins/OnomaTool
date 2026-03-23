"""Cross-platform filename sanitization."""

import re

# Windows reserved characters
WINDOWS_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')

# Windows reserved names (case-insensitive)
WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

# Maximum filename length in bytes (ext4, NTFS, APFS all use 255)
MAX_FILENAME_BYTES = 255


def sanitize_filename(name: str) -> str:
    """Sanitize a filename for cross-platform compatibility.

    - Strips Windows-illegal characters (<>:"/\\|?*)
    - Rejects Windows reserved names (CON, PRN, etc.)
    - Enforces 255 byte max
    - Strips leading/trailing dots and spaces
    - Replaces control characters with underscores
    """
    # Replace illegal characters with underscore
    name = WINDOWS_ILLEGAL_CHARS.sub("_", name)

    # Replace control characters (0x00-0x1F)
    name = re.sub(r"[\x00-\x1f]", "_", name)

    # Replace Unicode fullwidth path separators (U+FF0F, U+FF3C)
    name = name.replace("\uff0f", "_").replace("\uff3c", "_")

    # Strip leading/trailing dots and spaces
    name = name.strip(". ")

    # Neutralize path traversal sequences after stripping
    name = name.replace("..", "_")

    # Handle Windows reserved names
    base_name = name.split(".")[0].upper()
    if base_name in WINDOWS_RESERVED_NAMES:
        name = f"_{name}"

    # Enforce byte length limit (truncate if needed, preserving extension)
    encoded = name.encode("utf-8")
    if len(encoded) > MAX_FILENAME_BYTES:
        # Find extension
        dot_idx = name.rfind(".")
        if dot_idx > 0:
            ext = name[dot_idx:]
            base = name[:dot_idx]
            max_base_bytes = MAX_FILENAME_BYTES - len(ext.encode("utf-8"))
            # Truncate base while keeping valid UTF-8
            base_encoded = base.encode("utf-8")[:max_base_bytes]
            base = base_encoded.decode("utf-8", errors="ignore")
            name = base + ext
        else:
            name = encoded[:MAX_FILENAME_BYTES].decode("utf-8", errors="ignore")

    # If empty after sanitization, use fallback
    if not name or name == ".":
        name = "unnamed"

    return name
