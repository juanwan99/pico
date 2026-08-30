"""Pico control-plane API."""

# uvicorn loads this file before main.py puts the orchestrator package on sys.path.
# Do not import the orchestrator package or openai_compat here.
from __future__ import annotations

import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder


class _EduSidebarPiBoot(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != "app.openai_compat":
            return None
        spec = PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        orig = spec.loader

        class _Loader:
            def create_module(self, spec):
                if hasattr(orig, "create_module"):
                    return orig.create_module(spec)
                return None

            def exec_module(self, module):
                orig.exec_module(module)
                from app.edu_sidebar_pi import install_edu_sidebar_pi

                install_edu_sidebar_pi(module)

        spec.loader = _Loader()
        return spec


if not any(isinstance(item, _EduSidebarPiBoot) for item in sys.meta_path):
    sys.meta_path.insert(0, _EduSidebarPiBoot())
