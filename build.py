
"""
build.py - Compila organizer_gui.py con PyInstaller.

Uso:
    python build.py

Requisitos:
    pip install pyinstaller watchdog tomli
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
APP_NAME = "FileOrganizer"
ICON_DIR = HERE / "assets" / "icons"
WINDOWS_ICON = ICON_DIR / "fileorganizer.ico"
LINUX_ICON = ICON_DIR / "fileorganizer.png"


def main():
    is_windows = sys.platform == "win32"
    executable_name = f"{APP_NAME}.exe" if is_windows else APP_NAME

    print(f"🔨 Compilando {APP_NAME} para {sys.platform}")
    print("─" * 45)

    # Verifica PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller no instalado. Instalando...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "pyinstaller"
        ])

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--add-data",
        f"{HERE / 'organizer.py'}{';' if is_windows else ':'}.",
        str(HERE / "organizer_gui.py"),
    ]
    if is_windows and WINDOWS_ICON.exists():
        cmd.extend(["--icon", str(WINDOWS_ICON)])

    icon_path = HERE / ("icon.ico" if is_windows else "icon.png")
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    print(f"Comando: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=HERE)

    if result.returncode == 0:
        executable = HERE / "dist" / executable_name

        print("\n✅ Build exitoso!")
        print(f"   Ejecutable: {executable}")
        print("\n📦 Archivos generados:")
        print(f"   • {executable}")
        print("   • organizer_config.toml (opcional)")
    else:
        print("\n❌ Build falló. Revisa el output arriba.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
