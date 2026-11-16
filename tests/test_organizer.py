"""Tests mínimos para organizer.py (stdlib unittest, sin dependencias).

Se corren con:
    python -m unittest discover -s tests -v
"""
import json
import logging
import os
import re
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
    __version__,
    UserCancelled,
    build_extension_map,
    default_exclude,
    default_log_dir,
    load_config,
    move_file,
    OrganizerHandler,
    resolve_log_path,
    _watcher_config,
    organize_folder,
    prompt_conflict_mode,
    prompt_folder,
    resolve_conflict,
    setup_logging,
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
        # config. Sin log_file no se excluye la ruta resuelta del log,
        # pero el organizer.log viejo de la carpeta sigue excluido por
        # compatibilidad (v2.5.1 y antes, cuando el log vivía ahí).
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = load_config(None)
            del config["log_file"]
            excluded = default_exclude(folder, config)
            self.assertIn((Path(__file__).resolve().parent.parent / "organizer.py").resolve(), excluded)
            self.assertIn((Path(__file__).resolve().parent.parent / "organizer_gui.py").resolve(), excluded)
            self.assertIn((folder / "organizer.log").resolve(), excluded)


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


class AskCallbackTests(unittest.TestCase):
    def _conflict_setup(self, tmp):
        folder = Path(tmp)
        (folder / "Imágenes").mkdir()
        (folder / "Imágenes" / "foto.jpg").write_text("vieja")
        (folder / "foto.jpg").write_text("nueva")
        return folder

    def test_ask_callback_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            result = resolve_conflict(src, dst, "ask", _logger(),
                                      on_conflict=lambda s, d: "rename")
            self.assertEqual(result.name, "foto_1.jpg")

    def test_ask_callback_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            result = resolve_conflict(src, dst, "ask", _logger(),
                                      on_conflict=lambda s, d: "overwrite")
            self.assertEqual(result, dst)

    def test_ask_callback_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            result = resolve_conflict(src, dst, "ask", _logger(),
                                      on_conflict=lambda s, d: "skip")
            self.assertIsNone(result)

    def test_ask_callback_cancel_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            with self.assertRaises(UserCancelled):
                resolve_conflict(src, dst, "ask", _logger(),
                                 on_conflict=lambda s, d: "cancel")

    def test_ask_callback_accepts_cli_letters(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            result = resolve_conflict(src, dst, "ask", _logger(),
                                      on_conflict=lambda s, d: "r")
            self.assertEqual(result.name, "foto_1.jpg")
            with self.assertRaises(UserCancelled):
                resolve_conflict(src, dst, "ask", _logger(),
                                 on_conflict=lambda s, d: "q")

    def test_ask_callback_invalid_choice_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            with self.assertRaises(ValueError):
                resolve_conflict(src, dst, "ask", _logger(),
                                 on_conflict=lambda s, d: "tal vez")

    def test_ask_callback_receives_src_and_dst(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            seen = []
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            resolve_conflict(src, dst, "ask", _logger(),
                             on_conflict=lambda s, d: seen.append((s, d)) or "skip")
            self.assertEqual(seen, [(src, dst)])

    def test_ask_console_fallback_still_works_without_callback(self):
        # Sin callback, el modo ask sigue preguntando por consola (CLI).
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            src = folder / "foto.jpg"
            dst = folder / "Imágenes" / "foto.jpg"
            with mock.patch("organizer.input", return_value="r"):
                result = resolve_conflict(src, dst, "ask", _logger())
            self.assertEqual(result.name, "foto_1.jpg")

    def test_ask_cancel_aborts_run_leaving_files_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            config = load_config(None)
            config["conflict"] = "ask"
            ext_map = build_extension_map(config["categories"])
            with self.assertRaises(UserCancelled):
                organize_folder(folder, config, ext_map, _logger(),
                                on_conflict=lambda s, d: "cancel")
            # Nada se movió: el archivo sigue en su lugar y el
            # destino no se tocó.
            self.assertTrue((folder / "foto.jpg").exists())
            self.assertEqual((folder / "Imágenes" / "foto.jpg").read_text(), "vieja")

    def test_ask_rename_via_callback_completes_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._conflict_setup(tmp)
            config = load_config(None)
            config["conflict"] = "ask"
            ext_map = build_extension_map(config["categories"])
            moved, _ = organize_folder(folder, config, ext_map, _logger(),
                                       on_conflict=lambda s, d: "rename")
            self.assertEqual(moved, 1)
            self.assertTrue((folder / "Imágenes" / "foto_1.jpg").exists())


class CliPromptTests(unittest.TestCase):
    def test_prompt_folder_accepts_typed_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Resuelto: prompt_folder() devuelve la ruta resuelta, y en
            # Windows el temporal puede venir en forma corta 8.3
            # (C:\Users\RUNNER~1\...) mientras resolve() devuelve la
            # forma larga (C:\Users\runneradmin\...). Comparar sin
            # resolver falla solo en ese entorno.
            folder = Path(tmp).resolve()
            with mock.patch("organizer.input", return_value=str(folder)):
                self.assertEqual(prompt_folder(Path("/no/existe")), folder)

    def test_prompt_folder_empty_accepts_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            with mock.patch("organizer.input", return_value=""):
                self.assertEqual(prompt_folder(folder), folder)

    def test_prompt_folder_reasks_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
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

    @staticmethod
    def _fake_home_env(home: Path) -> dict:
        """Entorno que redirige Path.home() en Linux y en Windows.

        En Linux, Path.home() usa HOME; en Windows lo ignora desde
        Python 3.8 y usa USERPROFILE (o HOMEDRIVE+HOMEPATH). Si solo
        se pone HOME, en Windows el programa organiza las Descargas
        reales del usuario en vez de la carpeta temporal del test.
        """
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
        drive, tail = os.path.splitdrive(str(home))
        if drive:
            env["HOMEDRIVE"] = drive
            env["HOMEPATH"] = tail or "\\"
        return env

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
            env = self._fake_home_env(home)
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
            env = self._fake_home_env(home)
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
            env = self._fake_home_env(home)
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
            self.assertTrue(
                (downloads / "Documentos" / "decoy.txt").exists(),
                "decoy no quedó en Documentos; contenido de Downloads: "
                f"{sorted(str(p.relative_to(downloads)) for p in downloads.rglob('*'))}",
            )


class LogDirTests(unittest.TestCase):
    def test_default_log_dir_uses_xdg_data_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": tmp}):
                self.assertEqual(default_log_dir(), Path(tmp) / "TCS-FileOrganizer")

    def test_default_log_dir_falls_back_to_local_share(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                os.environ.pop("XDG_DATA_HOME", None)
                # Path.home() usa HOME en Linux
                self.assertEqual(default_log_dir(), home / ".local" / "share" / "TCS-FileOrganizer")

    def test_resolve_log_path_relative_goes_to_default_dir(self):
        config = load_config(None)
        self.assertEqual(resolve_log_path(config), default_log_dir() / "organizer.log")

    def test_resolve_log_path_absolute_wins(self):
        config = load_config(None)
        config["log_file"] = "/tmp/mis-logs/otro.log"
        self.assertEqual(resolve_log_path(config), Path("/tmp/mis-logs/otro.log"))

    def test_resolve_log_path_without_log_file_uses_default(self):
        self.assertEqual(resolve_log_path({}), default_log_dir() / "organizer.log")
        self.assertEqual(resolve_log_path({"log_file": "   "}), default_log_dir() / "organizer.log")

    def test_setup_logging_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "a" / "b" / "organizer.log"
            logger = setup_logging(log_path)
            logger.info("hola")
            for handler in list(logger.handlers):
                handler.close()
            logger.handlers.clear()
            self.assertTrue(log_path.exists())
            self.assertIn("hola", log_path.read_text(encoding="utf-8"))

    def test_default_exclude_excludes_new_log_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            log_dir = Path(tmp) / "logs"
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(log_dir)}):
                config = load_config(None)
                excluded = default_exclude(folder, config)
                self.assertIn((log_dir / "TCS-FileOrganizer" / "organizer.log"), excluded)

    def test_main_prints_log_path_at_end(self):
        repo = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            downloads = home / "Downloads"
            downloads.mkdir(parents=True)
            (downloads / "decoy.txt").write_text("decoy")
            env = CliPromptTests._fake_home_env(home)
            env.pop("XDG_DATA_HOME", None)
            result = subprocess.run(
                [sys.executable, str(repo / "organizer.py"), "--no-prompt"],
                input="",
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Log guardado en:", result.stdout)
            self.assertIn("organizer.log", result.stdout)
            # El log ya no queda dentro de Downloads
            self.assertFalse((downloads / "organizer.log").exists())
            self.assertTrue((home / ".local" / "share" / "TCS-FileOrganizer" / "organizer.log").exists())


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


class WatcherDryRunTests(unittest.TestCase):
    def _capturing_logger(self):
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger("test-watcher-dry-run")
        logger.setLevel(logging.DEBUG)
        logger.handlers = [_Capture()]
        logger.propagate = False
        return logger, records

    def test_handler_dry_run_does_not_move(self):
        logger, records = self._capturing_logger()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            src = folder / "foto.jpg"
            src.write_text("x")
            config = load_config(None)
            config["conflict"] = "rename"
            ext_map = build_extension_map(config["categories"])
            handler = OrganizerHandler(folder, config, ext_map, logger, dry_run=True)
            handler._pending[str(src)] = time.time() - 10
            handler.process_pending()
            self.assertTrue(src.exists(), "dry-run no debe mover el archivo")
            self.assertFalse((folder / "Imágenes").exists())
            self.assertTrue(any("[DRY-RUN]" in r for r in records))

    def test_handler_dry_run_conflict_logs_would_be_name(self):
        logger, records = self._capturing_logger()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Imágenes").mkdir()
            (folder / "Imágenes" / "foto.jpg").write_text("vieja")
            src = folder / "foto.jpg"
            src.write_text("nueva")
            config = load_config(None)
            config["conflict"] = "rename"
            ext_map = build_extension_map(config["categories"])
            handler = OrganizerHandler(folder, config, ext_map, logger, dry_run=True)
            handler._pending[str(src)] = time.time() - 10
            handler.process_pending()
            self.assertTrue(src.exists())
            self.assertEqual((folder / "Imágenes" / "foto.jpg").read_text(), "vieja")
            self.assertTrue(
                any("[DRY-RUN] CONFLICTO" in r and "foto_1.jpg" in r for r in records),
                f"el log dry-run debe mostrar el nombre que quedaría: {records}",
            )

    def test_handler_default_is_real_move(self):
        logger, records = self._capturing_logger()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            src = folder / "foto.jpg"
            src.write_text("x")
            config = load_config(None)
            config["conflict"] = "rename"
            ext_map = build_extension_map(config["categories"])
            handler = OrganizerHandler(folder, config, ext_map, logger)
            self.assertFalse(handler._dry_run)
            handler._pending[str(src)] = time.time() - 10
            handler.process_pending()
            self.assertFalse(src.exists())
            self.assertTrue((folder / "Imágenes" / "foto.jpg").exists())


class ConfigMergeTests(unittest.TestCase):
    def _user_config(self, tmp, data):
        path = Path(tmp) / "mi_config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_user_extensions_are_added_not_replacing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._user_config(tmp, {"categories": {"Imágenes": [".avif"]}})
            config = load_config(path)
            self.assertIn(".jpg", config["categories"]["Imágenes"])
            self.assertIn(".avif", config["categories"]["Imágenes"])
            # Sin duplicados y con las de por defecto primero
            self.assertEqual(
                config["categories"]["Imágenes"].count(".avif"), 1
            )
            self.assertLess(
                config["categories"]["Imágenes"].index(".jpg"),
                config["categories"]["Imágenes"].index(".avif"),
            )

    def test_user_category_is_added_alongside_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._user_config(tmp, {"categories": {"Mixtos": [".xyz"]}})
            config = load_config(path)
            self.assertIn("Mixtos", config["categories"])
            self.assertIn("Imágenes", config["categories"])

    def test_empty_list_removes_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._user_config(tmp, {"categories": {"Torrents": []}})
            config = load_config(path)
            self.assertNotIn("Torrents", config["categories"])
            self.assertIn("Imágenes", config["categories"])

    def test_merge_does_not_mutate_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._user_config(tmp, {"categories": {"Imágenes": [".avif"]}})
            load_config(path)
            self.assertNotIn(".avif", DEFAULT_CONFIG["categories"]["Imágenes"])
            # Y una segunda carga sin config sigue limpia
            self.assertNotIn(".avif", load_config(None)["categories"]["Imágenes"])

    def test_malformed_categories_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._user_config(tmp, {"categories": {"Imágenes": "jpg"}})
            with self.assertRaises(ValueError):
                load_config(path)
            path = self._user_config(tmp, {"categories": {"Imágenes": ["jpg"]}})
            with self.assertRaises(ValueError):
                load_config(path)
            path = self._user_config(tmp, {"categories": "nada"})
            with self.assertRaises(ValueError):
                load_config(path)

    def test_validate_config_rejects_bad_extensions(self):
        config = load_config(None)
        config["categories"]["Imágenes"] = ["jpg"]
        with self.assertRaises(ValueError):
            validate_config(config)
        config = load_config(None)
        config["categories"]["Imágenes"] = "jpg"
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_mime_fallback_still_merges_by_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._user_config(
                tmp, {"mime_fallback": {"application/x-nuevo": "Otros"}}
            )
            config = load_config(path)
            self.assertEqual(config["mime_fallback"]["application/x-nuevo"], "Otros")
            self.assertEqual(config["mime_fallback"]["image/"], "Imágenes")


class DryRunConflictModeTests(unittest.TestCase):
    def _capturing_logger(self):
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger("test-dry-run-mode")
        logger.setLevel(logging.DEBUG)
        logger.handlers = [_Capture()]
        logger.propagate = False
        return logger, records

    def _run_dry_conflict(self, mode):
        logger, records = self._capturing_logger()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Imágenes").mkdir()
            (folder / "Imágenes" / "foto.jpg").write_text("vieja")
            src = folder / "foto.jpg"
            src.write_text("nueva")
            config = load_config(None)
            config["conflict"] = mode
            ext_map = build_extension_map(config["categories"])
            moved = move_file(src, folder, config, ext_map, logger, dry_run=True)
            self.assertTrue(src.exists(), "dry-run no debe mover nada")
            self.assertEqual((folder / "Imágenes" / "foto.jpg").read_text(), "vieja")
            return moved, records

    def test_dry_run_rename_shows_new_name(self):
        moved, records = self._run_dry_conflict("rename")
        self.assertTrue(moved)
        self.assertTrue(any(
            "[DRY-RUN] CONFLICTO" in r and "foto_1.jpg" in r for r in records
        ))

    def test_dry_run_overwrite_says_it_would_overwrite(self):
        _, records = self._run_dry_conflict("overwrite")
        self.assertTrue(any(
            "[DRY-RUN] CONFLICTO" in r and "sobrescribiría" in r for r in records
        ))
        self.assertFalse(any("foto_1.jpg" in r for r in records))

    def test_dry_run_skip_says_it_would_skip(self):
        _, records = self._run_dry_conflict("skip")
        self.assertTrue(any(
            "[DRY-RUN] CONFLICTO" in r and "saltaría" in r for r in records
        ))
        self.assertFalse(any("foto_1.jpg" in r for r in records))

    def test_dry_run_ask_says_it_would_ask(self):
        _, records = self._run_dry_conflict("ask")
        self.assertTrue(any(
            "[DRY-RUN] CONFLICTO" in r and "preguntaría" in r
            and "foto_1.jpg" in r for r in records
        ))

    def test_dry_run_invalid_mode_raises(self):
        logger, _ = self._capturing_logger()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Imágenes").mkdir()
            (folder / "Imágenes" / "foto.jpg").write_text("vieja")
            src = folder / "foto.jpg"
            src.write_text("nueva")
            config = load_config(None)
            config["conflict"] = "typo"
            ext_map = build_extension_map(config["categories"])
            with self.assertRaises(ValueError):
                move_file(src, folder, config, ext_map, logger, dry_run=True)


class VersionTests(unittest.TestCase):
    def test_version_is_semver(self):
        # La versión es la única fuente para el tag de la GUI y debe
        # coincidir con el tag del release (vX.Y.Z).
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")

    def test_gui_label_uses_version_not_hardcoded(self):
        # La etiqueta de la GUI debe leer __version__, no un "v2.5"
        # fijo que se quede atrás en el siguiente release.
        repo = Path(__file__).resolve().parent.parent
        gui_source = (repo / "organizer_gui.py").read_text(encoding="utf-8")
        self.assertIn('f"v{__version__}"', gui_source)
        self.assertNotIn('"v2.5"', gui_source)


if __name__ == "__main__":
    unittest.main()
