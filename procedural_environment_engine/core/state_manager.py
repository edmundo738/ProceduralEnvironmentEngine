"""
STATE & REVERSIBILITY MANAGER (Sections 12 & 15 — Updated for CP-02)
Guarantees non-destructive operations, single clean material backups (preventing
_PROC_BACKUP_PROC_BACKUP chains), collection organization, and 1-click rollback.
"""

import json
from typing import Any, Dict
from ..config import (
    PREFIX,
    TERRAIN_MODIFIER_NAME,
    SURFACE_MATERIAL_NAME,
    BACKUP_SUFFIX,
    SNAPSHOT_PROP_KEY,
    COLLECTION_HIERARCHY,
)


def strip_backup_suffixes(mat_name: str) -> str:
    """Removes any repeated `_PROC_BACKUP` suffixes from a material name."""
    clean = str(mat_name)
    while clean.endswith(BACKUP_SUFFIX):
        clean = clean[: -len(BACKUP_SUFFIX)]
    return clean


class StateManager:
    """Manages snapshots, backups, collections, and reversible rollbacks."""

    def __init__(self, bpy_module: Any = None):
        if bpy_module is None:
            import bpy as _bpy
            self.bpy = _bpy
        else:
            self.bpy = bpy_module

    def ensure_collection_hierarchy(self, scene: Any = None) -> Dict[str, Any]:
        """
        Ensures the non-destructive collection hierarchy exists:
        PROC_ENV/
            TERRAIN, SURFACE, ROCKS, VEGETATION, LIGHTING, CAMERA
        """
        if scene is None:
            scene = self.bpy.context.scene

        collections_data = getattr(self.bpy.data, "collections", None)
        if collections_data is None:
            return {}

        root_col = collections_data.get(PREFIX)
        if root_col is None:
            root_col = collections_data.new(PREFIX)
            if hasattr(scene, "collection") and hasattr(scene.collection, "children"):
                if root_col.name not in [c.name for c in scene.collection.children]:
                    scene.collection.children.link(root_col)

        sub_cols: Dict[str, Any] = {"ROOT": root_col}
        for sub_name in COLLECTION_HIERARCHY:
            full_name = f"{PREFIX}_{sub_name}"
            sub_col = collections_data.get(full_name)
            if sub_col is None:
                sub_col = collections_data.new(full_name)
            if hasattr(root_col, "children") and sub_col.name not in [c.name for c in root_col.children]:
                root_col.children.link(sub_col)
            sub_cols[sub_name] = sub_col

        return sub_cols

    def create_snapshot(self, terrain_obj: Any, scene: Any = None) -> Dict[str, Any]:
        """
        Records the original state of `terrain_obj` (modifiers, active material, visibility)
        into `scene[SNAPSHOT_PROP_KEY]` and creates a single clean backup material datablock.
        """
        if scene is None:
            scene = self.bpy.context.scene

        existing_raw = None
        try:
            existing_raw = scene.get(SNAPSHOT_PROP_KEY, None)
        except Exception:
            existing_raw = None

        if existing_raw:
            try:
                parsed = json.loads(existing_raw)
                if parsed.get("terrain_name") == terrain_obj.name:
                    return parsed
            except Exception:
                pass

        mod_states = []
        for mod in getattr(terrain_obj, "modifiers", []):
            if mod.name == TERRAIN_MODIFIER_NAME:
                continue
            entry: Dict[str, Any] = {
                "name": str(mod.name),
                "type": str(getattr(mod, "type", "")),
                "show_viewport": bool(getattr(mod, "show_viewport", True)),
                "show_render": bool(getattr(mod, "show_render", True)),
            }
            if getattr(mod, "type", "") == "SUBSURF":
                entry["levels"] = int(getattr(mod, "levels", 1))
                entry["render_levels"] = int(getattr(mod, "render_levels", 2))
            elif getattr(mod, "type", "") == "DISPLACE":
                entry["strength"] = float(getattr(mod, "strength", 0.1))
            mod_states.append(entry)

        orig_mat = getattr(terrain_obj, "active_material", None)
        orig_mat_name = str(orig_mat.name) if orig_mat else ""
        base_mat_name = strip_backup_suffixes(orig_mat_name)
        backup_mat_name = ""

        if orig_mat is not None and not base_mat_name.startswith(PREFIX):
            backup_mat_name = self.backup_material(orig_mat)

        snapshot = {
            "terrain_name": str(terrain_obj.name),
            "original_material_name": base_mat_name or orig_mat_name,
            "backup_material_name": backup_mat_name,
            "modifiers": mod_states,
        }

        try:
            scene[SNAPSHOT_PROP_KEY] = json.dumps(snapshot)
        except Exception:
            pass

        return snapshot

    def backup_material(self, mat: Any) -> str:
        """
        Creates a single protected backup of `mat` (`<base_name>_PROC_BACKUP` with `use_fake_user=True`),
        stripping any existing `_PROC_BACKUP` chains so they never multiply.
        """
        base_name = strip_backup_suffixes(mat.name)
        if base_name.startswith(PREFIX) or base_name == SURFACE_MATERIAL_NAME:
            return ""

        backup_name = f"{base_name}{BACKUP_SUFFIX}"
        materials = getattr(self.bpy.data, "materials", None)
        if materials is None:
            return ""

        # If `mat` itself was accidentally named with multiple _PROC_BACKUPs, rename it cleanly
        if mat.name != base_name and mat.name.endswith(BACKUP_SUFFIX):
            existing_base = materials.get(base_name)
            if existing_base is None:
                mat.name = base_name

        existing = materials.get(backup_name)
        if existing is not None:
            existing.use_fake_user = True
            return str(existing.name)

        if hasattr(mat, "copy"):
            copied = mat.copy()
            copied.name = backup_name
            copied.use_fake_user = True
            return str(copied.name)
        return ""

    def restore_snapshot(self, scene: Any = None) -> Dict[str, Any]:
        """
        Reverts the terrain object to its pre-PROC_ENV state:
        - Removes the `PROC_ENV_Terrain` Geometry Nodes modifier
        - Restores `show_viewport`, `show_render`, and levels on all original modifiers
        - Restores the original material (cleanly named without _PROC_BACKUP chains)
        """
        if scene is None:
            scene = self.bpy.context.scene

        raw_json = None
        try:
            raw_json = scene.get(SNAPSHOT_PROP_KEY, None)
        except Exception:
            raw_json = None

        if not raw_json:
            return {"restored": False, "reason": "Nenhum snapshot anterior encontrado na cena."}

        snapshot = json.loads(raw_json)
        t_name = snapshot.get("terrain_name", "")
        objects = getattr(scene, "objects", {})
        terrain_obj = objects.get(t_name) if hasattr(objects, "get") else None
        if terrain_obj is None:
            for o in objects:
                if o.name == t_name:
                    terrain_obj = o
                    break

        if terrain_obj is None:
            return {"restored": False, "reason": f"Objeto '{t_name}' não encontrado."}

        # 1. Remove PROC_ENV_Terrain modifier if present
        proc_mod = None
        for m in getattr(terrain_obj, "modifiers", []):
            if m.name == TERRAIN_MODIFIER_NAME:
                proc_mod = m
                break
        if proc_mod is not None and hasattr(terrain_obj.modifiers, "remove"):
            terrain_obj.modifiers.remove(proc_mod)

        # 2. Restore original modifier states
        saved_mods = {m["name"]: m for m in snapshot.get("modifiers", [])}
        for m in getattr(terrain_obj, "modifiers", []):
            if m.name in saved_mods:
                sm = saved_mods[m.name]
                m.show_viewport = bool(sm.get("show_viewport", True))
                m.show_render = bool(sm.get("show_render", True))
                if "levels" in sm and hasattr(m, "levels"):
                    m.levels = int(sm["levels"])
                if "render_levels" in sm and hasattr(m, "render_levels"):
                    m.render_levels = int(sm["render_levels"])
                if "strength" in sm and hasattr(m, "strength"):
                    m.strength = float(sm["strength"])

        # 3. Restore original material cleanly
        materials = getattr(self.bpy.data, "materials", None)
        orig_mat_name = strip_backup_suffixes(snapshot.get("original_material_name", ""))
        backup_mat_name = snapshot.get("backup_material_name", "")

        if materials is not None:
            orig_mat = materials.get(orig_mat_name) if orig_mat_name else None
            backup_mat = materials.get(backup_mat_name) if backup_mat_name else None

            if orig_mat is not None and not orig_mat.name.startswith(PREFIX):
                terrain_obj.active_material = orig_mat
            elif backup_mat is not None:
                # Copy backup back into the clean original material name
                restored_copy = backup_mat.copy() if hasattr(backup_mat, "copy") else backup_mat
                if orig_mat_name and materials.get(orig_mat_name) is None:
                    restored_copy.name = orig_mat_name
                terrain_obj.active_material = restored_copy

        try:
            del scene[SNAPSHOT_PROP_KEY]
        except Exception:
            pass

        return {
            "restored": True,
            "terrain_name": t_name,
            "restored_material": getattr(terrain_obj.active_material, "name", None),
        }
