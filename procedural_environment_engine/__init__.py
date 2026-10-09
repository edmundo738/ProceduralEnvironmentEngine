"""
Procedural Environment Engine (ProcEnv V0) — Installable Blender 5.2+ LTS Add-on & Modular Core.

Can be used in two ways:
1. Installed as a Blender Add-on / Extension (.zip):
   Opens the `ProcEnv` tab in the 3D Viewport N-Panel (`View3D > Sidebar > ProcEnv`)
   with 1-Click 'AUTO (Preguiçoso)' generation, Scene Diagnostics, Guided Conflict Policy,
   Real-Time Manual Sliders, and 1-Click Rollback.
2. Imported or run via script (`scripts/run_v0_desert.py`):
   Uses `ProceduralEnvironmentEngine` directly in Python.
"""

bl_info = {
    "name": "Procedural Environment Engine (ProcEnv V0.4 - CP-04)",
    "author": "Edmundo & ProcEnv Engineering",
    "version": (0, 4, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > ProcEnv",
    "description": (
        "Complete Ready-Made Scenario Engine: Multi-Biome Terrains, Universal Road Carve System, "
        "Procedural Houses/Buildings, Props, Rocks, Vegetation, Decals & Hybrid PBR 4K"
    ),
    "category": "3D View",
}

from typing import List, Any
from .config import (
    TerrainEngineParams,
    ConflictStrategy,
    OperationMode,
    PerformanceProfile,
    MappingMethod,
)
from .core.engine import ProceduralEnvironmentEngine

_REGISTERED_CLASSES: List[Any] = []


def register() -> None:
    import bpy
    from bpy.props import PointerProperty
    from .ui.properties import get_properties_class
    from .ui.operators import get_operator_classes
    from .ui.panels import get_panel_classes

    global _REGISTERED_CLASSES
    _REGISTERED_CLASSES.clear()

    prop_cls = get_properties_class(bpy)
    op_classes = get_operator_classes(bpy)
    panel_classes = get_panel_classes(bpy)

    all_classes = [prop_cls, *op_classes, *panel_classes]
    for cls in all_classes:
        bpy.utils.register_class(cls)
        _REGISTERED_CLASSES.append(cls)

    bpy.types.Scene.proc_env_settings = PointerProperty(type=prop_cls)


def unregister() -> None:
    import bpy

    global _REGISTERED_CLASSES
    if hasattr(bpy.types.Scene, "proc_env_settings"):
        delattr(bpy.types.Scene, "proc_env_settings")

    for cls in reversed(_REGISTERED_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _REGISTERED_CLASSES.clear()


if __name__ == "__main__":
    register()
