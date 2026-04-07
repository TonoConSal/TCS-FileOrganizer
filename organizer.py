"""
organizer.py - File Organizer con detección MIME + extensión, watcher, logging y config externa.

Uso:
    python organizer.py [carpeta]               # Organiza una sola vez
    python organizer.py [carpeta] --watch       # Modo watcher (corre indefinidamente)
    python organizer.py [carpeta] --dry-run     # Simula sin mover nada
    python organizer.py --config mi_config.toml # Usa config personalizada
"""

import argparse
import json
import logging
import mimetypes
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Dependencias opcionales ───────────────────────────────────────────────────
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli
    except ImportError:
        tomllib = None

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# ── Config por defecto ────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "log_file": "organizer.log",
    "conflict": "ask",          # ask | rename | skip | overwrite
    "watch_delay": 1.5,         # segundos de espera antes de mover (evita archivos a medias)
    "categories": {
        "Imágenes":     [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".tiff", ".ico", ".heic"],
        "Videos":       [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"],
        "Audio":        [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"],
        "Documentos":   [".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".tex"],
        "Hojas de cálculo": [".xls", ".xlsx", ".ods", ".csv", ".tsv"],
        "Presentaciones":   [".ppt", ".pptx", ".odp"],
        "Código":       [".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h", ".java",
                         ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1",
                         ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
        "Ejecutables":  [".exe", ".msi", ".apk", ".dmg", ".deb", ".rpm", ".AppImage"],
        "Comprimidos":  [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tar.gz", ".tar.bz2"],
        "Fuentes":      [".ttf", ".otf", ".woff", ".woff2"],
        "Torrents":     [".torrent"],
        "Diseño":       [".psd", ".ai", ".xd", ".fig", ".sketch", ".indd"],
        "3D":           [".obj", ".fbx", ".stl", ".blend", ".3ds", ".dae"],
        "Bases de datos": [".db", ".sqlite", ".sql", ".mdb"],
        "eBooks":       [".epub", ".mobi", ".azw", ".azw3", ".cbr", ".cbz"],
        "ISO":          [".iso", ".img", ".bin", ".cue"],
    },
    # Reglas MIME como fallback (prefijo MIME → categoría)
    "mime_fallback": {
        "image/":       "Imágenes",
        "video/":       "Videos",
        "audio/":       "Audio",
        "text/":        "Documentos",
        "application/pdf": "Documentos",
        "application/zip": "Comprimidos",
        "application/x-tar": "Comprimidos",
        "application/gzip": "Comprimidos",
        "application/x-7z-compressed": "Comprimidos",
        "application/vnd.ms-excel": "Hojas de cálculo",
        "application/vnd.openxmlformats-officedocument.spreadsheetml": "Hojas de cálculo",
        "application/vnd.ms-powerpoint": "Presentaciones",
        "application/vnd.openxmlformats-officedocument.presentationml": "Presentaciones",
        "application/msword": "Documentos",
        "application/vnd.openxmlformats-officedocument.wordprocessingml": "Documentos",
        "application/octet-stream": "Otros",
    }
}


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("organizer")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ── Carga de config ───────────────────────────────────────────────────────────

def load_config(config_path: Path | None) -> dict:
    config = DEFAULT_CONFIG.copy()
    config["categories"] = dict(DEFAULT_CONFIG["categories"])
    config["mime_fallback"] = dict(DEFAULT_CONFIG["mime_fallback"])

    if config_path is None:
        return config

    if not config_path.exists():
        print(f"[!] No se encontró el archivo de config: {config_path}")
        sys.exit(1)

    suffix = config_path.suffix.lower()

    if suffix == ".json":
        with open(config_path, "r", encoding="utf-8") as f:
            user = json.load(f)
    elif suffix == ".toml":
        if tomllib is None:
            print("[!] Para usar TOML instala 'tomli': pip install tomli")
            sys.exit(1)
        with open(config_path, "rb") as f:
            user = tomllib.load(f)
    else:
        print(f"[!] Formato de config no soportado: {suffix} (usa .json o .toml)")
        sys.exit(1)

    # Merge: el usuario puede sobreescribir o agregar categorías
    if "categories" in user:
        config["categories"].update(user["categories"])
    if "mime_fallback" in user:
        config["mime_fallback"].update(user["mime_fallback"])
    for key in ("log_file", "conflict", "watch_delay"):
        if key in user:
            config[key] = user[key]

    return config


# ── Lógica de categorización ──────────────────────────────────────────────────

def build_extension_map(categories: dict) -> dict[str, str]:
    """Construye un dict rápido ext → categoría."""
    ext_map = {}
    for category, extensions in categories.items():
        for ext in extensions:
            ext_map[ext.lower()] = category
    return ext_map


def get_category(file: Path, ext_map: dict, mime_fallback: dict) -> str:
    """Detecta categoría por extensión primero, MIME como fallback."""
    # 1. Por extensión
    suffixes = "".join(file.suffixes).lower()   # maneja .tar.gz
    if suffixes in ext_map:
        return ext_map[suffixes]
    suffix = file.suffix.lower()
    if suffix in ext_map:
        return ext_map[suffix]

    # 2. Por MIME
    mime, _ = mimetypes.guess_type(file.name)
    if mime:
        # Primero busca match exacto
        if mime in mime_fallback:
            return mime_fallback[mime]
        # Luego por prefijo
        for prefix, category in mime_fallback.items():
            if mime.startswith(prefix):
                return category

    return "Otros"


# ── Resolución de conflictos ──────────────────────────────────────────────────

def resolve_conflict(src: Path, dst: Path, mode: str, logger: logging.Logger) -> Path | None:
    """
    Retorna el Path destino final, o None si se debe saltar el archivo.
    """
    if mode == "overwrite":
        return dst
    elif mode == "skip":
        logger.warning(f"SKIP (ya existe) → {dst.name}")
        return None
    elif mode == "rename":
        return unique_path(dst)
    elif mode == "ask":
        print(f"\n⚠️  Conflicto: '{dst.name}' ya existe en '{dst.parent}'")
        print("   [r] Renombrar  [o] Sobreescribir  [s] Saltar  [q] Salir")
        while True:
            resp = input("   Tu elección: ").strip().lower()
            if resp == "r":
                return unique_path(dst)
            elif resp == "o":
                return dst
            elif resp == "s":
                logger.warning(f"SKIP (usuario) → {dst.name}")
                return None
            elif resp == "q":
                logger.info("Usuario canceló la operación.")
                sys.exit(0)
            else:
                print("   Opción no válida, intenta de nuevo.")
    return dst


def unique_path(dst: Path) -> Path:
    """Genera un nombre único agregando _1, _2, etc."""
    counter = 1
    stem = dst.stem
    # Limpia sufijos numéricos anteriores para evitar archivo_1_1_1
    stem = re.sub(r"_\d+$", "", stem)
    while dst.exists():
        dst = dst.with_name(f"{stem}_{counter}{dst.suffix}")
        counter += 1
    return dst


# ── Mover archivo ─────────────────────────────────────────────────────────────

def move_file(
    src: Path,
    target_dir: Path,
    config: dict,
    ext_map: dict,
    logger: logging.Logger,
    dry_run: bool = False,
) -> bool:
    """
    Mueve src a la subcarpeta correcta dentro de target_dir.
    Retorna True si se movió (o se hubiera movido en dry-run).
    """
    category = get_category(src, ext_map, config["mime_fallback"])
    dest_folder = target_dir / category
    dest_file = dest_folder / src.name

    if dest_file == src:
        logger.debug(f"YA EN LUGAR CORRECTO → {src.name}")
        return False

    # Conflicto
    final_dest = dest_file
    if dest_file.exists():
        if dry_run:
            logger.info(f"[DRY-RUN] CONFLICTO → {src.name} → {dest_folder}/")
            return True
        final_dest = resolve_conflict(src, dest_file, config["conflict"], logger)
        if final_dest is None:
            return False

    if dry_run:
        logger.info(f"[DRY-RUN] {src.name}  →  {category}/")
        return True

    dest_folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(final_dest))
    logger.info(f"MOVIDO  {src.name}  →  {category}/")
    return True


# ── Organizar carpeta completa ────────────────────────────────────────────────

def organize_folder(
    folder: Path,
    config: dict,
    ext_map: dict,
    logger: logging.Logger,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Organiza todos los archivos en la carpeta (no recursivo). Retorna (movidos, saltados)."""
    moved = skipped = 0
    files = [f for f in folder.iterdir() if f.is_file()]

    if not files:
        logger.info("No hay archivos que organizar.")
        return 0, 0

    logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Organizando {len(files)} archivo(s) en '{folder}'...")

    for f in files:
        result = move_file(f, folder, config, ext_map, logger, dry_run)
        if result:
            moved += 1
        else:
            skipped += 1

    logger.info(f"Listo — Movidos: {moved} | Saltados/ya en lugar: {skipped}")
    return moved, skipped


# ── Watcher ───────────────────────────────────────────────────────────────────

class OrganizerHandler(FileSystemEventHandler):
    def __init__(self, folder: Path, config: dict, ext_map: dict, logger: logging.Logger):
        self.folder = folder
        self.config = config
        self.ext_map = ext_map
        self.logger = logger
        self._pending: dict[str, float] = {}

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Solo archivos directamente en la carpeta (no en subcarpetas)
        if path.parent != self.folder:
            return
        self._pending[str(path)] = time.time()

    def process_pending(self):
        now = time.time()
        delay = self.config.get("watch_delay", 1.5)
        ready = [p for p, t in self._pending.items() if now - t >= delay]
        for p in ready:
            path = Path(p)
            del self._pending[p]
            if path.exists() and path.is_file():
                move_file(path, self.folder, self.config, self.ext_map, self.logger)


def start_watcher(folder: Path, config: dict, ext_map: dict, logger: logging.Logger):
    if not WATCHDOG_AVAILABLE:
        logger.error("Watchdog no está instalado. Instálalo con: pip install watchdog")
        sys.exit(1)

    handler = OrganizerHandler(folder, config, ext_map, logger)
    observer = Observer()
    observer.schedule(handler, str(folder), recursive=False)
    observer.start()
    logger.info(f"👁️  Watcher activo en '{folder}'. Presiona Ctrl+C para detener.")

    try:
        while True:
            handler.process_pending()
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Watcher detenido por el usuario.")
        observer.stop()
    observer.join()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Organiza tu carpeta de descargas en subcarpetas automáticamente.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=None,
        help="Carpeta a organizar (por defecto: ~/Downloads o ~/Descargas)",
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Modo watcher: organiza nuevos archivos en tiempo real",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Simula sin mover nada",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help="Ruta a un archivo de config .json o .toml",
    )

    args = parser.parse_args()

    # Detectar carpeta
    if args.folder:
        folder = Path(args.folder).expanduser().resolve()
    else:
        # Intenta Descargas (es_MX) primero, luego Downloads
        candidates = [Path.home() / "Descargas", Path.home() / "Downloads"]
        folder = next((p for p in candidates if p.exists()), candidates[1])

    if not folder.exists():
        print(f"[!] La carpeta no existe: {folder}")
        sys.exit(1)

    config = load_config(args.config)

    log_path = folder / config["log_file"]
    logger = setup_logging(log_path)

    logger.info(f"=== Organizer iniciado {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    logger.info(f"Carpeta objetivo: {folder}")
    if args.config:
        logger.info(f"Config cargada desde: {args.config}")

    ext_map = build_extension_map(config["categories"])

    if args.watch:
        # En modo watch, primero organiza lo existente y luego se queda escuchando
        organize_folder(folder, config, ext_map, logger, dry_run=args.dry_run)
        if not args.dry_run:
            start_watcher(folder, config, ext_map, logger)
    else:
        organize_folder(folder, config, ext_map, logger, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
