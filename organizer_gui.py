"""
organizer_gui.py - Interfaz gráfica para el organizador de archivos.
Empaqueta junto a organizer.py y se compila con PyInstaller en un .exe.
"""

import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext
import logging
from pathlib import Path
import sys
import os

# ── Importar lógica del organizador ──────────────────────────────────────────
# Asegura que el directorio del script esté en el path (importante para .exe)
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
sys.path.insert(0, str(BASE_DIR))

from organizer import load_config, build_extension_map, organize_folder, start_watcher

# ── Paleta ────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#0f1117",
    "surface":   "#1a1d27",
    "border":    "#2a2d3e",
    "accent":    "#5b8af0",
    "accent_hv": "#7aa3ff",
    "success":   "#4ade80",
    "warn":      "#facc15",
    "danger":    "#f87171",
    "text":      "#e2e8f0",
    "muted":     "#64748b",
    "log_bg":    "#0a0c12",
}

FONT_MONO  = ("Consolas", 9)
FONT_UI    = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI Semibold", 13)
FONT_LABEL = ("Segoe UI", 9)


# ── Widget helpers ────────────────────────────────────────────────────────────

def styled_btn(parent, text, cmd, color=None, width=14):
    bg = color or C["accent"]
    btn = tk.Button(
        parent, text=text, command=cmd,
        bg=bg, fg=C["text"], activebackground=C["accent_hv"],
        activeforeground=C["text"], relief="flat", bd=0,
        font=FONT_UI, cursor="hand2", width=width,
        padx=10, pady=6,
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=C["accent_hv"]))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def section_label(parent, text):
    tk.Label(parent, text=text, bg=C["bg"], fg=C["muted"],
             font=FONT_LABEL).pack(anchor="w", padx=20, pady=(14, 2))


# ── Logger que escribe al widget de texto ─────────────────────────────────────

class GUILogHandler(logging.Handler):
    TAG_MAP = {
        "INFO":    "info",
        "WARNING": "warn",
        "ERROR":   "error",
        "DEBUG":   "muted",
    }

    def __init__(self, widget: scrolledtext.ScrolledText):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        msg = self.format(record)
        tag = self.TAG_MAP.get(record.levelname, "info")
        self.widget.after(0, self._append, msg + "\n", tag)

    def _append(self, msg, tag):
        self.widget.config(state="normal")
        self.widget.insert("end", msg, tag)
        self.widget.see("end")
        self.widget.config(state="disabled")


# ── Ventana principal ─────────────────────────────────────────────────────────

class OrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("File Organizer")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.geometry("580x620")

        # Estado
        self._watcher_thread: threading.Thread | None = None
        self._watching = False
        self._folder = tk.StringVar()
        self._dry_run = tk.BooleanVar(value=False)
        self._conflict = tk.StringVar(value="ask")
        self._config_path = tk.StringVar(value="")

        self._build_ui()
        self._setup_logger()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header
        header = tk.Frame(self, bg=C["surface"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📁  File Organizer", bg=C["surface"],
                 fg=C["text"], font=FONT_TITLE).pack(side="left", padx=20, pady=14)
        tk.Label(header, text="v2.0", bg=C["surface"],
                 fg=C["muted"], font=FONT_LABEL).pack(side="right", padx=20)

        # ── Carpeta objetivo
        section_label(self, "CARPETA A ORGANIZAR")
        row = tk.Frame(self, bg=C["bg"])
        row.pack(fill="x", padx=20)

        entry_folder = tk.Entry(
            row, textvariable=self._folder,
            bg=C["surface"], fg=C["text"], insertbackground=C["text"],
            relief="flat", font=FONT_UI, bd=0,
        )
        entry_folder.pack(side="left", fill="x", expand=True,
                          ipady=7, ipadx=8)
        self._add_border(entry_folder)

        styled_btn(row, "Examinar", self._pick_folder, width=10).pack(side="left", padx=(8, 0))

        # ── Config externa
        section_label(self, "CONFIG PERSONALIZADA  (opcional)")
        row2 = tk.Frame(self, bg=C["bg"])
        row2.pack(fill="x", padx=20)

        entry_cfg = tk.Entry(
            row2, textvariable=self._config_path,
            bg=C["surface"], fg=C["text"], insertbackground=C["text"],
            relief="flat", font=FONT_UI, bd=0,
        )
        entry_cfg.pack(side="left", fill="x", expand=True, ipady=7, ipadx=8)
        self._add_border(entry_cfg)

        styled_btn(row2, "Examinar", self._pick_config, width=10).pack(side="left", padx=(8, 0))

        # ── Opciones
        section_label(self, "OPCIONES")
        opts = tk.Frame(self, bg=C["bg"])
        opts.pack(fill="x", padx=20, pady=(0, 4))

        # Conflicto
        tk.Label(opts, text="Si existe el archivo:", bg=C["bg"],
                 fg=C["text"], font=FONT_UI).grid(row=0, column=0, sticky="w", pady=4)

        conflict_frame = tk.Frame(opts, bg=C["bg"])
        conflict_frame.grid(row=0, column=1, sticky="w", padx=(12, 0))
        for val, lbl in [("ask", "Preguntar"), ("rename", "Renombrar"), ("skip", "Saltar"), ("overwrite", "Sobreescribir")]:
            tk.Radiobutton(
                conflict_frame, text=lbl, variable=self._conflict, value=val,
                bg=C["bg"], fg=C["text"], selectcolor=C["surface"],
                activebackground=C["bg"], activeforeground=C["accent"],
                font=FONT_UI,
            ).pack(side="left", padx=(0, 10))

        # Dry run
        tk.Checkbutton(
            opts, text="Modo simulación (dry-run — no mueve nada)",
            variable=self._dry_run,
            bg=C["bg"], fg=C["text"], selectcolor=C["surface"],
            activebackground=C["bg"], font=FONT_UI,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=4)

        # ── Botones de acción
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=20, pady=12)

        actions = tk.Frame(self, bg=C["bg"])
        actions.pack(padx=20, pady=(0, 4))

        styled_btn(actions, "▶  Organizar ahora", self._run_once,
                   color=C["accent"], width=18).pack(side="left", padx=(0, 8))

        self._watch_btn = styled_btn(actions, "👁  Iniciar watcher", self._toggle_watcher,
                                      color="#2d4a7a", width=18)
        self._watch_btn.pack(side="left", padx=(0, 8))

        styled_btn(actions, "🗑  Limpiar log", self._clear_log,
                   color=C["surface"], width=14).pack(side="left")

        # ── Log
        section_label(self, "ACTIVIDAD")
        self._log_widget = scrolledtext.ScrolledText(
            self, bg=C["log_bg"], fg=C["text"], font=FONT_MONO,
            relief="flat", bd=0, state="disabled", height=14,
            wrap="word",
        )
        self._log_widget.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # Tags de color para el log
        self._log_widget.tag_config("info",    foreground=C["text"])
        self._log_widget.tag_config("warn",    foreground=C["warn"])
        self._log_widget.tag_config("error",   foreground=C["danger"])
        self._log_widget.tag_config("muted",   foreground=C["muted"])
        self._log_widget.tag_config("success", foreground=C["success"])

        # ── Status bar
        self._status = tk.Label(self, text="Listo.", bg=C["surface"],
                                fg=C["muted"], font=FONT_LABEL, anchor="w")
        self._status.pack(fill="x", padx=20, pady=(0, 8))

    def _add_border(self, widget):
        """Frame wrapper que simula borde."""
        widget.master.config(bg=C["border"], padx=1, pady=1)

    # ── Logger ───────────────────────────────────────────────────────────────

    def _setup_logger(self):
        self._logger = logging.getLogger("organizer")
        self._logger.setLevel(logging.DEBUG)
        # Limpia handlers anteriores (si se recrea)
        self._logger.handlers.clear()

        gui_handler = GUILogHandler(self._log_widget)
        gui_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", "%H:%M:%S")
        )
        self._logger.addHandler(gui_handler)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _pick_folder(self):
        path = filedialog.askdirectory(title="Selecciona la carpeta a organizar")
        if path:
            self._folder.set(path)

    def _pick_config(self):
        path = filedialog.askopenfilename(
            title="Selecciona config",
            filetypes=[("Config files", "*.toml *.json"), ("All files", "*.*")],
        )
        if path:
            self._config_path.set(path)

    def _get_config(self):
        cfg_str = self._config_path.get().strip()
        cfg_path = Path(cfg_str) if cfg_str else None
        config = load_config(cfg_path)
        config["conflict"] = self._conflict.get()
        return config

    def _validate_folder(self) -> Path | None:
        folder_str = self._folder.get().strip()
        if not folder_str:
            self._set_status("⚠️  Selecciona una carpeta primero.", C["warn"])
            return None
        folder = Path(folder_str)
        if not folder.exists():
            self._set_status("❌  La carpeta no existe.", C["danger"])
            return None
        return folder

    def _run_once(self):
        folder = self._validate_folder()
        if not folder:
            return
        config = self._get_config()
        ext_map = build_extension_map(config["categories"])
        dry = self._dry_run.get()

        self._set_status("Organizando..." if not dry else "Simulando...", C["accent"])
        self._set_buttons_state("disabled")

        def task():
            try:
                moved, skipped = organize_folder(folder, config, ext_map, self._logger, dry_run=dry)
                msg = f"{'[Simulación] ' if dry else ''}Listo — {moved} movidos, {skipped} saltados."
                self.after(0, self._set_status, msg, C["success"])
            except Exception as e:
                self.after(0, self._set_status, f"Error: {e}", C["danger"])
                self._logger.error(str(e))
            finally:
                self.after(0, self._set_buttons_state, "normal")

        threading.Thread(target=task, daemon=True).start()

    def _toggle_watcher(self):
        if self._watching:
            self._watching = False
            self._watch_btn.config(text="👁  Iniciar watcher", bg="#2d4a7a")
            self._set_status("Watcher detenido.", C["muted"])
            return

        folder = self._validate_folder()
        if not folder:
            return

        try:
            from watchdog.observers import Observer
        except ImportError:
            self._set_status("❌  Instala watchdog: pip install watchdog", C["danger"])
            return

        config = self._get_config()
        ext_map = build_extension_map(config["categories"])

        self._watching = True
        self._watch_btn.config(text="⏹  Detener watcher", bg=C["danger"])
        self._set_status("Watcher activo — monitoreando cambios...", C["success"])

        def task():
            try:
                start_watcher(folder, config, ext_map, self._logger)
            except Exception as e:
                self.after(0, self._set_status, f"Watcher error: {e}", C["danger"])
            finally:
                self._watching = False
                self.after(0, self._watch_btn.config,
                           {"text": "👁  Iniciar watcher", "bg": "#2d4a7a"})

        self._watcher_thread = threading.Thread(target=task, daemon=True)
        self._watcher_thread.start()

    def _clear_log(self):
        self._log_widget.config(state="normal")
        self._log_widget.delete("1.0", "end")
        self._log_widget.config(state="disabled")

    def _set_status(self, msg, color=None):
        self._status.config(text=msg, fg=color or C["muted"])

    def _set_buttons_state(self, state):
        for widget in self.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=state)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = OrganizerApp()
    app.mainloop()
