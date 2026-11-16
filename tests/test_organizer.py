"""Tests mínimos para organizer.py (stdlib unittest, sin dependencias).

Se corren con:
    python -m unittest discover -s tests -v
"""
import logging
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from organizer import (  # noqa: E402
    DEFAULT_CONFIG,
    build_extension_map,
    default_exclude,
    load_config,
    OrganizerHandler,
    _watcher_config,
    organize_folder,
    prompt_conflict_mode,
    prompt_folder,
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


class RenameLogTests(unittest.TestCase):
    def test_rename_conflict_logs_final_name(self):
        """El log debe decir que hubo conflicto y con qué nombre quedó.

        Antes solo decía 'MOVIDO foto.jpg → Imágenes/' aunque el
        archivo real quedaba como foto_1.jpg.
        """
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger("test-rename-log")
        logger.setLevel(logging.DEBUG)
        logger.handlers = [_Capture()]
        logger.propagate = False

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Imágenes").mkdir()
            (folder / "Imágenes" / "foto.jpg").write_text("vieja")
            (folder / "foto.jpg").write_text("nueva")
            config = load_config(None)
            config["conflict"] = "rename"
            ext_map = build_extension_map(config["categories"])
            moved, _ = organize_folder(folder, config, ext_map, logger)

            self.assertEqual(moved, 1)
            self.assertTrue((folder / "Imágenes" / "foto_1.jpg").exists())
            self.assertTrue(
                any("CONFLICTO" in r and "foto_1.jpg" in r for r in records),
                f"falta el log de conflicto con el nombre final: {records}",
            )
            self.assertTrue(
                any("MOVIDO" in r and "Imágenes/foto_1.jpg" in r for r in records),
                f"el log MOVIDO debe incluir el nombre final: {records}",
            )


class CliPromptTests(unittest.TestCase):
    def test_prompt_folder_accepts_typed_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with mock.patch("organizer.input", return_value=str(folder)):
                self.assertEqual(prompt_folder(Path("/no/existe")), folder)

    def test_prompt_folder_empty_accepts_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with mock.patch("organizer.input", return_value=""):
                self.assertEqual(prompt_folder(folder), folder)

    def test_prompt_folder_reasks_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with mock.patch(
                "organizer.input",
                side_effect=["/no/existe/seguro", str(folder)],
            ):
                self.assertEqual(prompt_folder(folder), folder)

    def test_prompt_folder_eof_exits_without_organizing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("organizer.input", side_effect=EOFError):
                with self.assertRaises(SystemExit):
                    prompt_folder(Path(tmp))

    def test_prompt_conflict_mode_accepts_typed_mode(self):
        with mock.patch("organizer.input", return_value="rename"):
            self.assertEqual(prompt_conflict_mode("ask"), "rename")

    def test_prompt_conflict_mode_empty_keeps_default(self):
        with mock.patch("organizer.input", return_value=""):
            self.assertEqual(prompt_conflict_mode("ask"), "ask")

    def test_prompt_conflict_mode_reasks_when_invalid(self):
        with mock.patch(
            "organizer.input", side_effect=["typo", "skip"]
        ):
            self.assertEqual(prompt_conflict_mode("ask"), "skip")

    def test_prompt_conflict_mode_eof_exits(self):
        with mock.patch("organizer.input", side_effect=EOFError):
            with self.assertRaises(SystemExit):
                prompt_conflict_mode("ask")

    def test_main_prompts_even_when_stdin_is_not_a_tty(self):
        """El Run de un IDE (stdin por tubería) también debe preguntar.

        Antes, el candado isatty() hacía que sin terminal se fuera
        directo a Descargas sin preguntar nada.
        """
        repo = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            downloads = home / "Downloads"
            downloads.mkdir(parents=True)
            (downloads / "decoy.txt").write_text("decoy")
            chosen = Path(tmp) / "elegida"
            chosen.mkdir()
            (chosen / "foto.jpg").write_text("x")
            env = dict(os.environ, HOME=str(home))
            result = subprocess.run(
                [sys.executable, str(repo / "organizer.py")],
                input=f"{chosen}\nrename\n",
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Carpeta a organizar", result.stdout)
            self.assertTrue((chosen / "Imágenes" / "foto.jpg").exists())
            # Descargas quedó intacta: el decoy no se movió
            self.assertTrue((downloads / "decoy.txt").exists())

    def test_main_eof_exits_without_organizing(self):
        repo = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            downloads = home / "Downloads"
            downloads.mkdir(parents=True)
            (downloads / "decoy.txt").write_text("decoy")
            env = dict(os.environ, HOME=str(home))
            result = subprocess.run(
                [sys.executable, str(repo / "organizer.py")],
                input="",
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Operación cancelada", result.stdout + result.stderr)
            self.assertTrue((downloads / "decoy.txt").exists())

    def test_main_no_prompt_uses_downloads_without_asking(self):
        repo = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            downloads = home / "Downloads"
            downloads.mkdir(parents=True)
            (downloads / "decoy.txt").write_text("decoy")
            env = dict(os.environ, HOME=str(home))
            result = subprocess.run(
                [sys.executable, str(repo / "organizer.py"), "--no-prompt"],
                input="",
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Carpeta a organizar", result.stdout)
            self.assertTrue((downloads / "Documentos" / "decoy.txt").exists())


class WatcherConfigTests(unittest.TestCase):
    def _capturing_logger(self):
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger("test-watcher-config")
        logger.setLevel(logging.DEBUG)
        logger.handlers = [_Capture()]
        logger.propagate = False
        return logger, records

    def test_watcher_replaces_ask_with_rename(self):
        config = load_config(None)
        config["conflict"] = "ask"
        logger, records = self._capturing_logger()
        watcher_config = _watcher_config(config, logger)
        self.assertEqual(watcher_config["conflict"], "rename")
        # La config original no se toca: 'ask' sigue para una sola vez
        self.assertEqual(config["conflict"], "ask")
        self.assertTrue(any("rename" in r for r in records))

    def test_watcher_keeps_other_modes(self):
        for mode in ("rename", "skip", "overwrite"):
            config = load_config(None)
            config["conflict"] = mode
            logger, records = self._capturing_logger()
            watcher_config = _watcher_config(config, logger)
            self.assertEqual(watcher_config["conflict"], mode)
            self.assertFalse(any("rename" in r for r in records))

    def test_watcher_handler_renames_without_asking(self):
        """Con la config del watcher, un conflicto no llama a input().

        Antes, con 'ask', process_pending() moría con EOFError en
        la GUI/.exe (sin consola) y el watcher se detenía entero.
        """
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger("test-watcher-handler")
        logger.setLevel(logging.DEBUG)
        logger.handlers = [_Capture()]
        logger.propagate = False

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Imágenes").mkdir()
            (folder / "Imágenes" / "foto.jpg").write_text("vieja")
            src = folder / "foto.jpg"
            src.write_text("nueva")
            config = load_config(None)
            config["conflict"] = "ask"
            ext_map = build_extension_map(config["categories"])
            handler = OrganizerHandler(
                folder, _watcher_config(config, logger), ext_map, logger
            )
            handler._pending[str(src)] = time.time() - 10
            # Si algo intentara preguntar, esto lo delataría con EOFError
            with mock.patch("organizer.input", side_effect=EOFError):
                handler.process_pending()
            self.assertTrue((folder / "Imágenes" / "foto_1.jpg").exists())
            self.assertFalse(src.exists())
            self.assertTrue(
                any("CONFLICTO" in r and "foto_1.jpg" in r for r in records),
                f"falta el log de conflicto: {records}",
            )


if __name__ == "__main__":
    unittest.main()
