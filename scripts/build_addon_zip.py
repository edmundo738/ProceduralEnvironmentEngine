"""
Empacota a pasta `procedural_environment_engine/` num ficheiro `.zip`
pronto a baixar do GitHub e instalar diretamente no Blender 5.2+
(`Edit > Preferences > Add-ons > Install from Disk`).
"""

import zipfile
from pathlib import Path


def build_zip(output_dir: str = "releases") -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    addon_dir = repo_root / "procedural_environment_engine"
    out_folder = repo_root / output_dir
    out_folder.mkdir(parents=True, exist_ok=True)
    zip_path = out_folder / "procedural_environment_engine_v0.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(addon_dir.rglob("*")):
            if file_path.is_dir():
                continue
            if "__pycache__" in file_path.parts or file_path.suffix in (".pyc", ".pyo"):
                continue
            arcname = file_path.relative_to(repo_root)
            zf.write(file_path, arcname)

    print(f"[Build] Add-on empacotado com sucesso em: {zip_path} ({zip_path.stat().st_size:,} bytes)")
    return zip_path


if __name__ == "__main__":
    build_zip()
