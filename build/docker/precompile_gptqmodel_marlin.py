"""Precompile GPTQModel Marlin extensions during the Docker worker-venv build.

Docker builds have no GPU. GPTQModel refuses to JIT-compile Marlin when
``torch.cuda.is_available()`` is false, so this script reports CUDA as available
after import and compiles against ``TORCH_CUDA_ARCH_LIST``. The resulting shared
libraries are copied to a stable path under the venv so the runtime image can
load them without nvcc.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> None:
    from gptqmodel import extension
    import torch

    torch.cuda.is_available = lambda: True
    results = extension.load("marlin")
    missing = [name for name, ok in results.items() if not ok]
    if missing:
        raise RuntimeError(f"Marlin precompile failed for: {', '.join(missing)}")

    cache_root = Path.home() / ".cache" / "gptqmodel" / "torch_extensions"
    dest = Path(sys.prefix) / "gptqmodel_prebuilt" / "marlin"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for library_name in (
        "gptqmodel_marlin_fp16_ops.so",
        "gptqmodel_marlin_bf16_ops.so",
    ):
        matches = sorted(cache_root.rglob(library_name))
        if not matches:
            raise RuntimeError(
                f"Marlin library `{library_name}` was not produced under `{cache_root}`"
            )
        shutil.copy2(matches[0], dest / library_name)
        print(f"copied {matches[0]} -> {dest / library_name}", flush=True)

    shutil.rmtree(cache_root, ignore_errors=True)
    print(f"Marlin prebuilt libraries ready under {dest}", flush=True)


if __name__ == "__main__":
    main()
