"""
organizer.py - File Organizer con detección MIME + extensión, watcher, logging y config externa.

Uso:
    python organizer.py [carpeta]               # Organiza una sola vez
    python organizer.py [carpeta] --watch       # Modo watcher (corre indefinidamente)
    python organizer.py [carpeta] --dry-run     # Simula sin mover nada
    python organizer.py --config mi_config.toml # Usa config personalizada

Sin carpeta ni --no-prompt, el programa pregunta al inicio qué
carpeta organizar y qué modo de conflicto usar, en vez de organizar
Descargas/Downloads sin avisar. También pregunta con el botón Run
de un IDE, donde stdin no es una terminal.
"""

import argparse
import json
import logging
import mimetypes
import shutil
import sys
import time
import threading
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
    Observer = None
    FileSystemEventHandler = object
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
        renamed = unique_path(dst)
        logger.info(f"CONFLICTO → {dst.name} ya existe, renombrado a {renamed.name}")
        return renamed
    elif mode == "ask":
        print(f"\n⚠️  Conflicto: '{dst.name}' ya existe en '{dst.parent}'")
        print("   [r] Renombrar  [o] Sobreescribir  [s] Saltar  [q] Salir")
        while True:
            resp = input("   Tu elección: ").strip().lower()
            if resp == "r":
                renamed = unique_path(dst)
                logger.info(f"CONFLICTO → {dst.name} ya existe, renombrado a {renamed.name}")
                return renamed
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
    raise ValueError(
        f"Modo de conflicto no válido: {mode!r} "
        "(usa ask, rename, skip u overwrite)"
    )


VALID_CONFLICT_MODES = frozenset({"ask", "rename", "skip", "overwrite"})


def default_exclude(
    folder: Path, config: dict, config_path: Path | None = None
) -> frozenset[Path]:
    """Rutas propias que nunca deben moverse, aunque estén en la carpeta
    objetivo: el log, la config y los scripts del programa (CLI y GUI).

    La CLI y la GUI deben usar este mismo helper, para que el arreglo no
    quede solo en un lado.

    Si la config no trae "log_file" (o viene vacío / no es texto), no se
    excluye ningún log y no se lanza KeyError: se excluyen solo los
    scripts y la config. Los puntos de entrada deben validar la config
    con validate_config() antes de llegar aquí, para que ese caso falle
    rápido con un mensaje claro en vez de seguir sin log excluido.
    """
    exclude = {
        Path(__file__).resolve(),
        (Path(__file__).resolve().parent / "organizer_gui.py").resolve(),
    }
    log_file = config.get("log_file") if isinstance(config, dict) else None
    if isinstance(log_file, str) and log_file.strip():
        exclude.add((folder / log_file).resolve())
    if config_path:
        exclude.add(config_path.resolve())
    return frozenset(exclude)


def validate_config(config: dict) -> None:
    """Valida la config ya cargada; lanza ValueError si algo no es usable."""
    if not isinstance(config, dict):
        raise ValueError("La configuración debe ser un dict.")
    conflict = config.get("conflict")
    # Comprobar el tipo antes de buscar en el frozenset: un valor no
    # hashable (lista, dict, ...) lanzaría TypeError en lugar del
    # ValueError esperado.
    if not isinstance(conflict, str) or conflict not in VALID_CONFLICT_MODES:
        raise ValueError(
            f"Modo de conflicto no válido: {conflict!r} "
            "(usa ask, rename, skip u overwrite)"
        )
    log_file = config.get("log_file")
    if not isinstance(log_file, str) or not log_file.strip():
        raise ValueError(
            "La configuración debe incluir 'log_file' como texto no vacío."
        )


# Únicas extensiones compuestas que se reconocen como una sola.
# Cualquier otro nombre con varios puntos se trata con su último
# sufijo, para no romperlo: "my.file.pdf" -> "my.file_1.pdf".
KNOWN_COMPOUND_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz")


def _split_stem_suffix(path: Path) -> tuple[str, str]:
    """Separa stem y sufijo, respetando solo las compuestas conocidas."""
    name_lower = path.name.lower()
    for compound in KNOWN_COMPOUND_SUFFIXES:
        if name_lower.endswith(compound):
            return path.name[: -len(compound)], path.name[-len(compound):]
    return path.stem, path.suffix


def unique_path(dst: Path) -> Path:
    """Genera un nombre único agregando _1, _2, etc.

    Respeta extensiones compuestas conocidas (.tar.gz -> archive_1.tar.gz)
    y conserva el nombre tal cual: no se interpreta ningún sufijo "_N"
    como contador generado, porque puede ser parte legítima del nombre
    original. Así "foto_1.jpg" -> "foto_1_1.jpg" y
    "report_2024.pdf" -> "report_2024_1.pdf".
    """
    stem, suffix = _split_stem_suffix(dst)
    counter = 1
    while dst.exists():
        dst = dst.with_name(f"{stem}_{counter}{suffix}")
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
    logger.info(f"MOVIDO  {src.name}  →  {category}/{final_dest.name}")
    return True


# ── Organizar carpeta completa ────────────────────────────────────────────────

def organize_folder(
    folder: Path,
    config: dict,
    ext_map: dict,
    logger: logging.Logger,
    dry_run: bool = False,
    exclude: frozenset[Path] | None = None,
) -> tuple[int, int]:
    """Organiza todos los archivos en la carpeta (no recursivo). Retorna (movidos, saltados).

    `exclude` son rutas (resueltas) que nunca se mueven: el propio log, el
    archivo de config y los scripts del programa, si están en la carpeta.
    """
    moved = skipped = 0
    excluded = {Path(p).resolve() for p in exclude} if exclude else set()
    files = [
        f
        for f in folder.iterdir()
        if f.is_file() and f.resolve() not in excluded
    ]

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
    def __init__(self, folder: Path, config: dict, ext_map: dict, logger: logging.Logger,
                 exclude: frozenset[Path] | None = None):
        self.folder = folder
        self.config = config
        self.ext_map = ext_map
        self.logger = logger
        self._pending: dict[str, float] = {}
        self._excluded = {Path(p).resolve() for p in exclude} if exclude else set()

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
            if path.resolve() in self._excluded:
                continue
            if path.exists() and path.is_file():
                move_file(path, self.folder, self.config, self.ext_map, self.logger)



def _watcher_config(config: dict, logger: logging.Logger) -> dict:
    """Config efectiva del watcher.

    El modo 'ask' no sirve en un watcher: es desatendido, corre en
    un hilo secundario y en la GUI/.exe ni siquiera hay consola, así
    que su input() muere con EOFError y detiene el watcher entero.
    En ese caso se usa 'rename' (nunca se sobrescribe nada) y se
    avisa en el log. La config original no se toca: el modo 'ask'
    sigue valiendo para organizar una sola vez.
    """
    watcher_config = dict(config)
    if watcher_config.get("conflict") == "ask":
        watcher_config["conflict"] = "rename"
        logger.warning(
            "Watcher: el modo 'ask' no funciona sin consola; "
            "usando 'rename' para no detener el watcher."
        )
    return watcher_config


def start_watcher(
    folder: Path,
    config: dict,
    ext_map: dict,
    logger: logging.Logger,
    stop_event: threading.Event | None = None,
    exclude: frozenset[Path] | None = None,
):
    if not WATCHDOG_AVAILABLE:
        logger.error("Watchdog no está instalado. Instálalo con: pip install watchdog")
        return

    # Si no recibimos una señal externa, creamos una propia.
    if stop_event is None:
        stop_event = threading.Event()

    handler = OrganizerHandler(
        folder, _watcher_config(config, logger), ext_map, logger, exclude=exclude
    )
    observer = Observer()

    observer.schedule(handler, str(folder), recursive=False)
    observer.start()

    logger.info(f"👁️ Watcher activo en '{folder}'.")

    try:
        while not stop_event.is_set():
            handler.process_pending()
            stop_event.wait(0.5)

    except KeyboardInterrupt:
        logger.info("Watcher detenido por el usuario.")

    finally:
        observer.stop()
        observer.join()
        logger.info("Watcher detenido.")



# ── Preguntas iniciales del CLI ─────────────────────────────────────────────

def _default_downloads_folder() -> Path:
    """Descargas (es_MX) si existe, si no Downloads. Puede no existir."""
    candidates = [Path.home() / "Descargas", Path.home() / "Downloads"]
    return next((p for p in candidates if p.exists()), candidates[1])


def prompt_folder(default: Path) -> Path:
    """Pregunta qué carpeta organizar. Enter acepta la sugerida.

    Vuelve a preguntar si la ruta no existe. Si no hay entrada
    (EOF) o se cancela con Ctrl+C, sale sin organizar nada.
    """
    while True:
        try:
            answer = input(f"Carpeta a organizar [{default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[!] Operación cancelada.")
            raise SystemExit(1)
        folder = Path(answer).expanduser().resolve() if answer else default.resolve()
        if folder.exists():
            return folder
        print(f"[!] La carpeta no existe: {folder}")


def prompt_conflict_mode(default: str) -> str:
    """Pregunta el modo de conflicto. Enter acepta el de la config."""
    modes = sorted(VALID_CONFLICT_MODES)
    while True:
        try:
            answer = input(
                f"Modo de conflicto {modes} [{default}]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[!] Operación cancelada.")
            raise SystemExit(1)
        if not answer:
            return default
        if answer in VALID_CONFLICT_MODES:
            return answer
        print(f"[!] Modo no válido: {answer!r} (usa {', '.join(modes)})")


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
        help="Carpeta a organizar. Si no se pasa, se pregunta al inicio "
        "(sugerida: ~/Descargas o ~/Downloads)",
    )
    parser.add_argument(
        "--conflict",
        choices=sorted(VALID_CONFLICT_MODES),
        default=None,
        help="Modo de conflicto: ask, rename, skip u overwrite. "
        "Si no se pasa, se pregunta al inicio",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="No preguntar nada al inicio: usa la carpeta y el modo de "
        "la config (para scripts y automatización)",
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

    config = load_config(args.config)
    try:
        validate_config(config)
    except ValueError as exc:
        print(f"[!] Config no válida: {exc}")
        sys.exit(1)

    # Carpeta a organizar: argumento, o pregunta al inicio siempre,
    # también con el botón Run de un IDE (donde stdin no es una
    # terminal). Solo --no-prompt usa Descargas sin preguntar.
    # Si no hay de dónde leer la respuesta (EOF), prompt_folder()
    # sale sin organizar nada, en vez de irse a Descargas en silencio.
    if args.folder:
        folder = Path(args.folder).expanduser().resolve()
    elif args.no_prompt:
        folder = _default_downloads_folder()
    else:
        folder = prompt_folder(_default_downloads_folder())

    if not folder.exists():
        print(f"[!] La carpeta no existe: {folder}")
        sys.exit(1)

    # Modo de conflicto: flag, o pregunta al inicio. Solo --no-prompt
    # usa el modo de la config sin preguntar.
    if args.conflict:
        config["conflict"] = args.conflict
    elif not args.no_prompt:
        config["conflict"] = prompt_conflict_mode(config["conflict"])

    log_path = folder / config["log_file"]
    logger = setup_logging(log_path)

    # Archivos propios que nunca deben moverse, aunque estén en la carpeta
    # objetivo: el log, la config y los scripts del programa.
    exclude = default_exclude(folder, config, args.config)

    logger.info(f"=== Organizer iniciado {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    logger.info(f"Carpeta objetivo: {folder}")
    logger.info(f"Modo de conflicto: {config['conflict']}")
    if args.config:
        logger.info(f"Config cargada desde: {args.config}")

    ext_map = build_extension_map(config["categories"])

    if args.watch:
        # En modo watch, primero organiza lo existente y luego se queda escuchando
        organize_folder(folder, config, ext_map, logger, dry_run=args.dry_run, exclude=exclude)
        if not args.dry_run:
            start_watcher(folder, config, ext_map, logger, exclude=exclude)
    else:
        organize_folder(folder, config, ext_map, logger, dry_run=args.dry_run, exclude=exclude)


if __name__ == "__main__":
    main()
