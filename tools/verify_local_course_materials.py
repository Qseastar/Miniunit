#!/usr/bin/env python3
"""Optionally verify local course PDFs against the tracked metadata manifest."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.course_material_manifest import (  # noqa: E402
    CourseMaterialManifestError,
    load_course_material_manifest,
)


class LocalMaterialIntegrityError(ValueError):
    """Raised when an available local PDF disagrees with its tracked digest."""


PageCounter = Callable[[Path], int]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pdfinfo_page_count(path: Path) -> int:
    executable = shutil.which("pdfinfo")
    if executable is None:
        raise LocalMaterialIntegrityError("pdfinfo is required to verify local PDF page counts.")
    try:
        completed = subprocess.run(
            [executable, str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise LocalMaterialIntegrityError(
            f"pdfinfo failed while verifying local material: {type(error).__name__}."
        ) from None
    for line in completed.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                page_count = int(line.split(":", 1)[1].strip())
            except ValueError:
                break
            if page_count > 0:
                return page_count
    raise LocalMaterialIntegrityError("pdfinfo did not return a positive page count.")


def verify_local_course_materials(
    *,
    manifest_path: str | Path,
    materials_root: str | Path,
    require: bool = False,
    page_counter: PageCounter = pdfinfo_page_count,
) -> dict[str, Any]:
    """Verify local files when present; allow ordinary CI to remain PDF-free.

    Missing materials report ``unavailable`` unless ``require`` is true. Any
    material that is present must match the tracked size, digest, and page count.
    """
    manifest = load_course_material_manifest(manifest_path)
    root = Path(materials_root)
    missing: list[str] = []
    verified: list[str] = []
    for material in manifest["materials"]:
        relative = Path(material["source_role"]) / material["source_file"]
        path = root / relative
        if not path.exists():
            missing.append(relative.as_posix())
            continue
        if not path.is_file():
            raise LocalMaterialIntegrityError("Local course material path is not a regular file.")
        if path.stat().st_size != material["size_bytes"]:
            raise LocalMaterialIntegrityError("Local course material size does not match manifest.")
        if sha256_file(path) != material["sha256"]:
            raise LocalMaterialIntegrityError("Local course material SHA-256 does not match manifest.")
        if page_counter(path) != material["page_count"]:
            raise LocalMaterialIntegrityError("Local course material page count does not match manifest.")
        verified.append(relative.as_posix())
    if missing and require:
        raise LocalMaterialIntegrityError("Required local course materials are unavailable.")
    return {
        "status": "unavailable" if missing else "pass",
        "verified_materials": verified,
        "missing_materials": missing,
        "required": require,
    }


def _require_from_environment() -> bool:
    value = os.environ.get("INTROAI_REQUIRE_LOCAL_MATERIALS", "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "course_material_manifest.json")
    parser.add_argument("--materials-root", type=Path, default=ROOT / "local_materials")
    parser.add_argument("--require", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify_local_course_materials(
            manifest_path=args.manifest,
            materials_root=args.materials_root,
            require=args.require or _require_from_environment(),
        )
    except (CourseMaterialManifestError, LocalMaterialIntegrityError) as error:
        print(f"local course material integrity: fail ({type(error).__name__})", file=sys.stderr)
        return 1
    print(
        "local course material integrity: "
        f"{result['status']} (verified={len(result['verified_materials'])}, "
        f"missing={len(result['missing_materials'])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
