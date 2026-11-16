"""Pruebas de la GUI (organizer_gui.py).

La mayoría necesita una pantalla: en Linux se corren con un display
virtual (xvfb-run -a python -m unittest discover -s tests -v); en
Windows corren directo. Sin display, esas pruebas se saltan solas.
Solo la prueba de close() con app falsa no necesita display.

Se corren junto al resto con:
    python -m unittest discover -s tests -v
"""
import logging
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk

from organizer import load_config
from organizer_gui import ConflictAsker, OrganizerApp


def _has_display():
    # Dos intentos: en Windows, Tcl a veces falla al leer su init.tcl
    # de forma transitoria (archivo bloqueado un instante por el
    # antivirus u otro proceso) y un reintento basta.
    for _ in range(2):
        try:
            root = tk.Tk()
            root.destroy()
            return True
        except tk.TclError:
            time.sleep(0.3)
    return False


HAS_DISPLAY = _has_display()


def _new_root():
    """Crea una ventana Tk; si Tcl no arranca, la prueba se salta.

    Un TclError aquí es un problema del entorno (Tk no pudo ni
    inicializarse), no del programa: fallar la prueba sería un falso
    positivo. El skip deja constancia del motivo.
    """
    try:
        return tk.Tk()
    except tk.TclError as exc:
        raise unittest.SkipTest(f"Tk no pudo arrancar: {exc}") from exc


def _new_app():
    """Como _new_root, pero crea la app completa (OrganizerApp)."""
    try:
        return OrganizerApp()
    except tk.TclError as exc:
        raise unittest.SkipTest(f"Tk no pudo arrancar: {exc}") from exc


class _StubApp:
    """App falsa: after() nunca ejecuta el diálogo."""

    def after(self, ms, func, *args):
        return None


class ConflictAskerCloseTests(unittest.TestCase):
    """close() debe despertar a ask() aunque el diálogo no exista.

    No necesita display: es la prueba del cuelgue que se reportó
    (cerrar la app con un diálogo pendiente dejaba el hilo esperando
    para siempre).
    """

    def test_close_unblocks_waiting_ask(self):
        asker = ConflictAsker(_StubApp())
        result = []
        t = threading.Thread(
            target=lambda: result.append(asker.ask(Path("a.txt"), Path("b.txt")))
        )
        t.start()
        time.sleep(0.3)
        asker.close()
        t.join(timeout=2)
        self.assertFalse(t.is_alive(), "ask() sigue bloqueado tras close()")
        self.assertEqual(result, ["cancel"])

    def test_ask_after_close_returns_cancel_immediately(self):
        asker = ConflictAsker(_StubApp())
        asker.close()
        self.assertEqual(asker.ask(Path("a.txt"), Path("b.txt")), "cancel")


def _close_organizer_logger():
    """Cierra los handlers del logger compartido (evita archivos
    abiertos entre pruebas)."""
    logger = logging.getLogger("organizer")
    for handler in list(logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
    logger.handlers.clear()


@unittest.skipUnless(HAS_DISPLAY, "sin display (usa xvfb-run en Linux)")
class ConflictDialogTests(unittest.TestCase):
    def setUp(self):
        self.root = _new_root()
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        _close_organizer_logger()

    def _run_ask(self, action, timeout=10):
        """Corre ask() en un hilo y ejecuta `action(dialog)` en el
        hilo principal cuando aparece el diálogo. Devuelve lo que
        devolvió ask()."""
        asker = ConflictAsker(self.root)
        result = []
        t = threading.Thread(
            target=lambda: result.append(
                asker.ask(Path("foto.jpg"), Path("Imágenes") / "foto.jpg")
            )
        )
        t.start()

        def check():
            if asker._dialog is not None:
                action(asker._dialog)
                self.root.after(200, self.root.destroy)
            else:
                self.root.after(50, check)

        self.root.after(100, check)
        self.root.after(timeout * 1000, self.root.destroy)  # no colgar el test
        self.root.mainloop()
        t.join(timeout=2)
        self.assertFalse(t.is_alive(), "ask() sigue bloqueado")
        return result[0] if result else None

    @staticmethod
    def _click_button(dialog, text):
        for child in dialog.winfo_children():
            for btn in child.winfo_children():
                if isinstance(btn, tk.Button) and btn.cget("text") == text:
                    btn.invoke()
                    return
        raise AssertionError(f"botón {text!r} no encontrado en el diálogo")

    def test_dialog_rename_button(self):
        self.assertEqual(
            self._run_ask(lambda d: self._click_button(d, "Renombrar")),
            "rename",
        )

    def test_dialog_overwrite_button(self):
        self.assertEqual(
            self._run_ask(lambda d: self._click_button(d, "Sobrescribir")),
            "overwrite",
        )

    def test_dialog_skip_button(self):
        self.assertEqual(
            self._run_ask(lambda d: self._click_button(d, "Saltar")),
            "skip",
        )

    def test_dialog_cancel_button(self):
        self.assertEqual(
            self._run_ask(lambda d: self._click_button(d, "Cancelar")),
            "cancel",
        )

    def test_dialog_close_button_is_skip(self):
        # La X de la ventana dispara el protocolo WM_DELETE_WINDOW.
        # protocol() sin función devuelve el comando Tcl registrado;
        # invocarlo es lo mismo que pulsar la X.
        def close_window(dialog):
            cmd = dialog.protocol("WM_DELETE_WINDOW")
            dialog.tk.call(cmd)

        self.assertEqual(self._run_ask(close_window), "skip")


@unittest.skipUnless(HAS_DISPLAY, "sin display (usa xvfb-run en Linux)")
class GuiAppTests(unittest.TestCase):
    def tearDown(self):
        _close_organizer_logger()

    def test_ensure_file_log_creates_and_replaces_handler(self):
        app = _new_app()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config = load_config(None)
                config["log_file"] = str(Path(tmp) / "uno.log")
                app._ensure_file_log(config)
                first = [
                    h for h in app._logger.handlers
                    if isinstance(h, logging.FileHandler)
                ]
                self.assertEqual(len(first), 1)
                self.assertTrue(Path(tmp, "uno.log").exists())
                self.assertEqual(app._log_path, Path(tmp) / "uno.log")

                config["log_file"] = str(Path(tmp) / "dos.log")
                app._ensure_file_log(config)
                handlers = [
                    h for h in app._logger.handlers
                    if isinstance(h, logging.FileHandler)
                ]
                self.assertEqual(len(handlers), 1, "debe quedar un solo FileHandler")
                self.assertTrue(Path(tmp, "dos.log").exists())
                # Al cerrar un FileHandler, su stream queda en None.
                self.assertIsNone(first[0].stream, "el handler viejo debe cerrarse")
                # Cerrar los handlers antes de borrar la carpeta: en
                # Windows no se puede borrar un archivo abierto.
                _close_organizer_logger()
        finally:
            app.destroy()

    def test_close_while_dialog_open_ends_app(self):
        """Cerrar la app con un diálogo de conflicto abierto no debe
        colgar: la corrida se cancela y mainloop() termina."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            folder = Path(tmp) / "prueba"
            (folder / "Imágenes").mkdir(parents=True)
            (folder / "Imágenes" / "foto.jpg").write_text("vieja")
            (folder / "foto.jpg").write_text("nueva")
            # En Windows el log va a %APPDATA%, en Linux a ~/.local/share.
            appdata = Path(tmp) / "appdata"
            log_file = (
                appdata / "TCS-FileOrganizer" / "organizer.log"
                if os.name == "nt"
                else home / ".local" / "share" / "TCS-FileOrganizer" / "organizer.log"
            )

            closed = []
            app = _new_app()
            app._folder.set(str(folder))
            app._conflict.set("ask")

            def step():
                if app._conflict_asker._dialog is not None:
                    closed.append(True)
                    app._on_close()
                else:
                    app.after(100, step)

            with mock.patch.dict(os.environ, {"HOME": str(home), "APPDATA": str(appdata)}):
                os.environ.pop("XDG_DATA_HOME", None)
                app.after(200, lambda: (app._run_once(), app.after(200, step)))
                app.after(15000, app.destroy)  # no colgar el test
                app.mainloop()

            self.assertTrue(closed, "el diálogo nunca apareció")
            # La corrida se canceló: el archivo sigue sin mover
            self.assertTrue((folder / "foto.jpg").exists())
            self.assertEqual((folder / "Imágenes" / "foto.jpg").read_text(), "vieja")
            # El log registra la cancelación (espera breve al hilo)
            for _ in range(30):
                if log_file.exists() and "Operación cancelada" in log_file.read_text(
                    encoding="utf-8", errors="ignore"
                ):
                    break
                time.sleep(0.1)
            self.assertIn(
                "Operación cancelada",
                log_file.read_text(encoding="utf-8", errors="ignore"),
            )
            # Cerrar los handlers antes de borrar la carpeta: en
            # Windows no se puede borrar un archivo abierto.
            _close_organizer_logger()

    def test_status_bar_shows_log_path_after_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            folder = Path(tmp) / "prueba"
            folder.mkdir(parents=True)
            (folder / "foto.jpg").write_text("x")
            # APPDATA temporal para que en Windows el log no toque el real.
            appdata = Path(tmp) / "appdata"

            app = _new_app()
            app._folder.set(str(folder))
            app._conflict.set("rename")
            seen = []

            def check():
                text = app._status.cget("text")
                if "Listo" in text:
                    seen.append(True)
                    self.assertIn("Log:", text)
                    app.destroy()
                else:
                    app.after(100, check)

            with mock.patch.dict(os.environ, {"HOME": str(home), "APPDATA": str(appdata)}):
                os.environ.pop("XDG_DATA_HOME", None)
                app.after(200, lambda: (app._run_once(), app.after(200, check)))
                app.after(15000, app.destroy)  # no colgar el test
                app.mainloop()

            self.assertTrue(seen, "la corrida nunca llegó a 'Listo'")
            self.assertTrue((folder / "Imágenes" / "foto.jpg").exists())
            # Cerrar los handlers antes de borrar la carpeta: en
            # Windows no se puede borrar un archivo abierto.
            _close_organizer_logger()


if __name__ == "__main__":
    unittest.main()
