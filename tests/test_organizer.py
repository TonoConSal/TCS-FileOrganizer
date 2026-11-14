"""Tests mínimos para organizer.py (stdlib unittest, sin dependencias).

Se corren con:
    python -m unittest discover -s tests -v
"""
import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from organizer import (  # noqa: E402
    DEFAULT_CONFIG,
    build_extension_map,
    default_exclude,
    load_config,
    organize_folder,
    resolve_conflict,
    unique_path,
    validate_config,
)


def _logger():
    logger = logging.getLogger("test-organizer")
    logger.setLevel(logging.CRITICAL)
    return logger


class UniquePathTests(unittest.TestCase):
    def test_compound_suffix_tar_gz(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "archive.tar.gz").write_text("x")
            result = unique_path(folder / "archive.tar.gz")
            self.assertEqual(result.name, "archive_1.tar.gz")

    def test_year_suffix_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "report_2024.pdf").write_text("x")
            result = unique_path(folder / "report_2024.pdf")
            self.assertEqual(result.name, "report_2024_1.pdf")

    def test_compound_suffix_tar_bz2(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "archive.tar.bz2").write_text("x")
            result = unique_path(folder / "archive.tar.bz2")
            self.assertEqual(result.name, "archive_1.tar.bz2")

    def test_compound_suffix_uppercase(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "archive.TAR.GZ").write_text("x")
            result = unique_path(folder / "archive.TAR.GZ")
            self.assertEqual(result.name, "archive_1.TAR.GZ")

    def test_dotted_name_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "my.file.pdf").write_text("x")
            result = unique_path(folder / "my.file.pdf")
            self.assertEqual(result.name, "my.file_1.pdf")

    def test_dotted_name_with_date_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "backup.2024-01-01.zip").write_text("x")
            result = unique_path(folder / "backup.2024-01-01.zip")
            self.assertEqual(result.name, "backup.2024-01-01_1.zip")

    def test_legitimate_numeric_suffix_is_preserved(self):
        # "_1" puede ser parte legítima del nombre original, no un
        # contador generado: no se interpreta ni se quita.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "foto_1.jpg").write_text("x")
            result = unique_path(folder / "foto_1.jpg")
            self.assertEqual(result.name, "foto_1_1.jpg")

    def test_legitimate_numeric_suffix_increments_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "foto_1.jpg").write_text("x")
            (folder / "foto_1_1.jpg").write_text("x")
            result = unique_path(folder / "foto_1.jpg")
            self.assertEqual(result.name, "foto_1_2.jpg")


class ConflictTests(unittest.TestCase):
    def test_invalid_mode_raises_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            src = folder / "a.txt"
            dst = folder / "b.txt"
            src.write_text("nuevo")
            dst.write_text("existente")
            with self.assertRaises(ValueError):
                resolve_conflict(src, dst, "typo", _logger())
            # El archivo existente no se tocó
            self.assertEqual(dst.read_text(), "existente")

    def test_validate_config_rejects_invalid_mode(self):
        config = load_config(None)
        config["conflict"] = "typo"
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_validate_config_rejects_list_conflict(self):
        # Un valor no hashable no debe lanzar TypeError, sino ValueError.
        config = load_config(None)
        config["conflict"] = ["rename"]
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_validate_config_rejects_dict_conflict(self):
        config = load_config(None)
        config["conflict"] = {"mode": "rename"}
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_validate_config_rejects_missing_log_file(self):
        config = load_config(None)
        del config["log_file"]
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_validate_config_rejects_empty_log_file(self):
        config = load_config(None)
        config["log_file"] = "   "
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_default_exclude_without_log_file_does_not_raise(self):
        # default_exclude() no debe lanzar KeyError: excluye scripts y
        # config, y simplemente no excluye ningún log.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = load_config(None)
            del config["log_file"]
            excluded = default_exclude(folder, config)
            self.assertIn((Path(__file__).resolve().parent.parent / "organizer.py").resolve(), excluded)
            self.assertIn((Path(__file__).resolve().parent.parent / "organizer_gui.py").resolve(), excluded)
            self.assertNotIn((folder / "organizer.log").resolve(), excluded)


class OrganizeFolderTests(unittest.TestCase):
    def test_log_file_is_not_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "organizer.log").write_text("log")
            (folder / "foto.jpg").write_text("x")
            config = load_config(None)
            ext_map = build_extension_map(config["categories"])
            moved, _ = organize_folder(
                folder, config, ext_map, _logger(),
                exclude=frozenset({(folder / "organizer.log").resolve()}),
            )
            self.assertTrue((folder / "organizer.log").exists())
            self.assertFalse((folder / "Otros" / "organizer.log").exists())
            self.assertTrue((folder / "Imágenes" / "foto.jpg").exists())
            self.assertEqual(moved, 1)

    def test_default_exclude_covers_log_config_and_scripts(self):
        """El helper compartido por CLI y GUI: log, config y scripts propios."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = load_config(None)
            cfg_path = folder / "mi_config.toml"
            cfg_path.write_text("")
            excluded = default_exclude(folder, config, cfg_path)
            self.assertIn((folder / "organizer.log").resolve(), excluded)
            self.assertIn(cfg_path.resolve(), excluded)
            self.assertIn((Path(__file__).resolve().parent.parent / "organizer.py").resolve(), excluded)
            self.assertIn((Path(__file__).resolve().parent.parent / "organizer_gui.py").resolve(), excluded)

    def test_default_exclude_keeps_log_in_place_via_gui_path(self):
        """Lo mismo que haría la GUI: organize_folder con default_exclude."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "organizer.log").write_text("log")
            (folder / "foto.jpg").write_text("x")
            config = load_config(None)
            ext_map = build_extension_map(config["categories"])
            moved, _ = organize_folder(
                folder, config, ext_map, _logger(),
                exclude=default_exclude(folder, config),
            )
            self.assertTrue((folder / "organizer.log").exists())
            self.assertFalse((folder / "Otros" / "organizer.log").exists())
            self.assertEqual(moved, 1)


if __name__ == "__main__":
    unittest.main()
