"""Load Docker-prebuilt GPTQModel Marlin libraries into the worker venv.

Imported from ``crynux_gptqmodel_marlin.pth`` during site initialization so
every worker process registers the Marlin torch.ops before GPTQModel attempts
JIT. A ``.pth`` import is required because Ubuntu ships
``/usr/lib/python3.10/sitecustomize.py``, which shadows a venv sitecustomize.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _preload_marlin() -> None:
    library_dir = Path(sys.prefix) / "gptqmodel_prebuilt" / "marlin"
    libraries = sorted(library_dir.glob("gptqmodel_marlin_*_ops.so"))
    if not libraries:
        return

    import torch

    if not torch.cuda.is_available():
        return

    for library in libraries:
        torch.ops.load_library(str(library))


_preload_marlin()
