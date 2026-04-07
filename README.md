# 📁 File Organizer

Organiza tus carpetas automáticamente en subcarpetas por tipo de archivo.
Detecta por **extensión** primero y por **tipo MIME** como fallback.

---

## 🚀 Instalación

```bash
pip install watchdog          # Para el modo watcher (tiempo real)
pip install tomli             # Solo si usas Python < 3.11 y configs TOML
```

---

## 📖 Uso

```bash
# Organiza tu carpeta Descargas/Downloads de una vez
python organizer.py

# Especifica una carpeta concreta
python organizer.py ~/Descargas

# Simula sin mover nada (útil para ver qué haría)
python organizer.py --dry-run

# Modo watcher: organiza en tiempo real mientras descargas
python organizer.py --watch

# Usa tu propia config
python organizer.py --config organizer_config.toml

# Combinar flags
python organizer.py ~/Descargas --watch --config mi_config.toml
```

---

## 📂 Carpetas que crea

| Carpeta             | Extensiones ejemplo                          |
|---------------------|----------------------------------------------|
| Imágenes            | .jpg, .png, .gif, .webp, .heic, .svg        |
| Videos              | .mp4, .mkv, .avi, .mov, .webm               |
| Audio               | .mp3, .flac, .wav, .ogg, .m4a               |
| Documentos          | .pdf, .docx, .txt, .md, .odt                |
| Hojas de cálculo    | .xlsx, .csv, .ods                            |
| Código              | .py, .js, .cs, .html, .json, .yaml          |
| Ejecutables         | .exe, .msi, .apk, .deb                      |
| Comprimidos         | .zip, .rar, .7z, .tar.gz                    |
| Diseño              | .psd, .ai, .fig, .sketch                    |
| eBooks              | .epub, .mobi, .cbr                          |
| Otros               | Todo lo que no encaje en ninguna categoría   |

---

## ⚙️ Config personalizada

Edita `organizer_config.toml` para agregar tus propias categorías:

```toml
[categories]
"Proyectos ROM" = [".gba", ".nds", ".ips", ".bps"]
"Godot"         = [".tscn", ".gd", ".tres"]
```

---

## 📝 Log

Cada vez que se corre, se escribe un log en la carpeta organizada:
```
[2025-06-01 14:23:11] INFO     MOVIDO  tutorial.mp4  →  Videos/
[2025-06-01 14:23:11] WARNING  SKIP (ya existe) → notas.txt
```

---

## 🔍 Cómo detecta el tipo

1. **Extensión compuesta** (`.tar.gz`) → busca en el mapa de categorías
2. **Extensión simple** (`.mp4`) → busca en el mapa de categorías  
3. **Tipo MIME** (via `mimetypes`) → fallback si la extensión no está mapeada
4. **"Otros"** → categoría de respaldo si nada funcionó
