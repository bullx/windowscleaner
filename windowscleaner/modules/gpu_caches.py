"""GPU / DirectX shader caches - regenerates on next use (pc_cleaner / TempCleaner)."""

from __future__ import annotations

import os
from pathlib import Path

from windowscleaner.modules.base import CleanItem, CleanModule, ModuleResult, ProgressCb, Risk
from windowscleaner.utils.fs import clear_directory_contents, merge_results
from windowscleaner.utils.size import path_size


def _targets() -> list[tuple[str, str, Path]]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    return [
        ("d3d", "Direct3D shader cache", local / "D3DSCache"),
        ("dxcache", "DXCache", local / "Microsoft" / "DXCache"),
        ("nvidia_gl", "NVIDIA GL cache", local / "NVIDIA" / "GLCache"),
        ("nvidia_dx", "NVIDIA DX cache", local / "NVIDIA" / "DXCache"),
        ("amd_dx", "AMD DX cache", local / "AMD" / "DxCache"),
        ("amd_gl", "AMD GL cache", local / "AMD" / "GLCache"),
        ("intel", "Intel shader cache", local / "Intel" / "ShaderCache"),
    ]


class GpuCachesModule(CleanModule):
    id = "gpu_caches"
    label = "GPU / Shader Caches"
    description = (
        "Clears DirectX / NVIDIA / AMD / Intel shader caches. Safe; games may hitch briefly "
        "while shaders rebuild. Widely used by community PC cleaners."
    )
    risk = Risk.SAFE
    requires_admin = False
    default_enabled = True

    def scan(self, progress: ProgressCb | None = None) -> ModuleResult:
        result = ModuleResult(module_id=self.id, label=self.label)
        for item_id, label, path in _targets():
            if progress:
                progress(f"Scanning {label}")
            size = path_size(path)
            if size <= 0:
                continue
            result.items.append(
                CleanItem(id=item_id, label=label, detail=str(path), bytes_estimate=size)
            )
        return result

    def clean(self, *, dry_run: bool = False, progress: ProgressCb | None = None) -> ModuleResult:
        if dry_run:
            result = self.scan(progress)
            result.dry_run = True
            result.bytes_freed = result.bytes_estimate
            for item in result.items:
                result.actions.append(f"Would clean {item.label}")
            return result

        result = ModuleResult(module_id=self.id, label=self.label, dry_run=False)
        results = []
        for item_id, label, path in _targets():
            try:
                if not path.exists():
                    continue
            except OSError:
                continue
            result.items.append(CleanItem(id=item_id, label=label, detail=str(path)))
            if progress:
                progress(f"Cleaning {label}")
            results.append(clear_directory_contents(path, dry_run=False))
            result.actions.append(f"Cleaned {label}")
        merged = merge_results(*results) if results else None
        if merged:
            result.bytes_freed = merged.bytes_freed
            result.errors.extend(merged.errors)
        return result
