#!/usr/bin/env python3
"""
duplicate_finder.py — Find and optionally delete duplicate files in a directory.

Usage:
    python duplicate_finder.py [directory] [options]

Options:
    --delete      Automatically delete all duplicate files (keeps one copy of each).
    --dry-run     Show what would be deleted without actually deleting anything.
    --interactive Prompt before deleting each group of duplicates (default behaviour
                  when --delete is not specified).
    --min-size N  Skip files smaller than N bytes (default: 1).
    --help        Show this help message.
"""

import argparse
import hashlib
import os
import sys
from collections import defaultdict


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

CHUNK_SIZE = 65536  # 64 KiB


def _hash_file(path: str) -> str | None:
    """Return the MD5 hex-digest of *path*, or None on error."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as fh:
            while chunk := fh.read(CHUNK_SIZE):
                h.update(chunk)
    except (OSError, PermissionError) as exc:
        print(f"  [warning] cannot read '{path}': {exc}", file=sys.stderr)
        return None
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_duplicates(directory: str, min_size: int = 1) -> dict[str, list[str]]:
    """
    Walk *directory* recursively and return a mapping of
    ``md5_hex -> [path1, path2, ...]`` for every hash that appears more than once.

    Files smaller than *min_size* bytes are skipped.
    """
    size_map: dict[int, list[str]] = defaultdict(list)

    for dirpath, _dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                size = os.path.getsize(filepath)
            except OSError:
                continue
            if size >= min_size:
                size_map[size].append(filepath)

    # Only hash files that share a size with at least one other file
    hash_map: dict[str, list[str]] = defaultdict(list)
    for paths in size_map.values():
        if len(paths) < 2:
            continue
        for path in paths:
            digest = _hash_file(path)
            if digest is not None:
                hash_map[digest].append(path)

    return {digest: paths for digest, paths in hash_map.items() if len(paths) > 1}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def print_duplicates(duplicates: dict[str, list[str]]) -> None:
    """Print all duplicate groups to stdout."""
    if not duplicates:
        print("No duplicate files found.")
        return

    total_wasted = 0
    for i, (digest, paths) in enumerate(duplicates.items(), start=1):
        size = os.path.getsize(paths[0])
        wasted = size * (len(paths) - 1)
        total_wasted += wasted
        print(f"\nGroup {i}  [{digest[:8]}…]  {_human_size(size)} each"
              f"  — {len(paths)} copies  ({_human_size(wasted)} wasted)")
        for j, path in enumerate(paths):
            marker = "  KEEP " if j == 0 else "  DUP  "
            print(f"    {marker} {path}")

    print(f"\nTotal duplicates: {sum(len(p) - 1 for p in duplicates.values())} file(s)"
          f"  /  {_human_size(total_wasted)} wasted")


# ---------------------------------------------------------------------------
# Deletion helpers
# ---------------------------------------------------------------------------

def _delete_file(path: str, dry_run: bool) -> bool:
    """Delete *path* (or just print what would be deleted in dry-run mode).
    Returns True on success / would-succeed."""
    if dry_run:
        print(f"    [dry-run] would delete: {path}")
        return True
    try:
        os.remove(path)
        print(f"    Deleted: {path}")
        return True
    except OSError as exc:
        print(f"    [error] could not delete '{path}': {exc}", file=sys.stderr)
        return False


def delete_duplicates(duplicates: dict[str, list[str]], dry_run: bool = False) -> int:
    """
    For every duplicate group keep the *first* path and delete the rest.
    Returns the number of files deleted (or that would be deleted in dry-run mode).
    """
    deleted = 0
    for digest, paths in duplicates.items():
        keep = paths[0]
        print(f"\n  Keeping: {keep}")
        for path in paths[1:]:
            if _delete_file(path, dry_run):
                deleted += 1
    return deleted


def interactive_delete(duplicates: dict[str, list[str]], dry_run: bool = False) -> int:
    """
    Walk through each duplicate group and ask the user which file to keep.
    Returns the number of files deleted.
    """
    if not duplicates:
        return 0

    deleted = 0
    for i, (digest, paths) in enumerate(duplicates.items(), start=1):
        size = os.path.getsize(paths[0])
        print(f"\nGroup {i} of {len(duplicates)}  [{digest[:8]}…]  {_human_size(size)} each")
        for j, path in enumerate(paths):
            print(f"  [{j + 1}] {path}")
        print(f"  [a] Keep all  [s] Skip")

        while True:
            choice = input("  Which file to KEEP? (number / a / s): ").strip().lower()
            if choice == "s":
                print("  Skipped.")
                break
            if choice == "a":
                print("  Keeping all copies.")
                break
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(paths):
                    keep = paths[idx]
                    to_delete = [p for j, p in enumerate(paths) if j != idx]
                    print(f"  Keeping: {keep}")
                    for path in to_delete:
                        if _delete_file(path, dry_run):
                            deleted += 1
                    break
            print("  Invalid choice, please try again.")

    return deleted


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Find and optionally delete duplicate files in a directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--delete",
        action="store_true",
        help="Automatically delete all duplicates (keep first occurrence of each).",
    )
    mode.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for each group to choose which copy to keep (default).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting anything.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        metavar="N",
        help="Skip files smaller than N bytes (default: 1).",
    )

    args = parser.parse_args(argv)

    directory = os.path.abspath(args.directory)
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        return 1

    print(f"Scanning '{directory}' …")
    duplicates = find_duplicates(directory, min_size=args.min_size)

    if not duplicates:
        print("No duplicate files found.")
        return 0

    print_duplicates(duplicates)

    if args.delete:
        print("\n--- Deleting duplicates (keeping first copy of each) ---")
        deleted = delete_duplicates(duplicates, dry_run=args.dry_run)
    else:
        # Default: interactive mode
        print("\n--- Interactive deletion ---")
        deleted = interactive_delete(duplicates, dry_run=args.dry_run)

    label = "Would delete" if args.dry_run else "Deleted"
    print(f"\n{label} {deleted} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
