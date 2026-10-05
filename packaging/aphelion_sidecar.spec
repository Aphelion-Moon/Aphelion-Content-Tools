from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata


project_root = Path(SPECPATH).parent
entry_point = project_root / "webapp" / "serve_api.py"

binaries: list[tuple[str, str]] = []
datas: list[tuple[str, str]] = [
	(str(project_root / "webapp" / "frontend" / "dist"), "webapp/frontend/dist"),
]
hiddenimports = ["webapp.store_worker"]

for package in ("fastembed", "lancedb"):
	package_datas, package_binaries, package_hiddenimports = collect_all(package)
	datas.extend(package_datas)
	binaries.extend(package_binaries)
	hiddenimports.extend(package_hiddenimports)

for distribution in ("fastembed", "lancedb", "onnxruntime", "Pillow", "pyarrow"):
	datas.extend(copy_metadata(distribution))

model_cache = Path(os.environ.get("LOCALAPPDATA", "")) / "AphelionContentTools" / "models"
if not model_cache.is_dir():
	raise SystemExit(f"FastEmbed model cache is unavailable: {model_cache}")
datas.append((str(model_cache), "models"))

analysis = Analysis(
	[str(entry_point)],
	pathex=[str(project_root)],
	binaries=binaries,
	datas=datas,
	hiddenimports=hiddenimports,
	hookspath=[],
	hooksconfig={},
	runtime_hooks=[],
	excludes=["pytest", "unittest"],
	noarchive=False,
	optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
	pyz,
	analysis.scripts,
	[],
	exclude_binaries=True,
	name="aphelion-sidecar",
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=False,
	console=True,
)

coll = COLLECT(
	exe,
	analysis.binaries,
	analysis.datas,
	strip=False,
	upx=False,
	upx_exclude=[],
	name="aphelion-sidecar",
)
