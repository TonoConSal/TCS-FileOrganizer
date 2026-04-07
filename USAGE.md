# 📁 FileOrganizer — Guía de uso

> Ordena tu carpeta de Descargas automáticamente en subcarpetas por tipo de archivo.  
> No requiere instalar nada. Solo descarga y abre.

---

## ⬇️ Descarga e instalación

1. Descarga **FileOrganizer.exe** desde la sección [Releases](../../releases) de este repositorio.
2. Guárdalo donde quieras (Escritorio, Documentos, etc.).
3. Haz doble clic para abrirlo. No necesitas instalar nada más.

> **Windows puede mostrar una advertencia de seguridad** la primera vez.  
> Haz clic en **"Más información"** → **"Ejecutar de todas formas"** para continuar.

---

## 🖥️ La interfaz

```
┌─────────────────────────────────────────────────┐
│  📁  File Organizer                        v2.0 │
├─────────────────────────────────────────────────┤
│  CARPETA A ORGANIZAR                            │
│  [ C:\Users\...\Downloads        ] [Examinar]   │
│                                                 │
│  CONFIG PERSONALIZADA (opcional)                │
│  [                               ] [Examinar]   │
│                                                 │
│  OPCIONES                                       │
│  Si existe el archivo:                          │
│  ● Preguntar  ○ Renombrar  ○ Saltar  ○ Sobresc. │
│  □ Modo simulación (dry-run — no mueve nada)    │
│                                                 │
│  [▶ Organizar ahora] [👁 Iniciar watcher] [🗑]  │
│─────────────────────────────────────────────────│
│  ACTIVIDAD                                      │
│  [14:23:01] INFO  MOVIDO pelicula.mp4 → Videos/ │
│  [14:23:01] INFO  MOVIDO foto.jpg → Imágenes/   │
│  ...                                            │
├─────────────────────────────────────────────────┤
│  Listo — 12 movidos, 0 saltados.                │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Uso básico (paso a paso)

### Organizar una carpeta de una sola vez

1. Abre **FileOrganizer.exe**.
2. En **"Carpeta a organizar"**, haz clic en **Examinar** y selecciona tu carpeta de Descargas (o cualquier otra).
3. Haz clic en **▶ Organizar ahora**.
4. Listo. En la sección **Actividad** verás qué archivo fue a qué carpeta.

---

## 📂 ¿Dónde van a parar mis archivos?

El programa crea subcarpetas automáticamente según el tipo de archivo:

| Subcarpeta          | Tipos de archivo                              |
|---------------------|-----------------------------------------------|
| Imágenes            | .jpg, .png, .gif, .webp, .heic, .svg, ...    |
| Videos              | .mp4, .mkv, .avi, .mov, .webm, ...           |
| Audio               | .mp3, .flac, .wav, .ogg, .m4a, ...           |
| Documentos          | .pdf, .docx, .txt, .md, ...                  |
| Hojas de cálculo    | .xlsx, .csv, .ods, ...                        |
| Código              | .py, .js, .html, .json, .yaml, ...           |
| Ejecutables         | .exe, .msi, .apk, ...                        |
| Comprimidos         | .zip, .rar, .7z, .tar.gz, ...                |
| Diseño              | .psd, .ai, .fig, .sketch, ...                |
| eBooks              | .epub, .mobi, .cbr, ...                      |
| Otros               | Todo lo que no encaje en ninguna categoría    |

---

## ⚙️ Opciones explicadas

### Si existe el archivo (conflictos)

Elige qué pasa cuando ya hay un archivo con el mismo nombre en la carpeta destino:

| Opción         | Qué hace                                                         |
|----------------|------------------------------------------------------------------|
| **Preguntar**  | Te pregunta caso por caso qué hacer *(recomendado)*             |
| **Renombrar**  | Guarda el nuevo como `archivo_1.pdf`, `archivo_2.pdf`, etc.     |
| **Saltar**     | Lo ignora y lo deja donde está                                   |
| **Sobreescribir** | Reemplaza el archivo existente sin preguntar                 |

---

### 👁 Watcher — organización en tiempo real

Cuando activas el **watcher**, el programa se queda corriendo en segundo plano y organiza automáticamente cada archivo nuevo que aparezca en la carpeta — ideal si lo apuntas a tu carpeta de Descargas y lo dejas toda la sesión.

- Haz clic en **👁 Iniciar watcher** para activarlo.
- El botón se pone **rojo** mientras está activo.
- Haz clic en **⏹ Detener watcher** para apagarlo.

> El watcher espera un momento antes de mover cada archivo para asegurarse de que la descarga esté completa.

---

### ☑️ Modo simulación (dry-run)

Marca esta casilla si quieres **ver qué haría el programa sin mover nada**. Útil para revisar antes de organizar por primera vez.

---

## 📋 El log de actividad

La sección **Actividad** muestra en tiempo real cada acción:

- 🟢 Líneas blancas — archivo movido exitosamente
- 🟡 Líneas amarillas — advertencias (ej. archivo saltado)
- 🔴 Líneas rojas — errores

También se guarda un archivo `organizer.log` dentro de la carpeta que organizaste, por si quieres revisarlo después.

---

## 🛠 Config personalizada (avanzado)

Si quieres definir tus propias categorías o cambiar el comportamiento por defecto, puedes usar un archivo de configuración `.toml`. Descárgalo desde el repositorio (`organizer_config.toml`), edítalo con el Bloc de notas, y cárgalo con el botón **Examinar** en el campo de config.

---

## ❓ Preguntas frecuentes

**¿Borra archivos?**  
No. Solo los mueve a subcarpetas dentro de la misma carpeta que seleccionaste.

**¿Funciona en otras carpetas además de Descargas?**  
Sí, cualquier carpeta funciona. Solo selecciónala con el botón **Examinar**.

**¿Organiza subcarpetas también?**  
No, solo los archivos que están directamente en la carpeta seleccionada.

**¿Qué pasa si cierro el programa con el watcher activo?**  
El watcher se detiene automáticamente al cerrar la ventana.

**¿Tengo que volver a configurarlo cada vez que lo abro?**  
Sí por ahora, no guarda la configuración entre sesiones. Próximamente.

---

## 🐛 Reportar un problema

¿Algo no funcionó como esperabas? Abre un [Issue](../../issues) en este repositorio describiendo qué pasó y en qué tipo de archivo ocurrió.
