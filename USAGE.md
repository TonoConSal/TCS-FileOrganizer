# FileOrganizer - Guía de uso

FileOrganizer es una herramienta de escritorio que permite organizar archivos automáticamente según su tipo. También incluye un modo de vigilancia que detecta archivos nuevos y los clasifica sin necesidad de intervenir manualmente.

La aplicación cuenta con una interfaz gráfica para facilitar su uso y está disponible para Windows y distribuciones Linux compatibles.

## Características principales

- Organización automática de archivos por categoría.
- Interfaz gráfica sencilla.
- Modo de vigilancia para organizar archivos nuevos automáticamente.
- Configuración personalizable mediante archivos TOML o JSON.
- Registro de operaciones para consultar los cambios realizados.

## Descargas

Puedes encontrar las versiones disponibles en la sección de [Releases de GitHub](https://github.com/TonoConSal/TCS-FileOrganizer/releases).

Selecciona el archivo correspondiente a tu sistema operativo.

---

## 🖥️ La interfaz

```
┌─────────────────────────────────────────────────┐
│  📁  File Organizer                        v2.5 │
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

## 🚀 Instalación y primeros pasos

### 🪟 Windows

1. Entra a la sección de [Releases](https://github.com/TonoConSal/TCS-FileOrganizer/releases) del repositorio.
2. Descarga el archivo `FileOrganizer.exe` de la versión que quieras instalar.
3. Ejecuta el archivo descargado.
4. Si Windows muestra una advertencia de seguridad, revisa que hayas descargado el ejecutable desde el repositorio oficial antes de permitir su ejecución.

No necesitas instalar Python ni dependencias adicionales.

### 🐧 Linux (Ubuntu, Debian y Linux Mint)

FileOrganizer también está disponible como paquete `.deb` para sistemas Linux de arquitectura **AMD64 (x86_64)**.

**Instalación mediante interfaz gráfica:**

1. Entra a [Releases](https://github.com/TonoConSal/TCS-FileOrganizer/releases).
2. Descarga `FileOrganizer_2.5.0_amd64.deb`.
3. Abre el archivo descargado con el instalador de paquetes de tu distribución.
4. Haz clic en **Instalar** y espera a que termine el proceso.
5. Busca **FileOrganizer** en el menú de aplicaciones y ábrelo.

**Instalación desde la terminal:**

También puedes instalarlo ejecutando el siguiente comando desde la carpeta donde descargaste el paquete:

```bash
sudo apt install ./FileOrganizer_2.5.0_amd64.deb
```

Una vez instalado, podrás iniciar FileOrganizer desde el menú de aplicaciones.

No necesitas instalar Python ni las dependencias del proyecto por separado.

### 📂 Organizar una carpeta

Una vez abierta la aplicación, sigue estos pasos:

1. En **Carpeta a organizar**, haz clic en **Examinar** y selecciona la carpeta que deseas organizar.
2. Si utilizas una configuración personalizada, selecciónala en el campo correspondiente. Este paso es opcional.
3. Ajusta las opciones según tus preferencias.
4. Haz clic en **Organizar ahora**.
5. Consulta los resultados en la sección **Actividad**.

¡Listo! FileOrganizer clasificará los archivos en subcarpetas según su tipo.

---
## 📂 ¿Dónde van a parar mis archivos?

FileOrganizer crea subcarpetas automáticamente según el tipo de archivo detectado.

| Subcarpeta | Extensiones reconocidas |
|---|---|
| Imágenes | `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.svg`, `.tiff`, `.ico`, `.heic` |
| Videos | `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.3gp` |
| Audio | `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.wma`, `.m4a`, `.opus` |
| Documentos | `.pdf`, `.doc`, `.docx`, `.odt`, `.rtf`, `.txt`, `.md`, `.tex` |
| Hojas de cálculo | `.xls`, `.xlsx`, `.ods`, `.csv`, `.tsv` |
| Presentaciones | `.ppt`, `.pptx`, `.odp` |
| Código | `.py`, `.js`, `.ts`, `.html`, `.css`, `.c`, `.cpp`, `.h`, `.java`, `.cs`, `.go`, `.rs`, `.rb`, `.php`, `.sh`, `.bat`, `.ps1`, `.json`, `.xml`, `.yaml`, `.yml`, `.toml`, `.ini`, `.cfg` |
| Ejecutables | `.exe`, `.msi`, `.apk`, `.dmg`, `.deb`, `.rpm`, `.AppImage` |
| Comprimidos | `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz`, `.tar.gz`, `.tar.bz2` |
| Fuentes | `.ttf`, `.otf`, `.woff`, `.woff2` |
| Torrents | `.torrent` |
| Diseño | `.psd`, `.ai`, `.xd`, `.fig`, `.sketch`, `.indd` |
| 3D | `.obj`, `.fbx`, `.stl`, `.blend`, `.3ds`, `.dae` |
| Bases de datos | `.db`, `.sqlite`, `.sql`, `.mdb` |
| eBooks | `.epub`, `.mobi`, `.azw`, `.azw3`, `.cbr`, `.cbz` |
| ISO | `.iso`, `.img`, `.bin`, `.cue` |
| Otros | Archivos que no coincidan con ninguna categoría conocida |

**Nota:** El programa también utiliza la detección MIME como alternativa cuando una extensión no coincide con las categorías configuradas.
---

## ⚙️ Opciones explicadas

### Sí existe el archivo (conflictos)

Elige qué pasa cuando ya hay un archivo con el mismo nombre en la carpeta destino:

| Opción         | Qué hace                                                         |
|----------------|------------------------------------------------------------------|
| **Preguntar**  | Te pregunta caso por caso qué hacer *(recomendado)*             |
| **Renombrar**  | Guarda el nuevo como `archivo_1.pdf`, `archivo_2.pdf`, etc.     |
| **Saltar**     | Lo ignora y lo deja donde está                                   |
| **Sobreescribir** | Reemplaza el archivo existente sin preguntar                 |

---

### 👁 Watcher — organización en tiempo real

Cuando activas el **watcher**, el programa permanece abierto y supervisa la carpeta seleccionada. Cada archivo nuevo que aparezca será organizado automáticamente.

- Haz clic en **👁 Iniciar watcher** para activarlo.
- El botón se pone **rojo** mientras está activo.
- Haz clic en **⏹ Detener watcher** para apagarlo.

> El watcher espera un momento antes de mover cada archivo para asegurarse de que la descarga esté completa.

---

### ☑️ Modo simulación (dry-run)

Marca esta casilla si quieres **ver qué haría el programa sin mover nada**. Útil para revisar antes de organizar por primera vez.

---

## 📋 El log de actividad

La sección **Actividad** muestra en tiempo real las operaciones realizadas por FileOrganizer.

Los mensajes utilizan diferentes colores según su nivel:

- ⚪ Blanco — información general y operaciones completadas.
- 🟡 Amarillo — advertencias, como archivos que fueron saltados.
- 🔴 Rojo — errores durante la ejecución.
- ⚫ Gris — información de depuración.

Puedes utilizar el botón **Limpiar log** para borrar los mensajes visibles en la interfaz.

**Nota:** La versión con interfaz gráfica muestra el registro directamente en la aplicación. El modo de línea de comandos (CLI) también puede generar un archivo `organizer.log` dentro de la carpeta organizada.

---

## 🛠️ Configuración personalizada (avanzado)

FileOrganizer permite personalizar su comportamiento mediante archivos de configuración `.toml` o `.json`.

Estos archivos permiten modificar las categorías, agregar nuevas extensiones y ajustar opciones como el comportamiento ante conflictos entre archivos.

Puedes encontrar archivos de ejemplo en el repositorio. Descarga el formato que prefieras, edítalo con un editor de texto y cárgalo mediante el botón **Examinar** en el campo de configuración de la aplicación.

Si no cargas un archivo personalizado, FileOrganizer utilizará su configuración predeterminada.

---

## ❓ Preguntas frecuentes

**¿Borra archivos?**  
No. FileOrganizer mueve los archivos a subcarpetas dentro de la carpeta seleccionada. Sin embargo, la opción **Sobrescribir** puede reemplazar archivos existentes si se produce un conflicto.

**¿Funciona en otras carpetas además de Descargas?**  
Sí. Puedes seleccionar cualquier carpeta mediante el botón **Examinar**.

**¿Organiza subcarpetas también?**  
No. Actualmente solo organiza los archivos que están directamente dentro de la carpeta seleccionada.

**¿Qué pasa si cierro el programa con el watcher activo?**  
El watcher se detiene automáticamente al cerrar la aplicación.

**¿Tengo que volver a configurarlo cada vez que lo abro?**  
Sí. La aplicación no guarda la configuración entre sesiones, por lo que tendrás que seleccionar nuevamente la carpeta que quieres organizar y cargar tu archivo TOML o JSON si utilizas una configuración personalizada.

**¿Necesito instalar Python o alguna dependencia?**  
No. Las versiones compiladas para Windows y Linux incluyen lo necesario para ejecutar la aplicación.

**¿Puedo recuperar un archivo después de organizarlo?**  
Sí. Los archivos se mueven a subcarpetas dentro de la carpeta seleccionada. Puedes moverlos manualmente a su ubicación anterior si lo necesitas.

---

## 🐛 Reportar un problema

¿Algo no funcionó como esperabas? Abre un [Issue]([Issues](https://github.com/TonoConSal/TCS-FileOrganizer/issues)) en este repositorio describiendo qué pasó y en qué tipo de archivo ocurrió.
