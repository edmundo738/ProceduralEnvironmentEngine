"""
LAYER 1 — SCENE ANALYZER
Observes and measures the Blender scene without modifying anything.
"""

from typing import Optional, List, Dict, Set, Tuple, Any
from ..config import SNAPSHOT_PROP_KEY, PREFIX
from .data_models import (
    SceneRawAnalysis,
    TerrainObjectMetrics,
    OtherObjectMetrics,
    ModifierMetrics,
    MaterialMetrics,
    PBRMapInfo,
    EpistemicTag,
)


def classify_pbr_channel(image_name: str) -> str:
    """Classifies an image datablock name into a standard PBR channel role."""
    lower = image_name.lower()
    if any(k in lower for k in ("_diff", "diffuse", "albedo", "basecolor", "base_color", "_col")):
        return "DIFFUSE"
    if any(k in lower for k in ("_nor", "normal", "_nrm", "nor_gl", "nor_dx")):
        return "NORMAL"
    if any(k in lower for k in ("_rough", "roughness", "_rgh")):
        return "ROUGHNESS"
    if any(k in lower for k in ("_disp", "displacement", "_height", "_bump")):
        return "DISPLACEMENT"
    if any(k in lower for k in ("_ao", "ambient_occlusion")):
        return "AO"
    return "OTHER"


def find_connected_nodes(node_tree: Any) -> Set[Any]:
    """
    Walks backwards from active Material Output / Group Output nodes
    to determine which nodes are genuinely connected to the shader output.
    """
    if not node_tree or not getattr(node_tree, "nodes", None):
        return set()

    output_nodes = [
        n for n in node_tree.nodes
        if getattr(n, "bl_idname", "") in ("ShaderNodeOutputMaterial", "NodeGroupOutput")
        or getattr(n, "type", "") in ("OUTPUT_MATERIAL", "GROUP_OUTPUT")
    ]
    if not output_nodes:
        output_nodes = list(node_tree.nodes)

    visited: Set[Any] = set()
    stack = list(output_nodes)
    while stack:
        curr = stack.pop()
        if curr in visited:
            continue
        visited.add(curr)
        for inp in getattr(curr, "inputs", []):
            for link in getattr(inp, "links", []):
                from_node = getattr(link, "from_node", None)
                if from_node and from_node not in visited:
                    stack.append(from_node)
    return visited


class SceneAnalyzer:
    """
    Layer 1: Pure diagnostic observer of a Blender scene.
    Accepts `bpy` module (or a compatible mock for automated testing).
    """

    def __init__(self, bpy_module: Any = None):
        if bpy_module is None:
            import bpy as _bpy
            self.bpy = _bpy
        else:
            self.bpy = bpy_module

    def analyze(
        self,
        scene: Any = None,
        preferred_terrain_name: Optional[str] = None,
    ) -> SceneRawAnalysis:
        if scene is None:
            scene = self.bpy.context.scene

        app_ver = getattr(self.bpy.app, "version_string", "Unknown")
        unit_settings = getattr(scene, "unit_settings", None)
        unit_system = getattr(unit_settings, "system", "METRIC") if unit_settings else "METRIC"
        unit_scale = float(getattr(unit_settings, "scale_length", 1.0)) if unit_settings else 1.0

        render = getattr(scene, "render", None)
        render_engine = getattr(render, "engine", "CYCLES") if render else "CYCLES"
        res_x = int(getattr(render, "resolution_x", 1920)) if render else 1920
        res_y = int(getattr(render, "resolution_y", 1080)) if render else 1080
        res_pct = int(getattr(render, "resolution_percentage", 100)) if render else 100

        objects = list(getattr(scene, "objects", []))
        mesh_objs = [o for o in objects if getattr(o, "type", "") == "MESH"]
        cam_objs = [o for o in objects if getattr(o, "type", "") == "CAMERA"]
        light_objs = [o for o in objects if getattr(o, "type", "") == "LIGHT"]

        terrain_obj = self._select_primary_terrain(mesh_objs, preferred_terrain_name)

        # Scan all images in bpy.data.images first
        all_images, available_pbr = self._scan_blend_images()

        primary_terrain_metrics: Optional[TerrainObjectMetrics] = None
        if terrain_obj is not None:
            primary_terrain_metrics = self._inspect_terrain_object(terrain_obj, available_pbr)

        other_objects: List[OtherObjectMetrics] = []
        for obj in objects:
            if terrain_obj is not None and obj.name == terrain_obj.name:
                continue
            other_objects.append(self._inspect_other_object(obj))

        world = getattr(scene, "world", None)
        world_name = getattr(world, "name", None) if world else None
        world_has_sky = False
        if world and getattr(world, "use_nodes", False) and getattr(world, "node_tree", None):
            for n in world.node_tree.nodes:
                if getattr(n, "type", "") == "TEX_SKY" or "Sky" in getattr(n, "bl_idname", ""):
                    world_has_sky = True
                    break

        has_snapshot = False
        try:
            has_snapshot = SNAPSHOT_PROP_KEY in scene
        except Exception:
            has_snapshot = False

        return SceneRawAnalysis(
            blender_version=str(app_ver),
            scene_name=getattr(scene, "name", "Scene"),
            unit_system=str(unit_system),
            unit_scale=unit_scale,
            render_engine=str(render_engine),
            resolution_x=res_x,
            resolution_y=res_y,
            resolution_percentage=res_pct,
            total_objects=len(objects),
            mesh_objects_count=len(mesh_objs),
            camera_objects_count=len(cam_objs),
            light_objects_count=len(light_objs),
            primary_terrain=primary_terrain_metrics,
            other_objects=other_objects,
            available_pbr_maps=available_pbr,
            all_blend_images=all_images,
            world_name=world_name,
            world_has_sky_texture=world_has_sky,
            has_existing_snapshot=has_snapshot,
        )

    def _select_primary_terrain(
        self,
        mesh_objs: List[Any],
        preferred_name: Optional[str] = None,
    ) -> Optional[Any]:
        if not mesh_objs:
            return None

        if preferred_name:
            for obj in mesh_objs:
                if obj.name == preferred_name:
                    return obj

        # Score candidates by: explicit terrain/plane naming + vertex density + horizontal XY area
        def score_candidate(obj: Any) -> float:
            dims = getattr(obj, "dimensions", (0.0, 0.0, 0.0))
            area_xy = float(dims[0]) * float(dims[1])
            mesh = getattr(obj, "data", None)
            v_count = len(getattr(mesh, "vertices", [])) if mesh else 0
            name_lower = obj.name.lower()

            score = area_xy
            if any(k in name_lower for k in ("terrain", "plane", "ground", "desert", "landscape", "proc_env")):
                score *= 3.0
            if v_count >= 1000:
                score *= 5.0
            elif v_count < 64:
                # Low-poly primitives like the 24-vertex Cone shouldn't beat a dense terrain
                score *= 0.05
            return score

        return max(mesh_objs, key=score_candidate)

    def _inspect_terrain_object(
        self,
        obj: Any,
        available_pbr: Dict[str, PBRMapInfo],
    ) -> TerrainObjectMetrics:
        dims = tuple(round(float(v), 4) for v in getattr(obj, "dimensions", (0.0, 0.0, 0.0)))
        scale = tuple(round(float(v), 4) for v in getattr(obj, "scale", (1.0, 1.0, 1.0)))
        area_m2 = round(dims[0] * dims[1], 2)
        area_km2 = round(area_m2 / 1_000_000.0, 4)

        min_xy = max(min(dims[0], dims[1]), 0.0001)
        max_xy = max(dims[0], dims[1])
        aspect_ratio = round(max_xy / min_xy, 4)

        # Local bounds from bound_box (8 corners)
        bbox = getattr(obj, "bound_box", None)
        if bbox and len(bbox) == 8:
            xs = [float(corner[0]) for corner in bbox]
            ys = [float(corner[1]) for corner in bbox]
            zs = [float(corner[2]) for corner in bbox]
            bounds_x = (round(min(xs), 4), round(max(xs), 4))
            bounds_y = (round(min(ys), 4), round(max(ys), 4))
            bounds_z = (round(min(zs), 4), round(max(zs), 4))
        else:
            bounds_x = (-dims[0] * 0.5, dims[0] * 0.5)
            bounds_y = (-dims[1] * 0.5, dims[1] * 0.5)
            bounds_z = (0.0, dims[2])

        mesh = getattr(obj, "data", None)
        base_verts = len(getattr(mesh, "vertices", [])) if mesh else 0
        base_edges = len(getattr(mesh, "edges", [])) if mesh else 0
        base_polys = len(getattr(mesh, "polygons", [])) if mesh else 0

        uv_maps: List[str] = []
        if mesh and getattr(mesh, "uv_layers", None):
            uv_maps = [uv.name for uv in mesh.uv_layers]

        modifiers_list: List[ModifierMetrics] = []
        est_view_polys = base_polys
        est_render_polys = base_polys

        for mod in getattr(obj, "modifiers", []):
            m_type = str(getattr(mod, "type", "UNKNOWN"))
            show_v = bool(getattr(mod, "show_viewport", True))
            show_r = bool(getattr(mod, "show_render", True))
            details: Dict[str, Any] = {}

            if m_type == "SUBSURF":
                v_lvl = int(getattr(mod, "levels", 1))
                r_lvl = int(getattr(mod, "render_levels", 2))
                details["viewport_levels"] = v_lvl
                details["render_levels"] = r_lvl
                if show_v and v_lvl > 0:
                    est_view_polys *= (4 ** v_lvl)
                if show_r and r_lvl > 0:
                    est_render_polys *= (4 ** r_lvl)
            elif m_type == "DISPLACE":
                details["strength"] = round(float(getattr(mod, "strength", 0.0)), 4)
                details["mid_level"] = round(float(getattr(mod, "mid_level", 0.5)), 4)
                tex = getattr(mod, "texture", None)
                details["texture_name"] = getattr(tex, "name", None) if tex else None
                details["texture_type"] = getattr(tex, "type", None) if tex else None
            elif m_type == "NODES":
                ng = getattr(mod, "node_group", None)
                details["node_group_name"] = getattr(ng, "name", None) if ng else None
                if ng and getattr(ng, "nodes", None):
                    details["node_count"] = len(ng.nodes)
                    details["node_types"] = [getattr(n, "bl_idname", getattr(n, "type", "")) for n in ng.nodes]

            modifiers_list.append(
                ModifierMetrics(
                    name=str(mod.name),
                    mod_type=m_type,
                    show_viewport=show_v,
                    show_render=show_r,
                    details=details,
                )
            )

        active_mat = getattr(obj, "active_material", None)
        if active_mat is None and mesh and getattr(mesh, "materials", None) and len(mesh.materials) > 0:
            active_mat = mesh.materials[0]

        mat_metrics: Optional[MaterialMetrics] = None
        if active_mat is not None:
            mat_metrics = self._inspect_material(active_mat, available_pbr)

        return TerrainObjectMetrics(
            name=str(obj.name),
            dimensions_m=dims,
            area_m2=area_m2,
            area_km2=area_km2,
            aspect_ratio_xy=aspect_ratio,
            local_bounds_x=bounds_x,
            local_bounds_y=bounds_y,
            local_bounds_z=bounds_z,
            scale=scale,
            base_vertices=base_verts,
            base_edges=base_edges,
            base_polygons=base_polys,
            uv_maps=uv_maps,
            modifiers=modifiers_list,
            active_material=mat_metrics,
            estimated_viewport_polygons=est_view_polys,
            estimated_render_polygons=est_render_polys,
        )

    def _inspect_material(
        self,
        mat: Any,
        available_pbr: Dict[str, PBRMapInfo],
    ) -> MaterialMetrics:
        use_nodes = bool(getattr(mat, "use_nodes", False))
        nt = getattr(mat, "node_tree", None) if use_nodes else None
        if not nt or not getattr(nt, "nodes", None):
            return MaterialMetrics(name=str(mat.name), use_nodes=use_nodes, node_count=0)

        nodes = list(nt.nodes)
        connected_set = find_connected_nodes(nt)
        node_types = [str(getattr(n, "bl_idname", getattr(n, "type", ""))) for n in nodes]
        node_names = [str(getattr(n, "name", "")) for n in nodes]

        connected_images: List[str] = []
        has_mapping = False
        has_proc_env = PREFIX in str(mat.name)

        for n in connected_set:
            bl_id = str(getattr(n, "bl_idname", ""))
            n_type = str(getattr(n, "type", ""))
            if PREFIX in str(getattr(n, "name", "")):
                has_proc_env = True
            if bl_id == "ShaderNodeMapping" or n_type == "MAPPING":
                has_mapping = True
            if bl_id == "ShaderNodeTexImage" or n_type == "TEX_IMAGE":
                img = getattr(n, "image", None)
                if img is not None:
                    img_name = str(img.name)
                    connected_images.append(img_name)
                    for role_info in available_pbr.values():
                        if role_info.image_name == img_name:
                            role_info.is_connected_to_active_material = True

        uses_pbr = len(connected_images) > 0
        return MaterialMetrics(
            name=str(mat.name),
            use_nodes=use_nodes,
            node_count=len(nodes),
            node_types=node_types,
            node_names=node_names,
            connected_image_names=connected_images,
            uses_pbr_maps=uses_pbr,
            has_explicit_mapping_node=has_mapping,
            has_proc_env_signature=has_proc_env,
        )

    def _scan_blend_images(self) -> Tuple[List[PBRMapInfo], Dict[str, PBRMapInfo]]:
        all_infos: List[PBRMapInfo] = []
        best_by_role: Dict[str, PBRMapInfo] = {}

        images = getattr(getattr(self.bpy, "data", None), "images", [])
        for img in images:
            name = str(getattr(img, "name", ""))
            if name in ("Render Result", "Viewer Node"):
                continue
            size = getattr(img, "size", (0, 0))
            res = (int(size[0]), int(size[1])) if len(size) >= 2 else (0, 0)
            source = str(getattr(img, "source", "FILE"))
            cs_settings = getattr(img, "colorspace_settings", None)
            colorspace = str(getattr(cs_settings, "name", "sRGB")) if cs_settings else "sRGB"
            is_packed = getattr(img, "packed_file", None) is not None
            has_data = bool(getattr(img, "has_data", True))
            role = classify_pbr_channel(name)

            info = PBRMapInfo(
                image_name=name,
                channel_role=role,
                resolution=res,
                source=source,
                colorspace=colorspace,
                is_packed=is_packed,
                has_data=has_data,
                is_connected_to_active_material=False,
            )
            all_infos.append(info)
            if role != "OTHER":
                # Prefer higher resolution or sand-named textures for desert
                existing = best_by_role.get(role)
                if existing is None or ("sand" in name.lower() and "sand" not in existing.image_name.lower()):
                    best_by_role[role] = info

        return all_infos, best_by_role

    def _inspect_other_object(self, obj: Any) -> OtherObjectMetrics:
        dims = tuple(round(float(v), 4) for v in getattr(obj, "dimensions", (0.0, 0.0, 0.0)))
        scale = tuple(round(float(v), 4) for v in getattr(obj, "scale", (1.0, 1.0, 1.0)))
        o_type = str(getattr(obj, "type", "UNKNOWN"))
        mesh = getattr(obj, "data", None) if o_type == "MESH" else None
        verts = len(getattr(mesh, "vertices", [])) if mesh else 0
        polys = len(getattr(mesh, "polygons", [])) if mesh else 0
        mats: List[str] = []
        if mesh and getattr(mesh, "materials", None):
            mats = [m.name for m in mesh.materials if m is not None]

        # Do NOT assume semantic role of unclassified meshes (like the 24-vertex Cone!)
        semantic_role = EpistemicTag.UNKNOWN
        if o_type == "CAMERA":
            semantic_role = "SCENE_CAMERA"
        elif o_type == "LIGHT":
            semantic_role = "SCENE_LIGHT"

        return OtherObjectMetrics(
            name=str(obj.name),
            obj_type=o_type,
            dimensions_m=dims,
            scale=scale,
            vertices=verts,
            polygons=polys,
            material_names=mats,
            semantic_role=semantic_role,
        )
