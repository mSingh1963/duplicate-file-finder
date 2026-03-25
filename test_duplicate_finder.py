"""
Tests for duplicate_finder.py
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from duplicate_finder import (
    delete_duplicates,
    find_duplicates,
    interactive_delete,
    main,
    _hash_file,
    _human_size,
)


class TestHashFile(unittest.TestCase):
    def test_same_content_same_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = os.path.join(tmpdir, "a.txt")
            b = os.path.join(tmpdir, "b.txt")
            content = b"hello world"
            with open(a, "wb") as f:
                f.write(content)
            with open(b, "wb") as f:
                f.write(content)
            self.assertEqual(_hash_file(a), _hash_file(b))

    def test_different_content_different_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = os.path.join(tmpdir, "a.txt")
            b = os.path.join(tmpdir, "b.txt")
            with open(a, "wb") as f:
                f.write(b"hello")
            with open(b, "wb") as f:
                f.write(b"world")
            self.assertNotEqual(_hash_file(a), _hash_file(b))

    def test_nonexistent_file_returns_none(self):
        result = _hash_file("/nonexistent/path/file.txt")
        self.assertIsNone(result)


class TestHumanSize(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(_human_size(512), "512.0 B")

    def test_kilobytes(self):
        self.assertEqual(_human_size(1024), "1.0 KB")

    def test_megabytes(self):
        self.assertEqual(_human_size(1024 * 1024), "1.0 MB")


class TestFindDuplicates(unittest.TestCase):
    def _make_file(self, directory, name, content):
        path = os.path.join(directory, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_finds_duplicate_pair(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "file1.txt", b"duplicate content")
            self._make_file(tmpdir, "file2.txt", b"duplicate content")
            self._make_file(tmpdir, "unique.txt", b"unique content xyz")

            dups = find_duplicates(tmpdir)
            self.assertEqual(len(dups), 1)
            paths = list(dups.values())[0]
            self.assertEqual(len(paths), 2)

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"aaa")
            self._make_file(tmpdir, "b.txt", b"bbb")

            dups = find_duplicates(tmpdir)
            self.assertEqual(dups, {})

    def test_three_copies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content = b"same same same"
            for name in ("x.txt", "y.txt", "z.txt"):
                self._make_file(tmpdir, name, content)

            dups = find_duplicates(tmpdir)
            self.assertEqual(len(dups), 1)
            paths = list(dups.values())[0]
            self.assertEqual(len(paths), 3)

    def test_min_size_skips_small_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"hi")  # 2 bytes
            self._make_file(tmpdir, "b.txt", b"hi")  # 2 bytes

            dups = find_duplicates(tmpdir, min_size=10)
            self.assertEqual(dups, {})

    def test_recursive_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            self._make_file(tmpdir, "root.txt", b"match me")
            self._make_file(subdir, "nested.txt", b"match me")

            dups = find_duplicates(tmpdir)
            self.assertEqual(len(dups), 1)

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dups = find_duplicates(tmpdir)
            self.assertEqual(dups, {})


class TestDeleteDuplicates(unittest.TestCase):
    def _make_file(self, directory, name, content):
        path = os.path.join(directory, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_deletes_duplicates_keeps_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = self._make_file(tmpdir, "a.txt", b"same")
            b = self._make_file(tmpdir, "b.txt", b"same")

            dups = find_duplicates(tmpdir)
            deleted = delete_duplicates(dups)

            self.assertEqual(deleted, 1)
            # Exactly one of the two files should remain
            remaining = [p for p in (a, b) if os.path.exists(p)]
            self.assertEqual(len(remaining), 1)

    def test_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"same")
            self._make_file(tmpdir, "b.txt", b"same")

            dups = find_duplicates(tmpdir)
            deleted = delete_duplicates(dups, dry_run=True)

            self.assertEqual(deleted, 1)
            # Both files should still exist
            self.assertEqual(len(os.listdir(tmpdir)), 2)


class TestInteractiveDelete(unittest.TestCase):
    def _make_file(self, directory, name, content):
        path = os.path.join(directory, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_interactive_keep_choice(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = self._make_file(tmpdir, "a.txt", b"dup")
            b = self._make_file(tmpdir, "b.txt", b"dup")

            dups = find_duplicates(tmpdir)
            # User types "1" — keeps the first path in the list, deletes the second.
            with patch("builtins.input", return_value="1"):
                deleted = interactive_delete(dups)

            self.assertEqual(deleted, 1)
            # Exactly one of the two files should exist after deletion.
            paths = list(dups.values())[0]
            kept = paths[0]
            dropped = paths[1]
            self.assertTrue(os.path.exists(kept))
            self.assertFalse(os.path.exists(dropped))

    def test_interactive_skip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"dup")
            self._make_file(tmpdir, "b.txt", b"dup")

            dups = find_duplicates(tmpdir)
            with patch("builtins.input", return_value="s"):
                deleted = interactive_delete(dups)

            self.assertEqual(deleted, 0)
            self.assertEqual(len(os.listdir(tmpdir)), 2)

    def test_interactive_keep_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"dup")
            self._make_file(tmpdir, "b.txt", b"dup")

            dups = find_duplicates(tmpdir)
            with patch("builtins.input", return_value="a"):
                deleted = interactive_delete(dups)

            self.assertEqual(deleted, 0)
            self.assertEqual(len(os.listdir(tmpdir)), 2)

    def test_interactive_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"dup")
            self._make_file(tmpdir, "b.txt", b"dup")

            dups = find_duplicates(tmpdir)
            with patch("builtins.input", return_value="1"):
                deleted = interactive_delete(dups, dry_run=True)

            self.assertEqual(deleted, 1)
            # Both files should still exist (dry run)
            self.assertEqual(len(os.listdir(tmpdir)), 2)


class TestMain(unittest.TestCase):
    def _make_file(self, directory, name, content):
        path = os.path.join(directory, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_main_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"aaa")
            self._make_file(tmpdir, "b.txt", b"bbb")
            result = main([tmpdir])
            self.assertEqual(result, 0)

    def test_main_delete_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"same")
            self._make_file(tmpdir, "b.txt", b"same")
            result = main([tmpdir, "--delete"])
            self.assertEqual(result, 0)
            remaining = os.listdir(tmpdir)
            self.assertEqual(len(remaining), 1)

    def test_main_dry_run_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"same")
            self._make_file(tmpdir, "b.txt", b"same")
            result = main([tmpdir, "--delete", "--dry-run"])
            self.assertEqual(result, 0)
            # Both files still present
            self.assertEqual(len(os.listdir(tmpdir)), 2)

    def test_main_invalid_directory(self):
        result = main(["/nonexistent/path/does/not/exist"])
        self.assertEqual(result, 1)

    def test_main_interactive_with_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_file(tmpdir, "a.txt", b"same")
            self._make_file(tmpdir, "b.txt", b"same")
            with patch("builtins.input", return_value="1"):
                result = main([tmpdir, "--interactive"])
            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
