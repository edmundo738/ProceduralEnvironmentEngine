"""
VALIDATOR (Section 19 — Critério de Sucesso do V0 / CP-02)
Measures and verifies before/after state, generation time, geometry load,
PBR connections, branching Voronoi nodes, topological smoothing, and parameter responsiveness.
"""

from typing import Any, Dict, List
from ..config import TERRAIN_MODIFIER_NAME, TERRAIN_NODE_GROUP_NAME, TerrainEngineParams
from .data_models import SceneRawAnalysis, ValidationReport
from .layer3_terrain import _compute_effective_frequencies


class EngineValidator:
    """Validates the result of Layer 3 & Layer 4 generation against CP-02 criteria."""

    def __init__(self, bpy_module: Any = None):
        if bpy_module is None:
            import bpy as _bpy
            self.bpy = _bpy
        else:
            self.bpy = bpy_module

    def validate(
        self,
        before: SceneRawAnalysis,
        after: SceneRawAnalysis,
        params: TerrainEngineParams,
        terrain_result: Dict[str, Any],
        surface_result: Dict[str, Any],
        execution_time_ms: float,
    ) -> ValidationReport:
        t_before = before.primary_terrain
        t_after = after.primary_terrain

        before_dims = t_before.dimensions_m if t_before else (0.0, 0.0, 0.0)
        after_dims = t_after.dimensions_m if t_after else (0.0, 0.0, 0.0)
        before_verts = t_before.base_vertices if t_before else 0
        after_verts = t_after.base_vertices if t_after else 0
        before_r_polys = t_before.estimated_render_polygons if t_before else 0
        after_r_polys = t_after.estimated_render_polygons if t_after else 0

        dunes_mod_active = False
        if t_after:
            for m in t_after.modifiers:
                if m.name == TERRAIN_MODIFIER_NAME and m.show_viewport:
                    dunes_mod_active = True
                    break

        mat_after = t_after.active_material if t_after else None
        connected_pbr: List[str] = mat_after.connected_image_names if mat_after else []

        # Verify parameter responsiveness inside Geometry Nodes & Shader
        param_checks: Dict[str, Any] = {}
        freqs = _compute_effective_frequencies(params)
        ng = getattr(self.bpy.data, "node_groups", {}).get(TERRAIN_NODE_GROUP_NAME)
        if ng and getattr(ng, "nodes", None):
            if "PROC_DuneHeightMul" in ng.nodes:
                actual_h = float(ng.nodes["PROC_DuneHeightMul"].inputs[1].default_value)
                param_checks["dune_height_applied_m"] = round(actual_h, 3)
                param_checks["dune_height_matches"] = abs(actual_h - params.dune_height) < 1e-3
            if "PROC_PrimaryDuneWave" in ng.nodes:
                actual_scale = float(ng.nodes["PROC_PrimaryDuneWave"].inputs["Scale"].default_value)
                param_checks["dune_wave_scale"] = round(actual_scale, 5)
                param_checks["dune_scale_matches"] = abs(actual_scale - freqs["wave_freq"]) < 1e-4
                param_checks["wave_profile"] = getattr(ng.nodes["PROC_PrimaryDuneWave"], "wave_profile", "SIN")
            if "PROC_BranchingVoronoiMain" in ng.nodes:
                param_checks["branching_voronoi_active"] = True
            if "PROC_TopologicalSmoothZ" in ng.nodes:
                param_checks["topological_blur_active"] = True

        notes: List[str] = []
        if before_verts > 0 and after_verts == before_verts:
            notes.append(f"PASS: Geometria base preservada em {after_verts:,} vértices (zero explosão geométrica).")
        if before_r_polys > after_r_polys:
            notes.append(
                f"PASS: Carga de polígonos no Render otimizada de ~{before_r_polys:,} para ~{after_r_polys:,}."
            )
        if dunes_mod_active:
            notes.append(
                f"PASS: Sistema de dunas cinematográficas '{TERRAIN_MODIFIER_NAME}' ativo "
                f"(Morfologia={params.dune_morphology}, Escala={params.dune_scale:.1f}, "
                f"Ramificação={params.dune_branching:.2f}, Blur={params.mesh_smooth_iterations} iterações)."
            )
        if connected_pbr:
            notes.append(
                f"PASS: {len(connected_pbr)} mapas PBR conectados ao shader com escala métrica "
                f"({params.pbr_tile_size_meters:.1f}m por tile): {', '.join(connected_pbr)}."
            )
        if surface_result.get("backup_material_name"):
            notes.append(f"PASS: Backup reversível limpo criado: '{surface_result['backup_material_name']}'.")

        success = bool(dunes_mod_active and t_after is not None)

        return ValidationReport(
            success=success,
            execution_time_ms=round(execution_time_ms, 2),
            terrain_object_name=t_after.name if t_after else "",
            before_dimensions_m=before_dims,
            after_dimensions_m=after_dims,
            before_base_vertices=before_verts,
            after_base_vertices=after_verts,
            before_estimated_render_polys=before_r_polys,
            after_estimated_render_polys=after_r_polys,
            dunes_modifier_active=dunes_mod_active,
            surface_material_name=mat_after.name if mat_after else "",
            pbr_maps_connected=connected_pbr,
            mapping_method_used=str(surface_result.get("mapping_method", "")),
            pbr_tile_size_m=float(surface_result.get("pbr_tile_size_meters", 0.0)),
            backup_created=bool(surface_result.get("backup_material_name") or after.has_existing_snapshot),
            backup_material_name=str(surface_result.get("backup_material_name", "")),
            parameter_verification=param_checks,
            notes=notes,
        )
