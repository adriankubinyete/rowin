import os
import subprocess
import sys

import autoit


def build():
    # Pega o caminho da DLL do autoit dinamicamente
    import_path = os.path.dirname(autoit.__file__)
    dll_path = os.path.join(import_path, "lib", "AutoItX3_x64.dll")

    # Nome do script principal - altere se quiser
    script = "main.py"

    # Nome do exe gerado (igual ao script sem extensão)
    exe_name = "rowin"

    # Monta o comando PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        script,
        "--onefile",
        "--windowed",  # para não abrir terminal na execução (Tkinter)
        f"--name={exe_name}",
        f"--add-binary={dll_path};autoit/lib",
        "--hidden-import=src.app",
    ]

    print("Running command:")
    print(" ".join(cmd))

    # Executa o build
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    build()
