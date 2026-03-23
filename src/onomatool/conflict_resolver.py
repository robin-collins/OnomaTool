import os

from onomatool.exceptions import OnomaConflictError

MAX_CONFLICT_ITERATIONS = 10_000


def resolve_conflict(desired_name: str, existing_names: list[str]) -> str:
    """
    Resolve naming conflicts by appending a numeric suffix.

    Args:
        desired_name: The desired base name for the file
        existing_names: List of existing file names in the target directory

    Returns:
        A unique file name by appending a numeric suffix if needed

    Raises:
        RuntimeError: If no unique name found within MAX_CONFLICT_ITERATIONS
    """
    existing_set = set(existing_names)
    if desired_name not in existing_set:
        return desired_name

    base, ext = os.path.splitext(desired_name)
    for counter in range(2, MAX_CONFLICT_ITERATIONS + 2):
        new_name = f"{base}_{counter}{ext}"
        if new_name not in existing_set:
            return new_name

    raise OnomaConflictError(
        f"Could not resolve filename conflict for '{desired_name}' "
        f"after {MAX_CONFLICT_ITERATIONS} attempts"
    )
