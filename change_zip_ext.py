#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import zipfile
from typing import Iterable, List, Set
import glob


def is_zip_file(path: Path) -> bool:
    """Return True if the file is a valid ZIP archive."""
    try:
        return zipfile.is_zipfile(path)
    except Exception:
        return False


def ensure_dot_prefix(ext: str) -> str:
    """Normalize extension to start with a dot, like '.ben'."""
    ext = ext.strip()
    if not ext:
        raise ValueError("Extension cannot be empty.")
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def next_available_path(target: Path) -> Path:
    """
    If `target` exists, find a non-conflicting path by appending -1, -2, ...
    Example: file.ben -> file-1.ben, file-2.ben, etc.
    """
    if not target.exists():
        return target
    i = 1
    while True:
        candidate = target.with_name(f"{target.stem}-{i}{target.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def safe_replace(src: Path, dst: Path, overwrite: bool = False) -> Path:
    """
    Cross-platform safe replace:
    - If overwrite=True, atomically replace dst when possible.
    - If overwrite=False and dst exists, pick a unique name.
    Returns the final destination path used.
    """
    dst = dst if overwrite else next_available_path(dst)
    # os.replace is atomic on most platforms and overwrites if exists.
    os.replace(src, dst)
    return dst


def change_extension(
    file_path: Path,
    new_extension: str = ".ben",
    *,
    verify_zip: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Change file extension of a ZIP file to `new_extension`.

    Returns (success, message).
    """
    if not file_path.is_file():
        return False, f"Skip: '{file_path}' is not a file."

    new_extension = ensure_dot_prefix(new_extension)

    if verify_zip and not is_zip_file(file_path):
        return False, f"Skip: '{file_path}' is not a valid ZIP (use --no-verify to force)."

    # Build destination by changing only the final suffix.
    dst = file_path.with_suffix(new_extension)

    if dry_run:
        exists_note = " (will overwrite)" if overwrite and dst.exists() else ""
        return True, f"Would rename: {file_path.name} -> {dst.name}{exists_note}"

    try:
        # Perform a rename; if overwrite is False and dst exists, we auto-suffix.
        final_dst = dst if overwrite else next_available_path(dst)
        # If overwrite True, do atomic replace
        if overwrite and dst.exists():
            os.replace(file_path, dst)
            return True, f"Renamed (overwrote): {file_path.name} -> {dst.name}"
        else:
            os.replace(file_path, final_dst)
            suffix_note = "" if final_dst == dst else f" (renamed to avoid conflict: {final_dst.name})"
            return True, f"Renamed: {file_path.name} -> {final_dst.name}{suffix_note}"
    except OSError as e:
        return False, f"Error renaming '{file_path}': {e}"


def expand_inputs(paths_or_patterns: Iterable[str]) -> List[Path]:
    """
    Expand a mix of literal paths and glob patterns into unique, existing Path objects.
    """
    seen: Set[Path] = set()
    results: List[Path] = []

    for item in paths_or_patterns:
        # Expand globs relative to repo/workdir
        matches = [Path(p) for p in glob.glob(item, recursive=True)]
        if not matches:
            # If no glob matches, treat as literal path
            p = Path(item)
            matches = [p]

        for p in matches:
            # Normalize path
            p = p.resolve() if p.exists() else p
            if p not in seen:
                seen.add(p)
                results.append(p)

    return results


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert .zip files to another extension (default .ben). Supports globs."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="File paths or glob patterns to process (e.g., uploads/*.zip).",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Glob pattern(s) of files to convert. Can be given multiple times.",
    )
    parser.add_argument(
        "--to",
        default=".ben",
        help="Target extension (default: .ben).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite destination if it exists. Without this, a numeric suffix is added.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Do not verify that the input files are ZIP archives.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes.",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    inputs = list(args.paths) + list(args.pattern)

    if not inputs:
        print("No inputs provided. Specify files or use --pattern.")
        return 2

    files = expand_inputs(inputs)

    if not files:
        print("No files matched the provided paths/patterns.")
        return 1

    overall_ok = True
    for f in files:
        ok, msg = change_extension(
            Path(f),
            args.to,
            verify_zip=not args.no_verify,
            overwrite=args.force,
            dry_run=args.dry_run,
        )
        print(msg)
        overall_ok = overall_ok and ok

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
