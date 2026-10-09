"""
CENTRAL ORCHESTRATOR — PROCEDURAL ENVIRONMENT ENGINE (V0.4 — CP-04)
Coordinates:
  SCAN (Layer 1) -> INTERPRET (Layer 2) -> SNAPSHOT (StateManager) ->
  GENERATE TERRAIN & ROADS (Layer 3) -> GENERATE SURFACE (Layer 4) ->
  POPULATE HOUSES, PROPS, ROCKS, VEGETATION & DECALS (Layer 5) -> VALIDATE (Validator)
"""

import time
from typing import Any, Dict, Optional, Tuple
from ..config import (
    TerrainEngineParams,
    OperationMode,
    TERRAIN_MODIFIER_NAME,
    TERRAIN_NODE_GROUP_NAME,
)
from .data_models import (
    SceneRawAnalysis,
    ContextInterpretationReport,
    ValidationReport,
)
from .layer1_analyzer import SceneAnalyzer
from .layer2_interpreter import ContextInterpreter
from .state_manager import StateManager
from .layer3_terrain import TerrainGenerator
from .layer4_surface import SurfaceGenerator
from .layer5_environment import EnvironmentGenerator
from .validator import EngineValidator


class ProceduralEnvironmentEngine:
    """Main entry point for both the Blender N-Panel UI and standalone scripts."""

    def __init__(self, bpy_module: Any = None):
        if bpy_module is None:
            import bpy as _bpy
            self.bpy = _bpy
        else:
            self.bpy = bpy_module

        self.analyzer = SceneAnalyzer(self.bpy)
        self.interpreter = ContextInterpreter()
        self.state_manager = StateManager(self.bpy)
        self.terrain_gen = TerrainGenerator(self.bpy)
        self.surface_gen = SurfaceGenerator(self.bpy)
        self.environment_gen = EnvironmentGenerator(self.bpy)
        self.validator = EngineValidator(self.bpy)

    def analyze_only(
        self,
        scene: Any = None,
        preferred_terrain_name: Optional[str] = None,
    ) -> Tuple[SceneRawAnalysis, ContextInterpretationReport]:
        """Runs Layer 1 (Scene Analyzer) and Layer 2 (Context Interpreter) without modifying anything."""
        raw = self.analyzer.analyze(scene=scene, preferred_terrain_name=preferred_terrain_name)
        context_report = self.interpreter.interpret(raw)
        return raw, context_report

    def run_v0(
        self,
        params: Optional[TerrainEngineParams] = None,
        scene: Any = None,
        preferred_terrain_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the full Procedural Environment Engine pipeline (CP-04):
        SCAN -> MEASURE -> CLASSIFY -> SNAPSHOT ->
        GENERATE TERRAIN & ROADS -> GENERATE SURFACE ->
        POPULATE HOUSES, PROPS, ROCKS, VEGETATION & DECALS -> VALIDATE
        """
        if params is None:
            params = TerrainEngineParams()
        if scene is None:
            scene = self.bpy.context.scene

        t0 = time.perf_counter()

        # 1. Layer 1 & Layer 2: Analyze & Interpret before touching anything
        raw_before, interpretation = self.analyze_only(
            scene=scene,
            preferred_terrain_name=preferred_terrain_name,
        )

        if params.operation_mode == OperationMode.ANALYZE_ONLY:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "mode": OperationMode.ANALYZE_ONLY,
                "raw_before": raw_before,
                "interpretation": interpretation,
                "validation": None,
                "execution_time_ms": round(elapsed_ms, 2),
                "formatted_report": self.format_diagnostic_report(raw_before, interpretation, None),
            }

        # Resolve target terrain object if present
        terrain_obj = None
        if raw_before.primary_terrain is not None:
            t_name = raw_before.primary_terrain.name
            objs = getattr(scene, "objects", {})
            terrain_obj = objs.get(t_name) if hasattr(objs, "get") else None
            if terrain_obj is None:
                for o in objs:
                    if o.name == t_name:
                        terrain_obj = o
                        break

        # 2. Ensure Collection Hierarchy & Create Reversible Snapshot
        collections = self.state_manager.ensure_collection_hierarchy(scene=scene)
        snapshot = {}
        if terrain_obj is not None:
            snapshot = self.state_manager.create_snapshot(terrain_obj, scene=scene)

        # 3. Layer 3: Generate / Update Terrain Deformations & Universal Road System
        terrain_result = self.terrain_gen.apply_terrain(
            terrain_obj=terrain_obj,
            params=params,
            scene=scene,
            collections=collections,
        )
        active_terrain_obj = terrain_result["terrain_object"]

        # 4. Layer 4: Generate / Update Multi-Biome + Road + PBR 4K Surface
        surface_result = self.surface_gen.apply_surface(
            terrain_obj=active_terrain_obj,
            params=params,
            available_pbr=raw_before.available_pbr_maps,
            state_manager=self.state_manager,
        )

        # 5. Layer 5: Populate Procedural Houses, Roadside Props, Rocks, Vegetation & Decals
        environment_result = self.environment_gen.populate_scenario(
            terrain_obj=active_terrain_obj,
            params=params,
            scene=scene,
            collections=collections,
        )

        # 6. Re-scan and Validate (Section 19)
        raw_after = self.analyzer.analyze(
            scene=scene,
            preferred_terrain_name=active_terrain_obj.name,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        validation = self.validator.validate(
            before=raw_before,
            after=raw_after,
            params=params,
            terrain_result=terrain_result,
            surface_result=surface_result,
            execution_time_ms=elapsed_ms,
        )
        if environment_result.get("total_spawned", 0) > 0:
            validation.notes.append(
                f"PASS: Layer 5 gerou {environment_result['total_spawned']} objetos no cenário "
                f"({environment_result['houses_spawned']} Casas, {environment_result['props_spawned']} Props, "
                f"{environment_result['rocks_spawned']} Rochas, {environment_result['vegetation_spawned']} Vegetação, "
                f"{environment_result['decals_spawned']} Decals)."
            )

        return {
            "mode": params.operation_mode,
            "raw_before": raw_before,
            "interpretation": interpretation,
            "snapshot": snapshot,
            "terrain_result": terrain_result,
            "surface_result": surface_result,
            "environment_result": environment_result,
            "raw_after": raw_after,
            "validation": validation,
            "execution_time_ms": round(elapsed_ms, 2),
            "formatted_report": self.format_diagnostic_report(
                raw_before, interpretation, validation, environment_result
            ),
        }

    def live_update_parameters(
        self,
        params: TerrainEngineParams,
        scene: Any = None,
        preferred_terrain_name: Optional[str] = None,
    ) -> bool:
        """
        Lightweight live update called when the user drags sliders in the N-Panel.
        Updates the Geometry Nodes sockets/values and Shader parameters in real time.
        """
        if scene is None:
            scene = self.bpy.context.scene

        raw = self.analyzer.analyze(scene=scene, preferred_terrain_name=preferred_terrain_name)
        if raw.primary_terrain is None:
            return False

        t_name = raw.primary_terrain.name
        objs = getattr(scene, "objects", {})
        terrain_obj = objs.get(t_name) if hasattr(objs, "get") else None
        if terrain_obj is None:
            for o in objs:
                if o.name == t_name:
                    terrain_obj = o
                    break
        if terrain_obj is None:
            return False

        proc_mod = None
        for m in getattr(terrain_obj, "modifiers", []):
            if m.name == TERRAIN_MODIFIER_NAME:
                proc_mod = m
                break
        gn_tree = getattr(self.bpy.data, "node_groups", {}).get(TERRAIN_NODE_GROUP_NAME)
        if proc_mod is not None and gn_tree is not None:
            self.terrain_gen.sync_modifier_parameters(proc_mod, gn_tree, params)

        mat = getattr(terrain_obj, "active_material", None)
        if mat is not None:
            dx, dy, _ = raw.primary_terrain.dimensions_m
            self.surface_gen.sync_surface_parameters(mat, params, dim_x=dx, dim_y=dy)

        if hasattr(terrain_obj, "update_tag"):
            try:
                terrain_obj.update_tag()
            except Exception:
                pass
        return True

    def rollback_to_snapshot(self, scene: Any = None) -> Dict[str, Any]:
        """Restores the scene to the state recorded before `run_v0` and removes spawned Layer 5 assets."""
        self.environment_gen.clear_scenario_objects(scene=scene)
        return self.state_manager.restore_snapshot(scene=scene)

    def format_diagnostic_report(
        self,
        raw: SceneRawAnalysis,
        interp: ContextInterpretationReport,
        val: Optional[ValidationReport] = None,
        env_res: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generates a structured, readable engineering report (FACT / INFERRED / UNKNOWN + 5 Questions)."""
        lines = [
            "=" * 78,
            " PROCEDURAL ENVIRONMENT ENGINE V0.4 — RELATÓRIO DE DIAGNÓSTICO E CONSTRUÇÃO",
            "=" * 78,
            f"Blender: {raw.blender_version} | Engine: {raw.render_engine} | "
            f"Scene: {raw.scene_name} ({raw.unit_system}, scale={raw.unit_scale})",
            f"Objetos Iniciais: {raw.total_objects} total ({raw.mesh_objects_count} mesh, "
            f"{raw.camera_objects_count} camera, {raw.light_objects_count} light)",
            "-" * 78,
            "1. SEPARAÇÃO EPISTEMOLÓGICA (FACT / INFERRED / UNKNOWN):",
        ]
        for f in interp.findings:
            lines.append(f"  [{f.tag}] ({f.component}): {f.summary}")

        lines.append("-" * 78)
        lines.append("2. AS 5 PERGUNTAS DO MOTOR (CONTEXT INTERPRETER):")
        lines.append("  • WHAT DO I HAVE?       " + ("; ".join(interp.what_i_have) or "Nada detetado"))
        lines.append("  • WHAT CAN I KEEP?      " + ("; ".join(interp.what_i_can_keep) or "Nada"))
        lines.append("  • WHAT SHOULD I MODIFY? " + ("; ".join(interp.what_i_should_modify) or "Nada"))
        lines.append("  • WHAT IS MISSING?      " + ("; ".join(interp.what_is_missing) or "Nada"))
        lines.append("  • WHAT SHOULD I BUILD?  " + ("; ".join(interp.what_i_should_generate) or "Nada"))

        if val is not None:
            lines.extend([
                "-" * 78,
                "3. VALIDAÇÃO PÓS-GERAÇÃO (TERRAIN + ROAD + SCENARIO ENGINE CP-04):",
                f"  • Status:               {'PASS / SUCESSO' if val.success else 'FALHA'}",
                f"  • Tempo de Execução:    {val.execution_time_ms:.2f} ms",
                f"  • Terreno Alvo:         {val.terrain_object_name}",
                f"  • Vértices Base:        {val.before_base_vertices:,} -> {val.after_base_vertices:,}",
                f"  • Polígonos Est. Render:{val.before_estimated_render_polys:,} -> {val.after_estimated_render_polys:,}",
                f"  • Material Ativo:       {val.surface_material_name} (Backup: {val.backup_material_name or 'Existente'})",
                f"  • Mapas PBR Conectados: {', '.join(val.pbr_maps_connected) if val.pbr_maps_connected else 'Apenas Procedural'}",
                f"  • Mapeamento Anti-Est.: {val.mapping_method_used} ({val.pbr_tile_size_m:.2f}m por tile 4K)",
            ])
            if env_res is not None:
                lines.append(
                    f"  • Objetos de Cenário:   {env_res.get('total_spawned', 0)} gerados "
                    f"(Casas={env_res.get('houses_spawned', 0)}, Props={env_res.get('props_spawned', 0)}, "
                    f"Rochas={env_res.get('rocks_spawned', 0)}, Vegetação={env_res.get('vegetation_spawned', 0)}, "
                    f"Decals={env_res.get('decals_spawned', 0)})"
                )
            lines.append("  • Notas de Validação:")
            for note in val.notes:
                lines.append(f"      - {note}")

        lines.append("=" * 78)
        return "\n".join(lines)
