"""
build.py - Compila organizer_gui.py en un .exe con PyInstaller.

Uso:
    python build.py

Requisitos:
    pip install pyinstaller watchdog tomli
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

def main():
    print("🔨 Compilando File Organizer → .exe")
    print("─" * 45)

    # Verifica PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller no instalado. Corriendo: pip install pyinstaller")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                        # Un solo .exe
        "--windowed",                       # Sin ventana de consola
        "--name", "FileOrganizer",          # Nombre del ejecutable
        "--add-data", f"{HERE / 'organizer.py'}{';' if sys.platform == 'win32' else ':'}.",
        # Si tienes un ícono .ico descomenta la siguiente línea:
        # "--icon", str(HERE / "icon.ico"),
        str(HERE / "organizer_gui.py"),
    ]

    print(f"Comando: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=HERE)

    if result.returncode == 0:
        exe = HERE / "dist" / "FileOrganizer.exe"
        print("\n✅ Build exitoso!")
        print(f"   Ejecutable: {exe}")
        print("\n📦 Archivos para entregar al cliente:")
        print("   • dist/FileOrganizer.exe")
        print("   • organizer_config.toml  (opcional, para personalización)")
    else:
        print("\n❌ Build falló. Revisa el output arriba.")
        sys.exit(1)


if __name__ == "__main__":
    main()
