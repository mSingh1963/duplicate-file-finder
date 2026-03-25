# duplicate-file-finder

A command-line tool that scans a directory for duplicate files and lets you delete them — keeping one copy of each.

## Requirements

- Python 3.10 or later (uses union type syntax `X | Y` from 3.10+)

## Installation

No extra dependencies needed — the script uses only the Python standard library.

```bash
git clone https://github.com/mSingh1963/duplicate-file-finder.git
cd duplicate-file-finder
```

## Usage

```
python duplicate_finder.py [directory] [options]
```

| Argument / flag | Description |
|---|---|
| `directory` | Directory to scan (default: current directory) |
| `--delete` | Automatically delete all duplicates, keeping the first copy found |
| `--interactive` | Prompt for each group to choose which copy to keep (default) |
| `--dry-run` | Preview what would be deleted without actually removing files |
| `--min-size N` | Skip files smaller than N bytes (default: 1) |

### Examples

**Find duplicates (display only):**
```bash
python duplicate_finder.py ~/Downloads
```

**Interactive deletion — choose which copy to keep:**
```bash
python duplicate_finder.py ~/Downloads --interactive
```

**Automatically delete all duplicates (dry run first to be safe):**
```bash
python duplicate_finder.py ~/Downloads --delete --dry-run
python duplicate_finder.py ~/Downloads --delete
```

**Ignore files smaller than 1 KB:**
```bash
python duplicate_finder.py ~/Downloads --delete --min-size 1024
```

## How it works

1. All files in the target directory are grouped by **file size** — files with unique sizes cannot be duplicates.
2. For each size group with more than one file, an **MD5 hash** of the full file content is computed.
3. Files that share the same hash are reported as duplicates.
4. You can then delete the extras interactively or automatically.

## Running tests

```bash
python -m pytest test_duplicate_finder.py -v
```
