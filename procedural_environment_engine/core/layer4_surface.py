"""
LAYER 4 — MULTI-BIOME & ROAD SURFACE GENERATOR (CP-03)
Combines:
- Multi-Scale Procedural Ground (Sand / Grass / Moss / Savanna Soil / Fantasy Turf)
- Slope-Based Procedural Rock & Cliff Outcrops (`Normal.Z` -> `PROC_SlopeRockMask`)
- Automatic Road / Path Surface Shading (`ShaderNodeAttribute` reading `proc_road_mask`)
- Existing 4K PBR Maps (`red_sand_4k`) with Metric Anti-Stretching Mapping & Anti-Tiling
"""

import math
from typing import Any, Dict, List, Optional, Tuple
from ..config import (
    TerrainEngineParams,
    MappingMethod,
    SURFACE_MATERIAL_NAME,
    ROAD_MASK_ATTRIBUTE_NAME,
)
from .data_models import PBRMapInfo


def _get_mix_rgba_sockets(mix_node: Any) -> Tuple[Any, Any, Any, Any]:
    """
    Returns (factor_in, a_in, b_in, result_out) for a `ShaderNodeMix` configured with `data_type='RGBA'`
    compatible across Blender 3.x, 4.x, and 5.2+ LTS.
    """
    inputs = list(getattr(mix_node, "inputs", []))
    outputs = list(getattr(mix_node, "outputs", []))

    factor_in = inputs[0] if inputs else None
    rgba_ins = [s for s in inputs if str(getattr(s, "type", "")) == "RGBA"]
    if len(rgba_ins) >= 2:
        a_in, b_in = rgba_ins[0], rgba_ins[1]
    else:
        a_in = next((s for s in inputs if s.name in ("A", "Color1")), inputs[1] if len(inputs) > 1 else None)
        b_in = next((s for s in inputs if s.name in ("B", "Color2")), inputs[2] if len(inputs) > 2 else None)

    rgba_outs = [s for s in outputs if str(getattr(s, "type", "")) == "RGBA"]
    if rgba_outs:
        res_out = rgba_outs[0]
    else:
        res_out = next((s for s in outputs if s.name in ("Result", "Color")), outputs[0] if outputs else None)

    return factor_in, a_in, b_in, res_out


class SurfaceGenerator:
    """
    Layer 4: Builds and updates the Multi-Biome (Desert / Mountain / Valley / Savanna / Fantasy)
    + Slope Rock + Road Path + PBR 4K surface shader.
    """

    def __init__(self, bpy_module: Any = None):
        if bpy_module is None:
            import bpy as _bpy
            self.bpy = _bpy
        else:
            self.bpy = bpy_module

    def apply_surface(
        self,
        terrain_obj: Any,
        params: TerrainEngineParams,
        available_pbr: Dict[str, PBRMapInfo],
        state_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        orig_mat = getattr(terrain_obj, "active_material", None)
        backup_name = ""
        if orig_mat is not None and state_manager is not None:
            if not str(orig_mat.name).startswith("PROC_ENV"):
                backup_name = state_manager.backup_material(orig_mat)

        mat = self.bpy.data.materials.get(SURFACE_MATERIAL_NAME)
        if mat is None:
            mat = self.bpy.data.materials.new(name=SURFACE_MATERIAL_NAME)
        terrain_obj.active_material = mat
        mesh = getattr(terrain_obj, "data", None)
        if mesh and getattr(mesh, "materials", None) is not None:
            if len(mesh.materials) == 0 and hasattr(mesh.materials, "append"):
                mesh.materials.append(mat)
            elif len(mesh.materials) > 0:
                try:
                    mesh.materials[0] = mat
                except Exception:
                    pass

        mat.use_nodes = True

        dims = getattr(terrain_obj, "dimensions", (params.world_size_x, params.world_size_y, 38.0))
        obj_scale = getattr(terrain_obj, "scale", (1.0, 1.0, 1.0))
        dim_x = max(float(dims[0]), 1.0)
        dim_y = max(float(dims[1]), 1.0)

        connected_pbr = self._build_hybrid_surface_shader(
            mat=mat,
            params=params,
            available_pbr=available_pbr,
            dim_x=dim_x,
            dim_y=dim_y,
            obj_scale=(float(obj_scale[0]), float(obj_scale[1]), float(obj_scale[2])),
        )

        return {
            "material_name": mat.name,
            "backup_material_name": backup_name,
            "connected_pbr_maps": connected_pbr,
            "mapping_method": params.mapping_method,
            "pbr_tile_size_meters": params.pbr_tile_size_meters,
        }

    def _build_hybrid_surface_shader(
        self,
        mat: Any,
        params: TerrainEngineParams,
        available_pbr: Dict[str, PBRMapInfo],
        dim_x: float,
        dim_y: float,
        obj_scale: Tuple[float, float, float],
    ) -> List[str]:
        nt = mat.node_tree
        nodes = nt.nodes
        links = nt.links
        nodes.clear()

        connected_pbr_names: List[str] = []

        # ------------------------------------------------------------------
        # A. OUTPUT & PRINCIPLED BSDF
        # ------------------------------------------------------------------
        n_out = nodes.new("ShaderNodeOutputMaterial")
        n_out.name = "Material Output"
        n_out.location = (1450, 100)

        n_bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        n_bsdf.name = "Principled BSDF"
        n_bsdf.location = (1120, 100)
        links.new(n_bsdf.outputs["BSDF"], n_out.inputs["Surface"])

        if "IOR" in n_bsdf.inputs:
            n_bsdf.inputs["IOR"].default_value = 1.46
        if "Specular IOR Level" in n_bsdf.inputs:
            n_bsdf.inputs["Specular IOR Level"].default_value = 0.25
        elif "Specular" in n_bsdf.inputs:
            n_bsdf.inputs["Specular"].default_value = 0.25

        # ------------------------------------------------------------------
        # B. METRIC & ASPECT-CORRECTED COORDINATE MAPPING (ZERO STRETCHING)
        # ------------------------------------------------------------------
        n_texcoord = nodes.new("ShaderNodeTexCoord")
        n_texcoord.name = "PROC_TexCoord"
        n_texcoord.location = (-1850, 0)

        n_metric_scale = nodes.new("ShaderNodeVectorMath")
        n_metric_scale.name = "PROC_ObjectToMeters"
        n_metric_scale.operation = "MULTIPLY"
        n_metric_scale.location = (-1620, 160)
        links.new(n_texcoord.outputs["Object"], n_metric_scale.inputs[0])
        sx = abs(obj_scale[0]) if abs(obj_scale[0]) > 1e-4 else 1.0
        sy = abs(obj_scale[1]) if abs(obj_scale[1]) > 1e-4 else 1.0
        sz = abs(obj_scale[2]) if abs(obj_scale[2]) > 1e-4 else 1.0
        n_metric_scale.inputs[1].default_value = (sx, sy, sz)

        tile_m = max(float(params.pbr_tile_size_meters), 0.1)
        n_mapping = nodes.new("ShaderNodeMapping")
        n_mapping.name = "PROC_PBR_Mapping"
        n_mapping.location = (-1380, -140)

        if params.mapping_method == MappingMethod.ASPECT_CORRECTED_UV:
            links.new(n_texcoord.outputs["UV"], n_mapping.inputs["Vector"])
            n_mapping.inputs["Scale"].default_value = (dim_x / tile_m, dim_y / tile_m, 1.0)
        else:
            links.new(n_metric_scale.outputs["Vector"], n_mapping.inputs["Vector"])
            inv_tile = 1.0 / tile_m
            n_mapping.inputs["Scale"].default_value = (inv_tile, inv_tile, inv_tile)

        n_detile_noise = nodes.new("ShaderNodeTexNoise")
        n_detile_noise.name = "PROC_AntiTilingNoise"
        n_detile_noise.location = (-1380, -420)
        n_detile_noise.inputs["Scale"].default_value = 0.075
        n_detile_noise.inputs["Detail"].default_value = 2.0
        links.new(n_metric_scale.outputs["Vector"], n_detile_noise.inputs["Vector"])

        n_detile_scale = nodes.new("ShaderNodeVectorMath")
        n_detile_scale.name = "PROC_AntiTilingScale"
        n_detile_scale.operation = "SCALE"
        n_detile_scale.location = (-1160, -420)
        links.new(n_detile_noise.outputs["Color"], n_detile_scale.inputs[0])
        n_detile_scale.inputs["Scale"].default_value = float(params.anti_tiling_strength) * 0.35

        n_pbr_coords = nodes.new("ShaderNodeVectorMath")
        n_pbr_coords.name = "PROC_DetiledPBRVector"
        n_pbr_coords.operation = "ADD"
        n_pbr_coords.location = (-1020, -180)
        links.new(n_mapping.outputs["Vector"], n_pbr_coords.inputs[0])
        links.new(n_detile_scale.outputs["Vector"], n_pbr_coords.inputs[1])

        # ------------------------------------------------------------------
        # C. PROCEDURAL MULTI-SCALE GROUND (SAND / GRASS / MOSS / SAVANNA)
        # ------------------------------------------------------------------
        n_macro_noise = nodes.new("ShaderNodeTexNoise")
        n_macro_noise.name = "PROC_SandMacroNoise"
        n_macro_noise.location = (-1250, 560)
        n_macro_noise.inputs["Scale"].default_value = 0.0045
        n_macro_noise.inputs["Detail"].default_value = 3.0
        n_macro_noise.inputs["Roughness"].default_value = 0.55
        links.new(n_metric_scale.outputs["Vector"], n_macro_noise.inputs["Vector"])

        n_macro_ramp = nodes.new("ShaderNodeValToRGB")
        n_macro_ramp.name = "PROC_SandMacroColorRamp"
        n_macro_ramp.location = (-980, 560)
        elems = n_macro_ramp.color_ramp.elements
        elems[0].position = 0.25
        elems[0].color = params.color_sand_trough
        elems[1].position = 0.75
        elems[1].color = params.color_sand_crest
        links.new(n_macro_noise.outputs["Fac"], n_macro_ramp.inputs["Fac"])

        n_med_noise = nodes.new("ShaderNodeTexNoise")
        n_med_noise.name = "PROC_SandMediumNoise"
        n_med_noise.location = (-1250, 300)
        n_med_noise.inputs["Scale"].default_value = 0.05
        n_med_noise.inputs["Detail"].default_value = 4.0
        n_med_noise.inputs["Roughness"].default_value = 0.6
        links.new(n_metric_scale.outputs["Vector"], n_med_noise.inputs["Vector"])

        n_med_ramp = nodes.new("ShaderNodeValToRGB")
        n_med_ramp.name = "PROC_SandMediumColorRamp"
        n_med_ramp.location = (-980, 300)
        m_elems = n_med_ramp.color_ramp.elements
        m_elems[0].position = 0.30
        m_elems[0].color = params.color_moss
        m_elems[1].position = 0.78
        m_elems[1].color = params.color_sand_primary
        links.new(n_med_noise.outputs["Fac"], n_med_ramp.inputs["Fac"])

        n_proc_color_mix = nodes.new("ShaderNodeMix")
        n_proc_color_mix.name = "PROC_ProceduralSandMix"
        n_proc_color_mix.data_type = "RGBA"
        n_proc_color_mix.blend_type = "MIX"
        n_proc_color_mix.location = (-680, 420)
        fac_in, a_in, b_in, proc_col_out = _get_mix_rgba_sockets(n_proc_color_mix)
        fac_in.default_value = float(params.sand_color_variation)
        links.new(n_macro_ramp.outputs["Color"], a_in)
        links.new(n_med_ramp.outputs["Color"], b_in)

        # ------------------------------------------------------------------
        # D. PBR 4K MAPS REINTEGRATION (DIFFUSE, ROUGHNESS, NORMAL)
        # ------------------------------------------------------------------
        diff_img = self._resolve_image("DIFFUSE", available_pbr)
        rough_img = self._resolve_image("ROUGHNESS", available_pbr)
        norm_img = self._resolve_image("NORMAL", available_pbr)

        ground_color_socket = proc_col_out
        if params.use_pbr_maps and diff_img is not None:
            try:
                diff_img.colorspace_settings.name = "sRGB"
            except Exception:
                pass
            n_tex_diff = nodes.new("ShaderNodeTexImage")
            n_tex_diff.name = "PROC_PBR_Diffuse"
            n_tex_diff.image = diff_img
            n_tex_diff.location = (-740, 80)
            links.new(n_pbr_coords.outputs["Vector"], n_tex_diff.inputs["Vector"])
            connected_pbr_names.append(str(diff_img.name))

            n_pbr_col_mix = nodes.new("ShaderNodeMix")
            n_pbr_col_mix.name = "PROC_PBR_Procedural_ColorBlend"
            n_pbr_col_mix.data_type = "RGBA"
            n_pbr_col_mix.blend_type = "MIX"
            n_pbr_col_mix.location = (-420, 280)
            p_fac, p_a, p_b, p_out = _get_mix_rgba_sockets(n_pbr_col_mix)
            p_fac.default_value = float(params.pbr_blend_factor)
            links.new(proc_col_out, p_a)
            links.new(n_tex_diff.outputs["Color"], p_b)
            ground_color_socket = p_out

        # ------------------------------------------------------------------
        # E. SLOPE-BASED PROCEDURAL ROCK & CLIFF LAYER (CP-03)
        # ------------------------------------------------------------------
        rock_blend_out = ground_color_socket
        try:
            n_geom = nodes.new("ShaderNodeNewGeometry")
            n_geom.name = "PROC_ShaderGeometry"
            n_geom.location = (-980, 820)

            n_norm_sep = nodes.new("ShaderNodeSeparateXYZ")
            n_norm_sep.name = "PROC_SlopeNormalZ"
            n_norm_sep.location = (-780, 820)
            links.new(n_geom.outputs["Normal"], n_norm_sep.inputs["Vector"])

            # Steep slope mask: Normal.Z < rock_slope_threshold -> 1.0 (Rock), else 0.0 (Ground)
            n_slope_mask = nodes.new("ShaderNodeMapRange")
            n_slope_mask.name = "PROC_SlopeRockMask"
            n_slope_mask.location = (-560, 820)
            thresh = float(params.rock_slope_threshold)
            sharp = max(0.02, float(params.rock_blend_sharpness))
            n_slope_mask.inputs["From Min"].default_value = max(0.0, thresh - sharp)
            n_slope_mask.inputs["From Max"].default_value = min(1.0, thresh + sharp)
            n_slope_mask.inputs["To Min"].default_value = 1.0
            n_slope_mask.inputs["To Max"].default_value = 0.0
            links.new(n_norm_sep.outputs["Z"], n_slope_mask.inputs["Value"])

            n_rock_noise = nodes.new("ShaderNodeTexNoise")
            n_rock_noise.name = "PROC_RockStrataNoise"
            n_rock_noise.location = (-780, 660)
            n_rock_noise.inputs["Scale"].default_value = 0.14
            n_rock_noise.inputs["Detail"].default_value = 5.0
            n_rock_noise.inputs["Roughness"].default_value = 0.65
            links.new(n_metric_scale.outputs["Vector"], n_rock_noise.inputs["Vector"])

            n_rock_ramp = nodes.new("ShaderNodeValToRGB")
            n_rock_ramp.name = "PROC_RockColorRamp"
            n_rock_ramp.location = (-520, 660)
            r_elems = n_rock_ramp.color_ramp.elements
            rc = params.color_rock
            r_elems[0].position = 0.25
            r_elems[0].color = (rc[0] * 0.65, rc[1] * 0.65, rc[2] * 0.65, 1.0)
            r_elems[1].position = 0.78
            r_elems[1].color = (min(1.0, rc[0] * 1.35), min(1.0, rc[1] * 1.35), min(1.0, rc[2] * 1.35), 1.0)
            links.new(n_rock_noise.outputs["Fac"], n_rock_ramp.inputs["Fac"])

            n_rock_mix = nodes.new("ShaderNodeMix")
            n_rock_mix.name = "PROC_SlopeRockColorMix"
            n_rock_mix.data_type = "RGBA"
            n_rock_mix.blend_type = "MIX"
            n_rock_mix.location = (-160, 420)
            r_fac, r_a, r_b, r_out = _get_mix_rgba_sockets(n_rock_mix)
            links.new(n_slope_mask.outputs["Result"], r_fac)
            links.new(ground_color_socket, r_a)
            links.new(n_rock_ramp.outputs["Color"], r_b)
            rock_blend_out = r_out
        except Exception:
            pass

        # ------------------------------------------------------------------
        # F. UNIVERSAL ROAD & PATH SHADER LAYER (`proc_road_mask` attribute)
        # ------------------------------------------------------------------
        final_color_socket = rock_blend_out
        try:
            n_road_attr = nodes.new("ShaderNodeAttribute")
            n_road_attr.name = "PROC_RoadMaskAttr"
            n_road_attr.attribute_name = ROAD_MASK_ATTRIBUTE_NAME
            n_road_attr.location = (-420, 720)

            n_road_ramp = nodes.new("ShaderNodeValToRGB")
            n_road_ramp.name = "PROC_RoadColorRamp"
            n_road_ramp.location = (-420, 560)
            rd = params.color_road
            rd_elems = n_road_ramp.color_ramp.elements
            rd_elems[0].position = 0.20
            rd_elems[0].color = (rd[0] * 0.78, rd[1] * 0.78, rd[2] * 0.78, 1.0)
            rd_elems[1].position = 0.80
            rd_elems[1].color = (min(1.0, rd[0] * 1.22), min(1.0, rd[1] * 1.22), min(1.0, rd[2] * 1.22), 1.0)
            links.new(n_med_noise.outputs["Fac"], n_road_ramp.inputs["Fac"])

            n_road_col_mix = nodes.new("ShaderNodeMix")
            n_road_col_mix.name = "PROC_RoadSurfaceColorMix"
            n_road_col_mix.data_type = "RGBA"
            n_road_col_mix.blend_type = "MIX"
            n_road_col_mix.location = (120, 420)
            rd_fac, rd_a, rd_b, rd_out = _get_mix_rgba_sockets(n_road_col_mix)
            links.new(n_road_attr.outputs["Fac"], rd_fac)
            links.new(rock_blend_out, rd_a)
            links.new(n_road_ramp.outputs["Color"], rd_b)
            final_color_socket = rd_out
        except Exception:
            pass

        links.new(final_color_socket, n_bsdf.inputs["Base Color"])

        # ------------------------------------------------------------------
        # G. ROUGHNESS (PROCEDURAL + PBR 4K)
        # ------------------------------------------------------------------
        n_rough_map = nodes.new("ShaderNodeMapRange")
        n_rough_map.name = "PROC_ProceduralRoughnessRange"
        n_rough_map.location = (-560, -240)
        base_r = float(params.sand_roughness_base)
        n_rough_map.inputs["From Min"].default_value = 0.0
        n_rough_map.inputs["From Max"].default_value = 1.0
        n_rough_map.inputs["To Min"].default_value = max(0.55, base_r - 0.10)
        n_rough_map.inputs["To Max"].default_value = min(0.99, base_r + 0.08)
        links.new(n_med_noise.outputs["Fac"], n_rough_map.inputs["Value"])

        if params.use_pbr_maps and rough_img is not None:
            try:
                rough_img.colorspace_settings.name = "Non-Color"
            except Exception:
                pass
            n_tex_rough = nodes.new("ShaderNodeTexImage")
            n_tex_rough.name = "PROC_PBR_Roughness"
            n_tex_rough.image = rough_img
            n_tex_rough.location = (-640, -500)
            links.new(n_pbr_coords.outputs["Vector"], n_tex_rough.inputs["Vector"])
            connected_pbr_names.append(str(rough_img.name))

            n_rough_mix = nodes.new("ShaderNodeMath")
            n_rough_mix.name = "PROC_RoughnessCombine"
            n_rough_mix.operation = "MULTIPLY"
            n_rough_mix.location = (-240, -340)
            links.new(n_tex_rough.outputs["Color"], n_rough_mix.inputs[0])
            links.new(n_rough_map.outputs["Result"], n_rough_mix.inputs[1])
            links.new(n_rough_mix.outputs["Value"], n_bsdf.inputs["Roughness"])
        else:
            links.new(n_rough_map.outputs["Result"], n_bsdf.inputs["Roughness"])

        # ------------------------------------------------------------------
        # H. MICRO VARIATION (WIND RIPPLES / TURF + GRAIN BUMP) + PBR 4K NORMAL
        # ------------------------------------------------------------------
        n_ripple_rot = nodes.new("ShaderNodeVectorRotate")
        n_ripple_rot.name = "PROC_MicroRippleWindRot"
        n_ripple_rot.rotation_type = "Z_AXIS"
        n_ripple_rot.location = (-1120, -700)
        n_ripple_rot.inputs["Angle"].default_value = math.radians(float(params.wind_direction_deg))
        links.new(n_metric_scale.outputs["Vector"], n_ripple_rot.inputs["Vector"])

        n_ripple_wave = nodes.new("ShaderNodeTexWave")
        n_ripple_wave.name = "PROC_MicroSandRipples"
        n_ripple_wave.wave_type = "BANDS"
        n_ripple_wave.bands_direction = "X"
        n_ripple_wave.wave_profile = "SIN"
        n_ripple_wave.location = (-880, -700)
        n_ripple_wave.inputs["Scale"].default_value = float(params.sand_ripple_scale) * 0.15
        n_ripple_wave.inputs["Distortion"].default_value = 2.4
        n_ripple_wave.inputs["Detail"].default_value = 2.0
        links.new(n_ripple_rot.outputs["Vector"], n_ripple_wave.inputs["Vector"])

        n_grain_noise = nodes.new("ShaderNodeTexNoise")
        n_grain_noise.name = "PROC_MicroSandGrain"
        n_grain_noise.location = (-880, -960)
        n_grain_noise.inputs["Scale"].default_value = 65.0
        n_grain_noise.inputs["Detail"].default_value = 4.0
        links.new(n_metric_scale.outputs["Vector"], n_grain_noise.inputs["Vector"])

        n_micro_mix = nodes.new("ShaderNodeMath")
        n_micro_mix.name = "PROC_MicroHeightMix"
        n_micro_mix.operation = "ADD"
        n_micro_mix.location = (-580, -780)
        links.new(n_ripple_wave.outputs["Fac"], n_micro_mix.inputs[0])
        links.new(n_grain_noise.outputs["Fac"], n_micro_mix.inputs[1])

        n_bump = nodes.new("ShaderNodeBump")
        n_bump.name = "PROC_MicroSandBump"
        n_bump.location = (520, -320)
        n_bump.inputs["Strength"].default_value = float(params.sand_bump_strength) * float(params.sand_detail)
        n_bump.inputs["Distance"].default_value = 0.025
        links.new(n_micro_mix.outputs["Value"], n_bump.inputs["Height"])

        if params.use_pbr_maps and norm_img is not None:
            try:
                norm_img.colorspace_settings.name = "Non-Color"
            except Exception:
                pass
            n_tex_norm = nodes.new("ShaderNodeTexImage")
            n_tex_norm.name = "PROC_PBR_Normal"
            n_tex_norm.image = norm_img
            n_tex_norm.location = (-360, -640)
            links.new(n_pbr_coords.outputs["Vector"], n_tex_norm.inputs["Vector"])
            connected_pbr_names.append(str(norm_img.name))

            n_norm_map = nodes.new("ShaderNodeNormalMap")
            n_norm_map.name = "PROC_PBR_NormalMap"
            n_norm_map.location = (40, -540)
            n_norm_map.inputs["Strength"].default_value = float(params.pbr_normal_strength)
            links.new(n_tex_norm.outputs["Color"], n_norm_map.inputs["Color"])
            links.new(n_norm_map.outputs["Normal"], n_bump.inputs["Normal"])

        links.new(n_bump.outputs["Normal"], n_bsdf.inputs["Normal"])

        return connected_pbr_names

    def sync_surface_parameters(
        self,
        mat: Any,
        params: TerrainEngineParams,
        dim_x: float = 590.212,
        dim_y: float = 833.532,
    ) -> None:
        """Fast live-update of multi-biome colors, rock slope, road colors, and PBR mapping."""
        if not mat or not getattr(mat, "use_nodes", False) or not getattr(mat, "node_tree", None):
            return
        nodes = mat.node_tree.nodes

        tile_m = max(float(params.pbr_tile_size_meters), 0.1)
        if "PROC_PBR_Mapping" in nodes:
            if params.mapping_method == MappingMethod.ASPECT_CORRECTED_UV:
                nodes["PROC_PBR_Mapping"].inputs["Scale"].default_value = (dim_x / tile_m, dim_y / tile_m, 1.0)
            else:
                inv = 1.0 / tile_m
                nodes["PROC_PBR_Mapping"].inputs["Scale"].default_value = (inv, inv, inv)

        if "PROC_AntiTilingScale" in nodes:
            nodes["PROC_AntiTilingScale"].inputs["Scale"].default_value = float(params.anti_tiling_strength) * 0.35

        if "PROC_SandMacroColorRamp" in nodes:
            elems = nodes["PROC_SandMacroColorRamp"].color_ramp.elements
            if len(elems) >= 2:
                elems[0].color = params.color_sand_trough
                elems[1].color = params.color_sand_crest

        if "PROC_SandMediumColorRamp" in nodes:
            elems = nodes["PROC_SandMediumColorRamp"].color_ramp.elements
            if len(elems) >= 2:
                elems[0].color = params.color_moss
                elems[1].color = params.color_sand_primary

        if "PROC_RockColorRamp" in nodes:
            elems = nodes["PROC_RockColorRamp"].color_ramp.elements
            rc = params.color_rock
            if len(elems) >= 2:
                elems[0].color = (rc[0] * 0.65, rc[1] * 0.65, rc[2] * 0.65, 1.0)
                elems[1].color = (min(1.0, rc[0] * 1.35), min(1.0, rc[1] * 1.35), min(1.0, rc[2] * 1.35), 1.0)

        if "PROC_RoadColorRamp" in nodes:
            elems = nodes["PROC_RoadColorRamp"].color_ramp.elements
            rd = params.color_road
            if len(elems) >= 2:
                elems[0].color = (rd[0] * 0.78, rd[1] * 0.78, rd[2] * 0.78, 1.0)
                elems[1].color = (min(1.0, rd[0] * 1.22), min(1.0, rd[1] * 1.22), min(1.0, rd[2] * 1.22), 1.0)

        if "PROC_SlopeRockMask" in nodes:
            thresh = float(params.rock_slope_threshold)
            sharp = max(0.02, float(params.rock_blend_sharpness))
            nodes["PROC_SlopeRockMask"].inputs["From Min"].default_value = max(0.0, thresh - sharp)
            nodes["PROC_SlopeRockMask"].inputs["From Max"].default_value = min(1.0, thresh + sharp)

        if "PROC_ProceduralSandMix" in nodes:
            fac_in, _, _, _ = _get_mix_rgba_sockets(nodes["PROC_ProceduralSandMix"])
            if fac_in is not None:
                fac_in.default_value = float(params.sand_color_variation)

        if "PROC_PBR_Procedural_ColorBlend" in nodes:
            fac_in, _, _, _ = _get_mix_rgba_sockets(nodes["PROC_PBR_Procedural_ColorBlend"])
            if fac_in is not None:
                fac_in.default_value = float(params.pbr_blend_factor)

        if "PROC_MicroSandRipples" in nodes:
            nodes["PROC_MicroSandRipples"].inputs["Scale"].default_value = float(params.sand_ripple_scale) * 0.15

        if "PROC_MicroRippleWindRot" in nodes:
            nodes["PROC_MicroRippleWindRot"].inputs["Angle"].default_value = math.radians(float(params.wind_direction_deg))

        if "PROC_MicroSandBump" in nodes:
            nodes["PROC_MicroSandBump"].inputs["Strength"].default_value = (
                float(params.sand_bump_strength) * float(params.sand_detail)
            )

        if "PROC_PBR_NormalMap" in nodes:
            nodes["PROC_PBR_NormalMap"].inputs["Strength"].default_value = float(params.pbr_normal_strength)

    def _resolve_image(self, role: str, available_pbr: Dict[str, PBRMapInfo]) -> Optional[Any]:
        info = available_pbr.get(role)
        if info is None:
            return None
        images = getattr(getattr(self.bpy, "data", None), "images", None)
        if images is None:
            return None
        return images.get(info.image_name)
