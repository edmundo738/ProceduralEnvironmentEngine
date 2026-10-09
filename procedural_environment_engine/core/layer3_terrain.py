"""
LAYER 3 — TERRAIN & ROAD GENERATOR (CP-03: Multi-Biome Deformations + Universal Road Carve Engine)
Capabilities:
1. Multi-Biome Deformations:
   - Branching Dunes (Voronoi Smooth F1 Web + Smooth SIN Wind Waves)
   - Alpine Mountains & Valleys
   - Savanna Explanadas & Flat-Topped Plateaus / Mesas (`PROC_PlateauMapRange`)
   - Fantasy Terraced Landscapes (`PROC_TerraceQuantize` + `BlurAttribute`)
2. Universal Road & Path Creator (Applicable to Deserts, Mountains, Savannas, Fantasy):
   - Mode A: 1-Click Procedural Winding Road + Smooth Y-Junction Secondary Branch (`PROCEDURAL_WINDING`)
   - Mode B: 3D Curve Guided Road (`CURVE_OBJECT` via `PROC_ENV_Road_Curve` + `GeometryProximity`)
   - Flattens, contours, and carves the terrain along the path with smooth shoulders & side berms.
   - Exports `proc_road_mask` via `GeometryNodeStoreNamedAttribute` so Layer 4 automatically shades the road!
"""

import math
from typing import Any, Dict, Optional
from ..config import (
    TerrainEngineParams,
    ConflictStrategy,
    PerformanceProfile,
    DuneMorphology,
    RoadMode,
    PERFORMANCE_SETTINGS,
    TERRAIN_MODIFIER_NAME,
    TERRAIN_NODE_GROUP_NAME,
    ROAD_CURVE_OBJECT_NAME,
    ROAD_MASK_ATTRIBUTE_NAME,
    PREFIX,
)


def _ensure_gn_socket(
    tree: Any,
    name: str,
    in_out: str,
    socket_type: str,
    default_value: Any = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> Any:
    """Blender 4.0+ / 5.2.1 LTS compatible helper for adding sockets to a GeometryNodeTree."""
    interface = getattr(tree, "interface", None)
    if interface is not None and hasattr(interface, "new_socket"):
        for item in getattr(interface, "items_tree", []):
            if getattr(item, "item_type", "SOCKET") == "SOCKET":
                if getattr(item, "name", "") == name and getattr(item, "in_out", "") == in_out:
                    if min_value is not None and hasattr(item, "min_value"):
                        try:
                            item.min_value = min_value
                        except Exception:
                            pass
                    if max_value is not None and hasattr(item, "max_value"):
                        try:
                            item.max_value = max_value
                        except Exception:
                            pass
                    return item
        sock = interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
        if default_value is not None and hasattr(sock, "default_value"):
            try:
                sock.default_value = default_value
            except Exception:
                pass
        if min_value is not None and hasattr(sock, "min_value"):
            try:
                sock.min_value = min_value
            except Exception:
                pass
        if max_value is not None and hasattr(sock, "max_value"):
            try:
                sock.max_value = max_value
            except Exception:
                pass
        return sock

    collection = getattr(tree, "inputs" if in_out == "INPUT" else "outputs", None)
    if collection is not None and hasattr(collection, "new"):
        sock = collection.new(socket_type, name)
        if default_value is not None and hasattr(sock, "default_value"):
            sock.default_value = default_value
        return sock
    return None


def _set_modifier_socket_value(mod: Any, tree: Any, socket_name: str, value: Any) -> None:
    """Sets a Geometry Nodes modifier input property by matching socket name -> identifier."""
    interface = getattr(tree, "interface", None)
    if interface is not None:
        for item in getattr(interface, "items_tree", []):
            if getattr(item, "name", "") == socket_name and getattr(item, "in_out", "") == "INPUT":
                ident = getattr(item, "identifier", None)
                if ident:
                    try:
                        mod[ident] = value
                    except Exception:
                        pass
                    try:
                        item.default_value = value
                    except Exception:
                        pass
                return


def _compute_effective_frequencies(params: TerrainEngineParams) -> Dict[str, float]:
    """
    Translates user-facing `dune_scale` (0.05..500), `dune_density` (0.05..100),
    `dune_morphology`, and `macro_basin_scale` into exact internal metric frequencies.
    """
    scale_norm = max(float(params.dune_scale) / 10.0, 0.005)
    density = max(float(params.dune_density), 0.02)
    macro_norm = max(float(params.macro_basin_scale) / 10.0, 0.01)

    base_freq = density / scale_norm

    morph = params.dune_morphology
    branch_weight = float(params.dune_branching)
    aniso = max(float(params.branch_anisotropy), 0.1)
    plateau_flat = float(params.plateau_flattening)
    terrace_steps = float(params.terrace_steps)

    if morph == DuneMorphology.DENDRITIC_WEB:
        branch_weight = max(branch_weight * 1.35, 0.95)
        aniso = max(aniso * 0.75, 0.2)
    elif morph == DuneMorphology.SINUOUS_WAVES:
        branch_weight = branch_weight * 0.45
        aniso = aniso * 1.35
    elif morph == DuneMorphology.MEGA_CORRIDORS:
        base_freq *= 0.70
        aniso = aniso * 1.25
    elif morph == DuneMorphology.ALPINE_MOUNTAINS:
        branch_weight = max(branch_weight * 1.40, 1.10)
        aniso = max(aniso * 0.65, 1.1)
    elif morph == DuneMorphology.SAVANNA_EXPLANADA:
        plateau_flat = max(plateau_flat, 0.60)
        base_freq *= 0.80
    elif morph == DuneMorphology.FANTASY_TERRACES:
        plateau_flat = max(plateau_flat, 0.40)
        terrace_steps = max(terrace_steps, 5.0)

    p_clamped = max(0.0, min(plateau_flat, 0.95))
    plateau_from_min = p_clamped * 0.38
    plateau_from_max = 1.0 - (p_clamped * 0.38)

    road_scale_norm = max(float(params.road_meander_scale) / 10.0, 0.02)
    road_freq = 0.0032 / road_scale_norm

    half_w = max(float(params.road_width_m) * 0.5, 0.25)
    shoulder_w = max(float(params.road_shoulder_m), 0.5)

    return {
        "warp_freq": 0.0038 * base_freq,
        "turb_freq": 0.0095 * base_freq,
        "voronoi_main_freq": 0.0145 * base_freq,
        "voronoi_sub_freq": 0.0270 * base_freq,
        "wave_freq": 0.0360 * base_freq,
        "medium_freq": 0.0240 * base_freq,
        "macro_freq": 0.0020 / macro_norm,
        "envelope_freq": 0.0028 / macro_norm,
        "branch_weight": branch_weight,
        "aniso_inv_y": 1.0 / max(aniso, 0.05),
        "plateau_from_min": plateau_from_min,
        "plateau_from_max": max(plateau_from_min + 0.05, plateau_from_max),
        "terrace_steps": terrace_steps,
        "terrace_mix": 0.55 if terrace_steps >= 1.0 else 0.0,
        "road_freq": road_freq,
        "road_half_w": half_w,
        "road_outer_w": half_w + shoulder_w,
        "road_active_factor": float(params.road_flatten_strength) if params.enable_road else 0.0,
        "road_mask_enable": 1.0 if params.enable_road else 0.0,
    }


class TerrainGenerator:
    """
    Layer 3: Generates or updates multi-biome terrain deformations and the Universal Road/Path Carve system.
    """

    def __init__(self, bpy_module: Any = None):
        if bpy_module is None:
            import bpy as _bpy
            self.bpy = _bpy
        else:
            self.bpy = bpy_module

    def apply_terrain(
        self,
        terrain_obj: Optional[Any],
        params: TerrainEngineParams,
        scene: Any = None,
        collections: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if scene is None:
            scene = self.bpy.context.scene

        perf_cfg = PERFORMANCE_SETTINGS.get(
            params.performance_profile,
            PERFORMANCE_SETTINGS[PerformanceProfile.BALANCED],
        )

        created_new = False
        if terrain_obj is None or params.conflict_strategy == ConflictStrategy.CREATE_NEW:
            terrain_obj = self._create_new_terrain_mesh(params, perf_cfg, scene, collections)
            created_new = True

        mod_actions = self._manage_existing_modifiers(terrain_obj, params, perf_cfg)
        gn_tree = self._build_or_update_dunes_node_group(params, perf_cfg, scene=scene)

        proc_mod = None
        for m in getattr(terrain_obj, "modifiers", []):
            if m.name == TERRAIN_MODIFIER_NAME:
                proc_mod = m
                break

        if proc_mod is None:
            proc_mod = terrain_obj.modifiers.new(name=TERRAIN_MODIFIER_NAME, type="NODES")

        proc_mod.node_group = gn_tree
        proc_mod.show_viewport = True
        proc_mod.show_render = True

        self.sync_modifier_parameters(proc_mod, gn_tree, params)

        if hasattr(terrain_obj, "update_tag"):
            try:
                terrain_obj.update_tag()
            except Exception:
                pass
        view_layer = getattr(self.bpy.context, "view_layer", None)
        if view_layer and hasattr(view_layer, "update"):
            try:
                view_layer.update()
            except Exception:
                pass

        return {
            "terrain_object": terrain_obj,
            "terrain_name": terrain_obj.name,
            "created_new_terrain": created_new,
            "modifier_name": proc_mod.name,
            "node_group_name": gn_tree.name,
            "modifier_actions": mod_actions,
        }

    def ensure_road_curve_object(
        self,
        terrain_obj: Optional[Any] = None,
        scene: Any = None,
        collections: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Creates or returns the 3D Bezier Curve `PROC_ENV_Road_Curve` spanning across the terrain
        so the user can interactively drag curve points in Edit Mode to guide the road!
        """
        if scene is None:
            scene = self.bpy.context.scene

        objects = getattr(self.bpy.data, "objects", None)
        curves = getattr(self.bpy.data, "curves", None)
        if objects is None or curves is None:
            return None

        existing_obj = objects.get(ROAD_CURVE_OBJECT_NAME)
        if existing_obj is not None:
            return existing_obj

        dims = getattr(terrain_obj, "dimensions", (590.0, 834.0, 38.0)) if terrain_obj else (590.0, 834.0, 38.0)
        dx = float(dims[0])
        dy = float(dims[1])

        curve_data = curves.new(name=ROAD_CURVE_OBJECT_NAME, type="CURVE")
        curve_data.dimensions = "3D"
        spline = curve_data.splines.new(type="BEZIER")
        # Create 5 control points meandering across the terrain
        pts = [
            (-dx * 0.42, -dy * 0.45, 10.0),
            (-dx * 0.15, -dy * 0.18, 12.0),
            (dx * 0.08, dy * 0.02, 14.0),
            (dx * 0.22, dy * 0.24, 12.0),
            (dx * 0.40, dy * 0.45, 10.0),
        ]
        spline.bezier_points.add(len(pts) - 1)
        for i, co in enumerate(pts):
            bp = spline.bezier_points[i]
            bp.co = co
            bp.handle_left_type = "AUTO"
            bp.handle_right_type = "AUTO"

        curve_obj = objects.new(ROAD_CURVE_OBJECT_NAME, curve_data)
        target_col = None
        if collections and "ROADS" in collections:
            target_col = collections["ROADS"]
        elif hasattr(scene, "collection"):
            target_col = scene.collection
        if target_col and hasattr(target_col, "objects"):
            target_col.objects.link(curve_obj)

        return curve_obj

    def _manage_existing_modifiers(
        self,
        terrain_obj: Any,
        params: TerrainEngineParams,
        perf_cfg: Dict[str, Any],
    ) -> Dict[str, str]:
        actions: Dict[str, str] = {}
        mesh = getattr(terrain_obj, "data", None)
        base_verts = len(getattr(mesh, "vertices", [])) if mesh else 0
        strategy = params.conflict_strategy

        for mod in getattr(terrain_obj, "modifiers", []):
            if mod.name == TERRAIN_MODIFIER_NAME:
                continue

            if strategy == ConflictStrategy.KEEP_AND_STACK:
                actions[mod.name] = "KEPT_AS_IS"
                continue

            if strategy == ConflictStrategy.CLEAN_REPLACE:
                mod.show_viewport = False
                mod.show_render = False
                actions[mod.name] = "MUTED_FOR_CLEAN_REPLACE"
                continue

            m_type = str(getattr(mod, "type", ""))
            if m_type == "SUBSURF":
                if base_verts >= perf_cfg["max_safe_base_vertices"] or not perf_cfg["allow_extra_subdiv"]:
                    mod.show_viewport = False
                    mod.show_render = False
                    actions[mod.name] = (
                        f"MUTED_SUBSURF_PROTECTION (base mesh already has {base_verts:,} vertices)"
                    )
                else:
                    mod.levels = min(int(getattr(mod, "levels", 1)), perf_cfg["max_viewport_subdiv"])
                    mod.render_levels = min(int(getattr(mod, "render_levels", 1)), perf_cfg["max_render_subdiv"])
                    actions[mod.name] = f"CAPPED_SUBSURF (view={mod.levels}, render={mod.render_levels})"
            elif m_type == "DISPLACE":
                mod.show_viewport = False
                mod.show_render = False
                actions[mod.name] = "MUTED_LEGACY_DISPLACE"
            elif m_type == "NODES":
                if base_verts >= 100_000 and float(params.existing_relief_keep) <= 0.01:
                    mod.show_viewport = False
                    mod.show_render = False
                    actions[mod.name] = "MUTED_LEGACY_GN (clean foundation on 1.33M base mesh)"
                else:
                    mod.show_viewport = True
                    mod.show_render = True
                    actions[mod.name] = f"KEPT_EXISTING_GN (relief blended at {params.existing_relief_keep:.2f})"
            else:
                actions[mod.name] = "KEPT"

        return actions

    def _build_or_update_dunes_node_group(
        self,
        params: TerrainEngineParams,
        perf_cfg: Dict[str, Any],
        scene: Any = None,
    ) -> Any:
        node_groups = self.bpy.data.node_groups
        tree = node_groups.get(TERRAIN_NODE_GROUP_NAME)
        if tree is None:
            tree = node_groups.new(name=TERRAIN_NODE_GROUP_NAME, type="GeometryNodeTree")

        _ensure_gn_socket(tree, "Geometry", "INPUT", "NodeSocketGeometry")
        _ensure_gn_socket(tree, "Geometry", "OUTPUT", "NodeSocketGeometry")
        _ensure_gn_socket(tree, "Seed", "INPUT", "NodeSocketInt", params.seed, -10000000, 10000000)
        _ensure_gn_socket(tree, "Existing Relief Keep", "INPUT", "NodeSocketFloat", params.existing_relief_keep, 0.0, 2.0)
        _ensure_gn_socket(tree, "Dune Height", "INPUT", "NodeSocketFloat", params.dune_height, -500.0, 1000.0)
        _ensure_gn_socket(tree, "Dune Scale", "INPUT", "NodeSocketFloat", params.dune_scale, 0.01, 500.0)
        _ensure_gn_socket(tree, "Dune Density", "INPUT", "NodeSocketFloat", params.dune_density, 0.01, 100.0)
        _ensure_gn_socket(tree, "Dune Variation", "INPUT", "NodeSocketFloat", params.dune_variation, 0.0, 50.0)
        _ensure_gn_socket(tree, "Wind Turbulence", "INPUT", "NodeSocketFloat", params.wind_turbulence, 0.0, 50.0)
        _ensure_gn_socket(tree, "Dune Branching", "INPUT", "NodeSocketFloat", params.dune_branching, 0.0, 10.0)
        _ensure_gn_socket(tree, "Branch Anisotropy", "INPUT", "NodeSocketFloat", params.branch_anisotropy, 0.05, 30.0)
        _ensure_gn_socket(tree, "Crest Roundness", "INPUT", "NodeSocketFloat", params.crest_roundness, 0.02, 2.0)
        _ensure_gn_socket(tree, "Dune Sharpness", "INPUT", "NodeSocketFloat", params.dune_sharpness, 0.5, 4.0)
        _ensure_gn_socket(tree, "Wind Direction Deg", "INPUT", "NodeSocketFloat", params.wind_direction_deg, -360.0, 360.0)
        _ensure_gn_socket(tree, "Macro Basin Height", "INPUT", "NodeSocketFloat", params.macro_basin_height, -500.0, 500.0)
        _ensure_gn_socket(tree, "Macro Scale", "INPUT", "NodeSocketFloat", params.macro_basin_scale, 0.05, 500.0)
        _ensure_gn_socket(tree, "Medium Undulation Height", "INPUT", "NodeSocketFloat", params.medium_undulation_height, 0.0, 200.0)

        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        freqs = _compute_effective_frequencies(params)
        detail_cap = float(perf_cfg.get("noise_detail_cap", 3.5))

        # ------------------------------------------------------------------
        # 1. GROUP INPUT / OUTPUT & 2D HORIZONTAL PROJECTION (ZERO Z-STEPS)
        # ------------------------------------------------------------------
        n_in = nodes.new("NodeGroupInput")
        n_in.name = "Group Input"
        n_in.location = (-2000, 0)

        n_out = nodes.new("NodeGroupOutput")
        n_out.name = "Group Output"
        n_out.location = (2200, 0)

        n_pos = nodes.new("GeometryNodeInputPosition")
        n_pos.name = "PROC_InputPosition"
        n_pos.location = (-2000, -260)

        n_sep = nodes.new("ShaderNodeSeparateXYZ")
        n_sep.name = "PROC_SeparateXYZ"
        n_sep.location = (-1800, -260)
        links.new(n_pos.outputs["Position"], n_sep.inputs["Vector"])

        n_flat_xy = nodes.new("ShaderNodeCombineXYZ")
        n_flat_xy.name = "PROC_FlatPosition2D"
        n_flat_xy.location = (-1600, -80)
        links.new(n_sep.outputs["X"], n_flat_xy.inputs["X"])
        links.new(n_sep.outputs["Y"], n_flat_xy.inputs["Y"])
        n_flat_xy.inputs["Z"].default_value = 0.0

        n_relief_mul = nodes.new("ShaderNodeMath")
        n_relief_mul.name = "PROC_ReliefKeepMul"
        n_relief_mul.operation = "MULTIPLY"
        n_relief_mul.location = (-900, -520)
        links.new(n_sep.outputs["Z"], n_relief_mul.inputs[0])
        n_relief_mul.inputs[1].default_value = float(params.existing_relief_keep)

        # ------------------------------------------------------------------
        # 2. WIND ALIGNMENT & 2-STAGE HORIZONTAL FLOW WARPING
        # ------------------------------------------------------------------
        wind_rad = math.radians(float(params.wind_direction_deg))
        n_rot = nodes.new("ShaderNodeVectorRotate")
        n_rot.name = "PROC_WindRotate"
        n_rot.rotation_type = "Z_AXIS"
        n_rot.location = (-1380, 80)
        links.new(n_flat_xy.outputs["Vector"], n_rot.inputs["Vector"])
        n_rot.inputs["Angle"].default_value = wind_rad

        n_seed_add = nodes.new("ShaderNodeVectorMath")
        n_seed_add.name = "PROC_SeedOffset"
        n_seed_add.operation = "ADD"
        n_seed_add.location = (-1180, 80)
        links.new(n_rot.outputs["Vector"], n_seed_add.inputs[0])
        seed_f = float(params.seed % 10000) * 0.137
        n_seed_add.inputs[1].default_value = (seed_f * 13.7, seed_f * 29.3, 0.0)

        n_warp_noise = nodes.new("ShaderNodeTexNoise")
        n_warp_noise.name = "PROC_DomainWarpNoise"
        n_warp_noise.location = (-980, 320)
        n_warp_noise.inputs["Scale"].default_value = freqs["warp_freq"]
        n_warp_noise.inputs["Detail"].default_value = min(2.2, detail_cap)
        n_warp_noise.inputs["Roughness"].default_value = 0.45
        links.new(n_seed_add.outputs["Vector"], n_warp_noise.inputs["Vector"])

        n_warp_vec = nodes.new("ShaderNodeVectorMath")
        n_warp_vec.name = "PROC_DomainWarpScale"
        n_warp_vec.operation = "MULTIPLY"
        n_warp_vec.location = (-780, 320)
        links.new(n_warp_noise.outputs["Color"], n_warp_vec.inputs[0])
        w_amp = float(params.dune_variation) * 38.0
        n_warp_vec.inputs[1].default_value = (w_amp, w_amp, 0.0)

        n_turb_noise = nodes.new("ShaderNodeTexNoise")
        n_turb_noise.name = "PROC_WindTurbulenceNoise"
        n_turb_noise.location = (-980, 60)
        n_turb_noise.inputs["Scale"].default_value = freqs["turb_freq"]
        n_turb_noise.inputs["Detail"].default_value = min(3.0, detail_cap)
        n_turb_noise.inputs["Roughness"].default_value = 0.50
        links.new(n_seed_add.outputs["Vector"], n_turb_noise.inputs["Vector"])

        n_turb_vec = nodes.new("ShaderNodeVectorMath")
        n_turb_vec.name = "PROC_WindTurbulenceScale"
        n_turb_vec.operation = "MULTIPLY"
        n_turb_vec.location = (-780, 60)
        links.new(n_turb_noise.outputs["Color"], n_turb_vec.inputs[0])
        t_amp = float(params.wind_turbulence) * 18.0
        n_turb_vec.inputs[1].default_value = (t_amp, t_amp, 0.0)

        n_warp_sum = nodes.new("ShaderNodeVectorMath")
        n_warp_sum.name = "PROC_TotalWindWarp"
        n_warp_sum.operation = "ADD"
        n_warp_sum.location = (-580, 200)
        links.new(n_warp_vec.outputs["Vector"], n_warp_sum.inputs[0])
        links.new(n_turb_vec.outputs["Vector"], n_warp_sum.inputs[1])

        n_warped_pos = nodes.new("ShaderNodeVectorMath")
        n_warped_pos.name = "PROC_WarpedPosition"
        n_warped_pos.operation = "ADD"
        n_warped_pos.location = (-380, 120)
        links.new(n_seed_add.outputs["Vector"], n_warped_pos.inputs[0])
        links.new(n_warp_sum.outputs["Vector"], n_warped_pos.inputs[1])

        # ------------------------------------------------------------------
        # 3. TREE / RIVER / WEB BRANCHING DUNE & RIDGE NETWORK (2-OCTAVE VORONOI)
        # ------------------------------------------------------------------
        n_aniso = nodes.new("ShaderNodeVectorMath")
        n_aniso.name = "PROC_AnisotropicStretch"
        n_aniso.operation = "MULTIPLY"
        n_aniso.location = (-180, 260)
        links.new(n_warped_pos.outputs["Vector"], n_aniso.inputs[0])
        n_aniso.inputs[1].default_value = (1.0, freqs["aniso_inv_y"], 0.0)

        n_vor_main = nodes.new("ShaderNodeTexVoronoi")
        n_vor_main.name = "PROC_BranchingVoronoiMain"
        n_vor_main.location = (40, 320)
        try:
            n_vor_main.feature = "SMOOTH_F1"
            n_vor_main.distance = "EUCLIDEAN"
        except Exception:
            pass
        n_vor_main.inputs["Scale"].default_value = freqs["voronoi_main_freq"]
        if "Smoothness" in n_vor_main.inputs:
            n_vor_main.inputs["Smoothness"].default_value = max(0.02, min(float(params.crest_roundness), 1.0))
        if "Randomness" in n_vor_main.inputs:
            n_vor_main.inputs["Randomness"].default_value = 0.85
        links.new(n_aniso.outputs["Vector"], n_vor_main.inputs["Vector"])

        n_sub_rot = nodes.new("ShaderNodeVectorRotate")
        n_sub_rot.name = "PROC_TributaryRotate"
        n_sub_rot.rotation_type = "Z_AXIS"
        n_sub_rot.location = (-180, 60)
        n_sub_rot.inputs["Angle"].default_value = 0.42
        links.new(n_aniso.outputs["Vector"], n_sub_rot.inputs["Vector"])

        n_vor_sub = nodes.new("ShaderNodeTexVoronoi")
        n_vor_sub.name = "PROC_BranchingVoronoiSub"
        n_vor_sub.location = (40, 80)
        try:
            n_vor_sub.feature = "SMOOTH_F1"
            n_vor_sub.distance = "EUCLIDEAN"
        except Exception:
            pass
        n_vor_sub.inputs["Scale"].default_value = freqs["voronoi_sub_freq"]
        if "Smoothness" in n_vor_sub.inputs:
            n_vor_sub.inputs["Smoothness"].default_value = max(0.05, min(float(params.crest_roundness) * 1.15, 1.0))
        if "Randomness" in n_vor_sub.inputs:
            n_vor_sub.inputs["Randomness"].default_value = 0.90
        links.new(n_sub_rot.outputs["Vector"], n_vor_sub.inputs["Vector"])

        n_sub_weight = nodes.new("ShaderNodeMath")
        n_sub_weight.name = "PROC_TributaryWeight"
        n_sub_weight.operation = "MULTIPLY"
        n_sub_weight.location = (240, 120)
        links.new(n_vor_sub.outputs["Distance"], n_sub_weight.inputs[0])
        n_sub_weight.inputs[1].default_value = 0.42

        n_web_sum = nodes.new("ShaderNodeMath")
        n_web_sum.name = "PROC_BranchingWebSum"
        n_web_sum.operation = "ADD"
        n_web_sum.location = (400, 240)
        links.new(n_vor_main.outputs["Distance"], n_web_sum.inputs[0])
        links.new(n_sub_weight.outputs["Value"], n_web_sum.inputs[1])

        n_web_weighted = nodes.new("ShaderNodeMath")
        n_web_weighted.name = "PROC_BranchingWebScaled"
        n_web_weighted.operation = "MULTIPLY"
        n_web_weighted.location = (560, 240)
        links.new(n_web_sum.outputs["Value"], n_web_weighted.inputs[0])
        n_web_weighted.inputs[1].default_value = freqs["branch_weight"]

        # ------------------------------------------------------------------
        # 4. SMOOTH CONTINUOUS WIND WAVE ('SIN') + PLATEAU / TERRACE SHAPING
        # ------------------------------------------------------------------
        n_dune_wave = nodes.new("ShaderNodeTexWave")
        n_dune_wave.name = "PROC_PrimaryDuneWave"
        n_dune_wave.wave_type = "BANDS"
        n_dune_wave.bands_direction = "X"
        n_dune_wave.wave_profile = "SIN"
        n_dune_wave.location = (40, -160)
        n_dune_wave.inputs["Scale"].default_value = freqs["wave_freq"]
        n_dune_wave.inputs["Distortion"].default_value = float(params.dune_variation) * 1.35
        n_dune_wave.inputs["Detail"].default_value = min(1.5, detail_cap)
        n_dune_wave.inputs["Detail Scale"].default_value = 1.2
        n_dune_wave.inputs["Detail Roughness"].default_value = 0.45
        links.new(n_warped_pos.outputs["Vector"], n_dune_wave.inputs["Vector"])

        n_wave_weighted = nodes.new("ShaderNodeMath")
        n_wave_weighted.name = "PROC_SmoothWaveScaled"
        n_wave_weighted.operation = "MULTIPLY"
        n_wave_weighted.location = (400, -120)
        links.new(n_dune_wave.outputs["Fac"], n_wave_weighted.inputs[0])
        n_wave_weighted.inputs[1].default_value = max(0.15, 1.0 - min(freqs["branch_weight"] * 0.45, 0.75))

        n_dune_combined = nodes.new("ShaderNodeMath")
        n_dune_combined.name = "PROC_CombinedDuneProfile"
        n_dune_combined.operation = "ADD"
        n_dune_combined.location = (680, 80)
        links.new(n_web_weighted.outputs["Value"], n_dune_combined.inputs[0])
        links.new(n_wave_weighted.outputs["Value"], n_dune_combined.inputs[1])

        # Savanna Explanada / Plateau Clamping (`ShaderNodeMapRange`)
        n_plateau = nodes.new("ShaderNodeMapRange")
        n_plateau.name = "PROC_PlateauMapRange"
        n_plateau.location = (820, 80)
        try:
            n_plateau.interpolation_type = "SMOOTHSTEP"
        except Exception:
            pass
        n_plateau.inputs["From Min"].default_value = freqs["plateau_from_min"]
        n_plateau.inputs["From Max"].default_value = freqs["plateau_from_max"]
        n_plateau.inputs["To Min"].default_value = 0.0
        n_plateau.inputs["To Max"].default_value = 1.0
        links.new(n_dune_combined.outputs["Value"], n_plateau.inputs["Value"])

        n_crest_pow = nodes.new("ShaderNodeMath")
        n_crest_pow.name = "PROC_DuneCrestSharpness"
        n_crest_pow.operation = "POWER"
        n_crest_pow.location = (980, 80)
        links.new(n_plateau.outputs["Result"], n_crest_pow.inputs[0])
        n_crest_pow.inputs[1].default_value = max(0.5, min(float(params.dune_sharpness), 2.8))

        n_env_noise = nodes.new("ShaderNodeTexNoise")
        n_env_noise.name = "PROC_DuneFieldEnvelope"
        n_env_noise.location = (400, -340)
        n_env_noise.inputs["Scale"].default_value = freqs["envelope_freq"]
        n_env_noise.inputs["Detail"].default_value = 2.0
        n_env_noise.inputs["Roughness"].default_value = 0.45
        links.new(n_seed_add.outputs["Vector"], n_env_noise.inputs["Vector"])

        n_env_mul = nodes.new("ShaderNodeMath")
        n_env_mul.name = "PROC_DuneEnvelopeMul"
        n_env_mul.operation = "MULTIPLY"
        n_env_mul.location = (980, -120)
        links.new(n_crest_pow.outputs["Value"], n_env_mul.inputs[0])
        links.new(n_env_noise.outputs["Fac"], n_env_mul.inputs[1])

        n_dune_height_mul = nodes.new("ShaderNodeMath")
        n_dune_height_mul.name = "PROC_DuneHeightMul"
        n_dune_height_mul.operation = "MULTIPLY"
        n_dune_height_mul.location = (1120, -40)
        links.new(n_env_mul.outputs["Value"], n_dune_height_mul.inputs[0])
        n_dune_height_mul.inputs[1].default_value = float(params.dune_height)

        # ------------------------------------------------------------------
        # 5. MACRO BASINS & SMOOTH MEDIUM UNDULATIONS
        # ------------------------------------------------------------------
        n_macro_noise = nodes.new("ShaderNodeTexNoise")
        n_macro_noise.name = "PROC_MacroBasinNoise"
        n_macro_noise.location = (40, 560)
        n_macro_noise.inputs["Scale"].default_value = freqs["macro_freq"]
        n_macro_noise.inputs["Detail"].default_value = min(2.5, detail_cap)
        n_macro_noise.inputs["Roughness"].default_value = 0.42
        links.new(n_seed_add.outputs["Vector"], n_macro_noise.inputs["Vector"])

        n_macro_mul = nodes.new("ShaderNodeMath")
        n_macro_mul.name = "PROC_MacroBasinHeightMul"
        n_macro_mul.operation = "MULTIPLY"
        n_macro_mul.location = (400, 560)
        links.new(n_macro_noise.outputs["Fac"], n_macro_mul.inputs[0])
        n_macro_mul.inputs[1].default_value = float(params.macro_basin_height)

        n_med_noise = nodes.new("ShaderNodeTexNoise")
        n_med_noise.name = "PROC_MediumUndulationNoise"
        n_med_noise.location = (40, -420)
        n_med_noise.inputs["Scale"].default_value = freqs["medium_freq"]
        n_med_noise.inputs["Detail"].default_value = min(2.5, detail_cap)
        n_med_noise.inputs["Roughness"].default_value = 0.45
        links.new(n_warped_pos.outputs["Vector"], n_med_noise.inputs["Vector"])

        n_med_mul = nodes.new("ShaderNodeMath")
        n_med_mul.name = "PROC_MediumHeightMul"
        n_med_mul.operation = "MULTIPLY"
        n_med_mul.location = (400, -520)
        links.new(n_med_noise.outputs["Fac"], n_med_mul.inputs[0])
        n_med_mul.inputs[1].default_value = float(params.medium_undulation_height)

        n_sum1 = nodes.new("ShaderNodeMath")
        n_sum1.name = "PROC_SumMacroAndDunes"
        n_sum1.operation = "ADD"
        n_sum1.location = (1260, 160)
        links.new(n_macro_mul.outputs["Value"], n_sum1.inputs[0])
        links.new(n_dune_height_mul.outputs["Value"], n_sum1.inputs[1])

        n_sum2 = nodes.new("ShaderNodeMath")
        n_sum2.name = "PROC_SumWithMedium"
        n_sum2.operation = "ADD"
        n_sum2.location = (1260, -40)
        links.new(n_sum1.outputs["Value"], n_sum2.inputs[0])
        links.new(n_med_mul.outputs["Value"], n_sum2.inputs[1])

        n_sum_terrain_z = nodes.new("ShaderNodeMath")
        n_sum_terrain_z.name = "PROC_TotalTerrainZ"
        n_sum_terrain_z.operation = "ADD"
        n_sum_terrain_z.location = (1260, -240)
        links.new(n_relief_mul.outputs["Value"], n_sum_terrain_z.inputs[0])
        links.new(n_sum2.outputs["Value"], n_sum_terrain_z.inputs[1])

        # ------------------------------------------------------------------
        # 6. UNIVERSAL ROAD & PATH CARVE SYSTEM (CP-03)
        #    Contours, flattens, and carves a smooth road + secondary branch
        #    across ANY terrain (Desert, Mountain, Savanna, Fantasy)
        # ------------------------------------------------------------------
        # Rotate flat coordinates by Road Direction
        n_road_rot = nodes.new("ShaderNodeVectorRotate")
        n_road_rot.name = "PROC_RoadRotate"
        n_road_rot.rotation_type = "Z_AXIS"
        n_road_rot.location = (-1380, -760)
        n_road_rot.inputs["Angle"].default_value = math.radians(float(params.road_direction_deg))
        links.new(n_flat_xy.outputs["Vector"], n_road_rot.inputs["Vector"])

        n_road_sep = nodes.new("ShaderNodeSeparateXYZ")
        n_road_sep.name = "PROC_RoadSeparateXY"
        n_road_sep.location = (-1180, -760)
        links.new(n_road_rot.outputs["Vector"], n_road_sep.inputs["Vector"])

        # Meandering Road Centerline Noise along Road X
        n_road_noise = nodes.new("ShaderNodeTexNoise")
        n_road_noise.name = "PROC_RoadMeanderNoise"
        n_road_noise.location = (-980, -920)
        n_road_noise.inputs["Scale"].default_value = freqs["road_freq"]
        n_road_noise.inputs["Detail"].default_value = 2.0
        n_road_noise.inputs["Roughness"].default_value = 0.40
        links.new(n_road_rot.outputs["Vector"], n_road_noise.inputs["Vector"])

        n_road_center_sub = nodes.new("ShaderNodeMath")
        n_road_center_sub.name = "PROC_RoadCenterZero"
        n_road_center_sub.operation = "SUBTRACT"
        n_road_center_sub.location = (-780, -920)
        links.new(n_road_noise.outputs["Fac"], n_road_center_sub.inputs[0])
        n_road_center_sub.inputs[1].default_value = 0.5

        n_road_amp = nodes.new("ShaderNodeMath")
        n_road_amp.name = "PROC_RoadMeanderAmp"
        n_road_amp.operation = "MULTIPLY"
        n_road_amp.location = (-600, -920)
        links.new(n_road_center_sub.outputs["Value"], n_road_amp.inputs[0])
        n_road_amp.inputs[1].default_value = float(params.road_meander_amplitude) * 2.0

        n_road_offset = nodes.new("ShaderNodeMath")
        n_road_offset.name = "PROC_RoadLateralOffset"
        n_road_offset.operation = "ADD"
        n_road_offset.location = (-420, -920)
        links.new(n_road_amp.outputs["Value"], n_road_offset.inputs[0])
        n_road_offset.inputs[1].default_value = float(params.road_offset_m)

        # Distance to Main Winding Road: d_main = abs(Road_Y - Center_Y)
        n_road_diff = nodes.new("ShaderNodeMath")
        n_road_diff.name = "PROC_RoadDiffY"
        n_road_diff.operation = "SUBTRACT"
        n_road_diff.location = (-240, -780)
        links.new(n_road_sep.outputs["Y"], n_road_diff.inputs[0])
        links.new(n_road_offset.outputs["Value"], n_road_diff.inputs[1])

        n_road_dist_main = nodes.new("ShaderNodeMath")
        n_road_dist_main.name = "PROC_RoadDistMain"
        n_road_dist_main.operation = "ABSOLUTE"
        n_road_dist_main.location = (-60, -780)
        links.new(n_road_diff.outputs["Value"], n_road_dist_main.inputs[0])

        # Secondary Fork / Branch Road ("Bifurcação de Caminho")
        n_branch_slope = nodes.new("ShaderNodeMath")
        n_branch_slope.name = "PROC_RoadBranchSlopeX"
        n_branch_slope.operation = "MULTIPLY"
        n_branch_slope.location = (-420, -1120)
        links.new(n_road_sep.outputs["X"], n_branch_slope.inputs[0])
        n_branch_slope.inputs[1].default_value = 0.62 if params.road_secondary_branch else 9999.0

        n_branch_target_y = nodes.new("ShaderNodeMath")
        n_branch_target_y.name = "PROC_RoadBranchTargetY"
        n_branch_target_y.operation = "ADD"
        n_branch_target_y.location = (-240, -1120)
        links.new(n_road_offset.outputs["Value"], n_branch_target_y.inputs[0])
        links.new(n_branch_slope.outputs["Value"], n_branch_target_y.inputs[1])

        n_branch_diff = nodes.new("ShaderNodeMath")
        n_branch_diff.name = "PROC_RoadBranchDiff"
        n_branch_diff.operation = "SUBTRACT"
        n_branch_diff.location = (-60, -1120)
        links.new(n_road_sep.outputs["Y"], n_branch_diff.inputs[0])
        links.new(n_branch_target_y.outputs["Value"], n_branch_diff.inputs[1])

        n_branch_abs = nodes.new("ShaderNodeMath")
        n_branch_abs.name = "PROC_RoadBranchAbs"
        n_branch_abs.operation = "ABSOLUTE"
        n_branch_abs.location = (120, -1120)
        links.new(n_branch_diff.outputs["Value"], n_branch_abs.inputs[0])

        # Only activate branch for X > 0 so it forks in a clean Y-junction from the center!
        n_neg_x = nodes.new("ShaderNodeMath")
        n_neg_x.name = "PROC_RoadBranchHalfPlane"
        n_neg_x.operation = "MULTIPLY"
        n_neg_x.location = (-60, -1280)
        links.new(n_road_sep.outputs["X"], n_neg_x.inputs[0])
        n_neg_x.inputs[1].default_value = -1.0

        n_branch_half_dist = nodes.new("ShaderNodeMath")
        n_branch_half_dist.name = "PROC_RoadBranchClipped"
        n_branch_half_dist.operation = "MAXIMUM"
        n_branch_half_dist.location = (280, -1180)
        links.new(n_branch_abs.outputs["Value"], n_branch_half_dist.inputs[0])
        links.new(n_neg_x.outputs["Value"], n_branch_half_dist.inputs[1])

        # Combine Main Road + Secondary Branch with MINIMUM
        n_road_dist_comb = nodes.new("ShaderNodeMath")
        n_road_dist_comb.name = "PROC_RoadCombinedDist"
        n_road_dist_comb.operation = "MINIMUM"
        n_road_dist_comb.location = (460, -860)
        links.new(n_road_dist_main.outputs["Value"], n_road_dist_comb.inputs[0])
        links.new(n_branch_half_dist.outputs["Value"], n_road_dist_comb.inputs[1])

        # Road Mask (1.0 on road bed, smooth transition across road_shoulder_m to 0.0)
        n_road_mask = nodes.new("ShaderNodeMapRange")
        n_road_mask.name = "PROC_RoadMaskRange"
        n_road_mask.location = (660, -860)
        try:
            n_road_mask.interpolation_type = "SMOOTHSTEP"
        except Exception:
            pass
        n_road_mask.inputs["From Min"].default_value = freqs["road_half_w"]
        n_road_mask.inputs["From Max"].default_value = freqs["road_outer_w"]
        n_road_mask.inputs["To Min"].default_value = 1.0
        n_road_mask.inputs["To Max"].default_value = 0.0
        links.new(n_road_dist_comb.outputs["Value"], n_road_mask.inputs["Value"])

        # Side Berm / Shoulder Bank: 4 * m * (1 - m) * road_berm_height_m
        n_one_minus_m = nodes.new("ShaderNodeMath")
        n_one_minus_m.name = "PROC_RoadOneMinusMask"
        n_one_minus_m.operation = "SUBTRACT"
        n_one_minus_m.location = (860, -1040)
        n_one_minus_m.inputs[0].default_value = 1.0
        links.new(n_road_mask.outputs["Result"], n_one_minus_m.inputs[1])

        n_berm_bell = nodes.new("ShaderNodeMath")
        n_berm_bell.name = "PROC_RoadBermBell"
        n_berm_bell.operation = "MULTIPLY"
        n_berm_bell.location = (1040, -1040)
        links.new(n_road_mask.outputs["Result"], n_berm_bell.inputs[0])
        links.new(n_one_minus_m.outputs["Value"], n_berm_bell.inputs[1])

        n_berm_height = nodes.new("ShaderNodeMath")
        n_berm_height.name = "PROC_RoadBermHeightMul"
        n_berm_height.operation = "MULTIPLY"
        n_berm_height.location = (1200, -1040)
        links.new(n_berm_bell.outputs["Value"], n_berm_height.inputs[0])
        n_berm_height.inputs[1].default_value = (
            float(params.road_berm_height_m) * 4.0 if params.enable_road else 0.0
        )

        # Target Road Elevation: Smoothly follows Macro Basin contour + Carve Depth
        n_road_macro_follow = nodes.new("ShaderNodeMath")
        n_road_macro_follow.name = "PROC_RoadMacroFollow"
        n_road_macro_follow.operation = "MULTIPLY"
        n_road_macro_follow.location = (860, -680)
        links.new(n_macro_mul.outputs["Value"], n_road_macro_follow.inputs[0])
        n_road_macro_follow.inputs[1].default_value = float(params.road_elevation_follow)

        n_road_base_z = nodes.new("ShaderNodeMath")
        n_road_base_z.name = "PROC_RoadBaseZ"
        n_road_base_z.operation = "ADD"
        n_road_base_z.location = (1040, -680)
        links.new(n_relief_mul.outputs["Value"], n_road_base_z.inputs[0])
        links.new(n_road_macro_follow.outputs["Value"], n_road_base_z.inputs[1])

        n_road_target_z = nodes.new("ShaderNodeMath")
        n_road_target_z.name = "PROC_RoadTargetZ"
        n_road_target_z.operation = "ADD"
        n_road_target_z.location = (1200, -680)
        links.new(n_road_base_z.outputs["Value"], n_road_target_z.inputs[0])
        n_road_target_z.inputs[1].default_value = float(params.road_carve_depth_m)

        # Effective Flatten Factor = road_mask * road_active_factor
        n_road_eff_fac = nodes.new("ShaderNodeMath")
        n_road_eff_fac.name = "PROC_RoadEffectiveFactor"
        n_road_eff_fac.operation = "MULTIPLY"
        n_road_eff_fac.location = (1200, -860)
        links.new(n_road_mask.outputs["Result"], n_road_eff_fac.inputs[0])
        n_road_eff_fac.inputs[1].default_value = freqs["road_active_factor"]

        # Linearly interpolate: Z_blended = Z_terrain + eff_fac * (Z_road_target - Z_terrain) + Berm
        n_road_z_delta = nodes.new("ShaderNodeMath")
        n_road_z_delta.name = "PROC_RoadZDelta"
        n_road_z_delta.operation = "SUBTRACT"
        n_road_z_delta.location = (1400, -560)
        links.new(n_road_target_z.outputs["Value"], n_road_z_delta.inputs[0])
        links.new(n_sum_terrain_z.outputs["Value"], n_road_z_delta.inputs[1])

        n_road_z_apply = nodes.new("ShaderNodeMath")
        n_road_z_apply.name = "PROC_RoadZApply"
        n_road_z_apply.operation = "MULTIPLY"
        n_road_z_apply.location = (1560, -660)
        links.new(n_road_z_delta.outputs["Value"], n_road_z_apply.inputs[0])
        links.new(n_road_eff_fac.outputs["Value"], n_road_z_apply.inputs[1])

        n_z_with_road = nodes.new("ShaderNodeMath")
        n_z_with_road.name = "PROC_ZWithRoad"
        n_z_with_road.operation = "ADD"
        n_z_with_road.location = (1720, -420)
        links.new(n_sum_terrain_z.outputs["Value"], n_z_with_road.inputs[0])
        links.new(n_road_z_apply.outputs["Value"], n_z_with_road.inputs[1])

        n_sum_total = nodes.new("ShaderNodeMath")
        n_sum_total.name = "PROC_TotalZ"
        n_sum_total.operation = "ADD"
        n_sum_total.location = (1860, -340)
        links.new(n_z_with_road.outputs["Value"], n_sum_total.inputs[0])
        links.new(n_berm_height.outputs["Value"], n_sum_total.inputs[1])

        # ------------------------------------------------------------------
        # 7. TOPOLOGICAL BLUR ATTRIBUTE + SET POSITION + STORE ROAD ATTRIBUTE
        # ------------------------------------------------------------------
        final_z_socket = n_sum_total.outputs["Value"]
        try:
            n_blur = nodes.new("GeometryNodeBlurAttribute")
            n_blur.name = "PROC_TopologicalSmoothZ"
            n_blur.data_type = "FLOAT"
            n_blur.location = (1540, -180)
            val_in = next((s for s in n_blur.inputs if s.name == "Value" and s.type == "VALUE"), n_blur.inputs[0])
            links.new(n_sum_total.outputs["Value"], val_in)
            if "Iterations" in n_blur.inputs:
                n_blur.inputs["Iterations"].default_value = int(params.mesh_smooth_iterations)
            if "Weight" in n_blur.inputs:
                n_blur.inputs["Weight"].default_value = float(params.mesh_smooth_factor)
            val_out = next((s for s in n_blur.outputs if s.name == "Value" and s.type == "VALUE"), n_blur.outputs[0])
            final_z_socket = val_out
        except Exception:
            pass

        n_comb = nodes.new("ShaderNodeCombineXYZ")
        n_comb.name = "PROC_CombineFinalPos"
        n_comb.location = (1720, -120)
        links.new(n_sep.outputs["X"], n_comb.inputs["X"])
        links.new(n_sep.outputs["Y"], n_comb.inputs["Y"])
        links.new(final_z_socket, n_comb.inputs["Z"])

        n_set_pos = nodes.new("GeometryNodeSetPosition")
        n_set_pos.name = "PROC_SetPosition"
        n_set_pos.location = (1880, 80)
        links.new(n_in.outputs["Geometry"], n_set_pos.inputs["Geometry"])
        links.new(n_comb.outputs["Vector"], n_set_pos.inputs["Position"])

        # Store `proc_road_mask` attribute on the mesh so the Surface Shader (Layer 4) shades the road!
        geo_after_pos = n_set_pos.outputs["Geometry"]
        try:
            n_mask_shader_mul = nodes.new("ShaderNodeMath")
            n_mask_shader_mul.name = "PROC_RoadShaderMaskEnable"
            n_mask_shader_mul.operation = "MULTIPLY"
            n_mask_shader_mul.location = (1720, -860)
            links.new(n_road_mask.outputs["Result"], n_mask_shader_mul.inputs[0])
            n_mask_shader_mul.inputs[1].default_value = freqs["road_mask_enable"]

            n_store_attr = nodes.new("GeometryNodeStoreNamedAttribute")
            n_store_attr.name = "PROC_StoreRoadMask"
            n_store_attr.data_type = "FLOAT"
            n_store_attr.domain = "POINT"
            n_store_attr.location = (2020, 80)
            links.new(geo_after_pos, n_store_attr.inputs["Geometry"])
            if "Name" in n_store_attr.inputs:
                n_store_attr.inputs["Name"].default_value = ROAD_MASK_ATTRIBUTE_NAME
            val_sock = next(
                (s for s in n_store_attr.inputs if s.name == "Value" and s.type == "VALUE"),
                n_store_attr.inputs[-1],
            )
            links.new(n_mask_shader_mul.outputs["Value"], val_sock)
            geo_after_pos = n_store_attr.outputs["Geometry"]
        except Exception:
            pass

        final_geo_socket = geo_after_pos
        try:
            n_smooth = nodes.new("GeometryNodeSetShadeSmooth")
            n_smooth.name = "PROC_SetShadeSmooth"
            n_smooth.location = (2180, 80)
            links.new(geo_after_pos, n_smooth.inputs["Geometry"])
            if "Shade Smooth" in n_smooth.inputs:
                n_smooth.inputs["Shade Smooth"].default_value = bool(params.shade_smooth)
            final_geo_socket = n_smooth.outputs["Geometry"]
        except Exception:
            pass

        links.new(final_geo_socket, n_out.inputs["Geometry"])

        return tree

    def sync_modifier_parameters(
        self,
        proc_mod: Any,
        gn_tree: Any,
        params: TerrainEngineParams,
    ) -> None:
        """
        Synchronizes TerrainEngineParams (including Multi-Biome & Road Carve parameters)
        with both modifier sockets and internal node default values for real-time viewport updates.
        """
        _set_modifier_socket_value(proc_mod, gn_tree, "Seed", int(params.seed))
        _set_modifier_socket_value(proc_mod, gn_tree, "Existing Relief Keep", float(params.existing_relief_keep))
        _set_modifier_socket_value(proc_mod, gn_tree, "Dune Height", float(params.dune_height))
        _set_modifier_socket_value(proc_mod, gn_tree, "Dune Scale", float(params.dune_scale))
        _set_modifier_socket_value(proc_mod, gn_tree, "Dune Density", float(params.dune_density))
        _set_modifier_socket_value(proc_mod, gn_tree, "Dune Variation", float(params.dune_variation))
        _set_modifier_socket_value(proc_mod, gn_tree, "Wind Turbulence", float(params.wind_turbulence))
        _set_modifier_socket_value(proc_mod, gn_tree, "Dune Branching", float(params.dune_branching))
        _set_modifier_socket_value(proc_mod, gn_tree, "Branch Anisotropy", float(params.branch_anisotropy))
        _set_modifier_socket_value(proc_mod, gn_tree, "Crest Roundness", float(params.crest_roundness))
        _set_modifier_socket_value(proc_mod, gn_tree, "Dune Sharpness", float(params.dune_sharpness))
        _set_modifier_socket_value(proc_mod, gn_tree, "Wind Direction Deg", float(params.wind_direction_deg))
        _set_modifier_socket_value(proc_mod, gn_tree, "Macro Basin Height", float(params.macro_basin_height))
        _set_modifier_socket_value(proc_mod, gn_tree, "Macro Scale", float(params.macro_basin_scale))
        _set_modifier_socket_value(proc_mod, gn_tree, "Medium Undulation Height", float(params.medium_undulation_height))

        nodes = getattr(gn_tree, "nodes", None)
        if not nodes:
            return

        freqs = _compute_effective_frequencies(params)
        seed_f = float(params.seed % 10000) * 0.137

        if "PROC_ReliefKeepMul" in nodes:
            nodes["PROC_ReliefKeepMul"].inputs[1].default_value = float(params.existing_relief_keep)
        if "PROC_WindRotate" in nodes:
            nodes["PROC_WindRotate"].inputs["Angle"].default_value = math.radians(float(params.wind_direction_deg))
        if "PROC_SeedOffset" in nodes:
            nodes["PROC_SeedOffset"].inputs[1].default_value = (seed_f * 13.7, seed_f * 29.3, 0.0)
        if "PROC_DomainWarpNoise" in nodes:
            nodes["PROC_DomainWarpNoise"].inputs["Scale"].default_value = freqs["warp_freq"]
        if "PROC_DomainWarpScale" in nodes:
            w_amp = float(params.dune_variation) * 38.0
            nodes["PROC_DomainWarpScale"].inputs[1].default_value = (w_amp, w_amp, 0.0)
        if "PROC_WindTurbulenceNoise" in nodes:
            nodes["PROC_WindTurbulenceNoise"].inputs["Scale"].default_value = freqs["turb_freq"]
        if "PROC_WindTurbulenceScale" in nodes:
            t_amp = float(params.wind_turbulence) * 18.0
            nodes["PROC_WindTurbulenceScale"].inputs[1].default_value = (t_amp, t_amp, 0.0)
        if "PROC_AnisotropicStretch" in nodes:
            nodes["PROC_AnisotropicStretch"].inputs[1].default_value = (1.0, freqs["aniso_inv_y"], 0.0)
        if "PROC_BranchingVoronoiMain" in nodes:
            v_main = nodes["PROC_BranchingVoronoiMain"]
            v_main.inputs["Scale"].default_value = freqs["voronoi_main_freq"]
            if "Smoothness" in v_main.inputs:
                v_main.inputs["Smoothness"].default_value = max(0.02, min(float(params.crest_roundness), 1.0))
        if "PROC_BranchingVoronoiSub" in nodes:
            v_sub = nodes["PROC_BranchingVoronoiSub"]
            v_sub.inputs["Scale"].default_value = freqs["voronoi_sub_freq"]
            if "Smoothness" in v_sub.inputs:
                v_sub.inputs["Smoothness"].default_value = max(0.05, min(float(params.crest_roundness) * 1.15, 1.0))
        if "PROC_BranchingWebScaled" in nodes:
            nodes["PROC_BranchingWebScaled"].inputs[1].default_value = freqs["branch_weight"]
        if "PROC_PrimaryDuneWave" in nodes:
            nodes["PROC_PrimaryDuneWave"].inputs["Scale"].default_value = freqs["wave_freq"]
            nodes["PROC_PrimaryDuneWave"].inputs["Distortion"].default_value = float(params.dune_variation) * 1.35
        if "PROC_SmoothWaveScaled" in nodes:
            nodes["PROC_SmoothWaveScaled"].inputs[1].default_value = max(
                0.15, 1.0 - min(freqs["branch_weight"] * 0.45, 0.75)
            )
        if "PROC_PlateauMapRange" in nodes:
            nodes["PROC_PlateauMapRange"].inputs["From Min"].default_value = freqs["plateau_from_min"]
            nodes["PROC_PlateauMapRange"].inputs["From Max"].default_value = freqs["plateau_from_max"]
        if "PROC_DuneCrestSharpness" in nodes:
            nodes["PROC_DuneCrestSharpness"].inputs[1].default_value = max(0.5, min(float(params.dune_sharpness), 2.8))
        if "PROC_DuneFieldEnvelope" in nodes:
            nodes["PROC_DuneFieldEnvelope"].inputs["Scale"].default_value = freqs["envelope_freq"]
        if "PROC_DuneHeightMul" in nodes:
            nodes["PROC_DuneHeightMul"].inputs[1].default_value = float(params.dune_height)
        if "PROC_MacroBasinNoise" in nodes:
            nodes["PROC_MacroBasinNoise"].inputs["Scale"].default_value = freqs["macro_freq"]
        if "PROC_MacroBasinHeightMul" in nodes:
            nodes["PROC_MacroBasinHeightMul"].inputs[1].default_value = float(params.macro_basin_height)
        if "PROC_MediumUndulationNoise" in nodes:
            nodes["PROC_MediumUndulationNoise"].inputs["Scale"].default_value = freqs["medium_freq"]
        if "PROC_MediumHeightMul" in nodes:
            nodes["PROC_MediumHeightMul"].inputs[1].default_value = float(params.medium_undulation_height)

        # Sync Universal Road System parameters live
        if "PROC_RoadRotate" in nodes:
            nodes["PROC_RoadRotate"].inputs["Angle"].default_value = math.radians(float(params.road_direction_deg))
        if "PROC_RoadMeanderNoise" in nodes:
            nodes["PROC_RoadMeanderNoise"].inputs["Scale"].default_value = freqs["road_freq"]
        if "PROC_RoadMeanderAmp" in nodes:
            nodes["PROC_RoadMeanderAmp"].inputs[1].default_value = float(params.road_meander_amplitude) * 2.0
        if "PROC_RoadLateralOffset" in nodes:
            nodes["PROC_RoadLateralOffset"].inputs[1].default_value = float(params.road_offset_m)
        if "PROC_RoadBranchSlopeX" in nodes:
            nodes["PROC_RoadBranchSlopeX"].inputs[1].default_value = (
                0.62 if params.road_secondary_branch else 9999.0
            )
        if "PROC_RoadMaskRange" in nodes:
            nodes["PROC_RoadMaskRange"].inputs["From Min"].default_value = freqs["road_half_w"]
            nodes["PROC_RoadMaskRange"].inputs["From Max"].default_value = freqs["road_outer_w"]
        if "PROC_RoadBermHeightMul" in nodes:
            nodes["PROC_RoadBermHeightMul"].inputs[1].default_value = (
                float(params.road_berm_height_m) * 4.0 if params.enable_road else 0.0
            )
        if "PROC_RoadMacroFollow" in nodes:
            nodes["PROC_RoadMacroFollow"].inputs[1].default_value = float(params.road_elevation_follow)
        if "PROC_RoadTargetZ" in nodes:
            nodes["PROC_RoadTargetZ"].inputs[1].default_value = float(params.road_carve_depth_m)
        if "PROC_RoadEffectiveFactor" in nodes:
            nodes["PROC_RoadEffectiveFactor"].inputs[1].default_value = freqs["road_active_factor"]
        if "PROC_RoadShaderMaskEnable" in nodes:
            nodes["PROC_RoadShaderMaskEnable"].inputs[1].default_value = freqs["road_mask_enable"]

        if "PROC_TopologicalSmoothZ" in nodes:
            n_blur = nodes["PROC_TopologicalSmoothZ"]
            if "Iterations" in n_blur.inputs:
                n_blur.inputs["Iterations"].default_value = int(params.mesh_smooth_iterations)
            if "Weight" in n_blur.inputs:
                n_blur.inputs["Weight"].default_value = float(params.mesh_smooth_factor)
        if "PROC_SetShadeSmooth" in nodes:
            n_sm = nodes["PROC_SetShadeSmooth"]
            if "Shade Smooth" in n_sm.inputs:
                n_sm.inputs["Shade Smooth"].default_value = bool(params.shade_smooth)

    def _create_new_terrain_mesh(
        self,
        params: TerrainEngineParams,
        perf_cfg: Dict[str, Any],
        scene: Any,
        collections: Optional[Dict[str, Any]],
    ) -> Any:
        import bmesh

        mesh_name = f"{PREFIX}_Terrain_Mesh"
        obj_name = f"{PREFIX}_Terrain"
        mesh = self.bpy.data.meshes.new(mesh_name)
        obj = self.bpy.data.objects.new(obj_name, mesh)

        target_col = None
        if collections and "TERRAIN" in collections:
            target_col = collections["TERRAIN"]
        elif hasattr(scene, "collection"):
            target_col = scene.collection

        if target_col and hasattr(target_col, "objects"):
            target_col.objects.link(obj)

        bm = bmesh.new()
        res = int(perf_cfg.get("new_terrain_grid_res", 256))
        bmesh.ops.create_grid(
            bm,
            x_segments=res,
            y_segments=res,
            size=0.5,
            calc_uvs=True,
        )
        sx = float(params.world_size_x)
        sy = float(params.world_size_y)
        for v in bm.verts:
            v.co.x *= sx
            v.co.y *= sy

        bm.to_mesh(mesh)
        bm.free()
        return obj
