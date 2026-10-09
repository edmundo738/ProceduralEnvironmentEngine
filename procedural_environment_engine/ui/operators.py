"""
Blender Operators for Procedural Environment Engine V0.3 (CP-03).
Includes Scene Analyzer, Multi-Biome & Road Builder, Seed Randomizer,
Road Layout Randomizer, 3D Road Curve Creator, and 1-Click Rollback.
"""

import random
from typing import Any
from ..core.engine import ProceduralEnvironmentEngine
from .properties import _build_params_from_props


def _populate_ui_diagnostics(props: Any, raw: Any, interp: Any, val: Any = None) -> None:
    props.diag_has_run = True
    t = raw.primary_terrain
    if t is None:
        props.diag_terrain_summary = "MISSING: Nenhum terreno detetado na cena"
        props.diag_geometry_status = "0 vértices"
    else:
        dx, dy, dz = t.dimensions_m
        props.diag_terrain_summary = (
            f"EXISTS: '{t.name}' ({dx:.1f} × {dy:.1f} × {dz:.1f} m | ~{t.area_km2:.2f} km²)"
        )
        props.diag_geometry_status = (
            f"{t.base_vertices:,} verts | Carga: {interp.geometry_load_level}"
        )

    pbr_count = len(raw.available_pbr_maps)
    if val is not None and val.pbr_maps_connected:
        props.diag_pbr_status = (
            f"CONNECTED: {len(val.pbr_maps_connected)} mapas 4K ativos ({val.pbr_tile_size_m:.1f}m/tile)"
        )
    elif t and t.active_material and t.active_material.uses_pbr_maps:
        props.diag_pbr_status = f"CONNECTED: {len(t.active_material.connected_image_names)} mapas ativos"
    elif pbr_count > 0:
        props.diag_pbr_status = f"EXISTS ({pbr_count} mapas 4K no .blend) -> NÃO CONECTADOS ao shader atual"
    else:
        props.diag_pbr_status = "MISSING: Nenhum mapa PBR no .blend (Modo 100% Procedural)"

    if val is not None and val.success:
        props.diag_stretch_status = (
            f"RESOLVIDO: Mapeamento {val.mapping_method_used} ({val.pbr_tile_size_m:.1f}m × {val.pbr_tile_size_m:.1f}m)"
        )
    elif interp.has_pbr_stretch_risk:
        props.diag_stretch_status = (
            f"RISCO DETETADO: Rácio 1:{t.aspect_ratio_xy:.2f} em {max(t.dimensions_m[0], t.dimensions_m[1]):.0f}m"
        )
    else:
        props.diag_stretch_status = "OK"


def _save_report_to_blend_text(bpy_module: Any, report_str: str) -> None:
    """Writes the full diagnostic/validation report to `PROC_ENV_Report.txt` inside the .blend file."""
    texts = getattr(getattr(bpy_module, "data", None), "texts", None)
    if texts is None:
        return
    txt = texts.get("PROC_ENV_Report.txt")
    if txt is None:
        txt = texts.new("PROC_ENV_Report.txt")
    txt.clear()
    txt.write(report_str)


def get_operator_classes(bpy_module: Any):
    class PROCENV_OT_analyze_scene(bpy_module.types.Operator):
        bl_idname = "proc_env.analyze_scene"
        bl_label = "Analisar Cena (Layer 1 & 2)"
        bl_description = "Observa e mede o terreno, vértices, modifiers e mapas PBR sem modificar nada na cena"
        bl_options = {"REGISTER"}

        def execute(self, context: Any):
            props = context.scene.proc_env_settings
            engine = ProceduralEnvironmentEngine(bpy_module)
            raw, interp = engine.analyze_only(scene=context.scene)
            _populate_ui_diagnostics(props, raw, interp, None)
            report_text = engine.format_diagnostic_report(raw, interp, None)
            _save_report_to_blend_text(bpy_module, report_text)
            print(report_text)
            props.diag_last_action = "Análise concluída (Relatório salvo em PROC_ENV_Report.txt)"
            self.report({"INFO"}, "Cena analisada! Veja o painel Diagnóstico ou PROC_ENV_Report.txt.")
            return {"FINISHED"}

    class PROCENV_OT_generate_desert(bpy_module.types.Operator):
        bl_idname = "proc_env.generate_desert"
        bl_label = "Gerar / Construir Cenário & Estrada (CP-03)"
        bl_description = (
            "Executa o pipeline completo CP-03: Analisa -> Cria Snapshot -> "
            "Constrói Terreno Multi-Bioma + Esculpe Estrada -> Aplica Superfície Híbrida -> Valida"
        )
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any):
            props = context.scene.proc_env_settings
            params = _build_params_from_props(props)
            engine = ProceduralEnvironmentEngine(bpy_module)
            result = engine.run_v0(params=params, scene=context.scene)

            raw_after = result["raw_after"]
            interp = result["interpretation"]
            val = result["validation"]
            _populate_ui_diagnostics(props, raw_after, interp, val)

            report_text = result["formatted_report"]
            _save_report_to_blend_text(bpy_module, report_text)
            print(report_text)

            props.diag_last_action = (
                f"Cenário '{props.preset_name}' construído em {val.execution_time_ms:.0f} ms "
                f"(Estrada={'Ativa' if props.enable_road else 'Off'}, {val.after_base_vertices:,} verts)."
            )
            self.report(
                {"INFO"},
                f"Cenário CP-03 gerado com sucesso em {val.execution_time_ms:.0f}ms! "
                f"Terreno: {val.terrain_object_name}",
            )
            return {"FINISHED"}

    class PROCENV_OT_randomize_seed(bpy_module.types.Operator):
        bl_idname = "proc_env.randomize_seed"
        bl_label = "Novo Seed Aleatório"
        bl_description = "Gera um novo Seed (estilo Minecraft) e atualiza a formação do terreno"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any):
            props = context.scene.proc_env_settings
            props.seed = random.randint(100000, 999999)
            self.report({"INFO"}, f"Novo Seed aplicado: {props.seed}")
            return {"FINISHED"}

    class PROCENV_OT_randomize_road(bpy_module.types.Operator):
        bl_idname = "proc_env.randomize_road"
        bl_label = "Novo Traçado de Estrada Aleatório"
        bl_description = "Gera um novo ângulo, posição e curvatura para a estrada sobre o terreno atual"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any):
            props = context.scene.proc_env_settings
            props.enable_road = True
            props.road_direction_deg = round(random.uniform(-75.0, 75.0), 1)
            props.road_offset_m = round(random.uniform(-80.0, 80.0), 1)
            props.road_meander_amplitude = round(random.uniform(55.0, 145.0), 1)
            props.road_meander_scale = round(random.uniform(8.0, 22.0), 1)
            self.report(
                {"INFO"},
                f"Nova estrada gerada (Direção={props.road_direction_deg}°, Curvas={props.road_meander_amplitude}m)!",
            )
            return {"FINISHED"}

    class PROCENV_OT_create_road_curve(bpy_module.types.Operator):
        bl_idname = "proc_env.create_road_curve"
        bl_label = "Criar / Selecionar Guia de Estrada 3D"
        bl_description = "Cria uma curva Bezier 3D (PROC_ENV_Road_Curve) no cenário para referência/edição do caminho"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any):
            engine = ProceduralEnvironmentEngine(bpy_module)
            cols = engine.state_manager.ensure_collection_hierarchy(scene=context.scene)
            raw, _ = engine.analyze_only(scene=context.scene)
            t_obj = None
            if raw.primary_terrain:
                t_obj = context.scene.objects.get(raw.primary_terrain.name)
            curve_obj = engine.terrain_gen.ensure_road_curve_object(
                terrain_obj=t_obj,
                scene=context.scene,
                collections=cols,
            )
            if curve_obj is not None:
                try:
                    context.view_layer.objects.active = curve_obj
                    curve_obj.select_set(True)
                except Exception:
                    pass
                self.report({"INFO"}, f"Curva '{curve_obj.name}' pronta e selecionada na Viewport!")
            return {"FINISHED"}

    class PROCENV_OT_populate_objects(bpy_module.types.Operator):
        bl_idname = "proc_env.populate_objects"
        bl_label = "Regenerar Casas, Props, Rochas & Decals"
        bl_description = "Gera ou atualiza apenas os objetos 3D procedurais (Casas, Postes, Rochas, Árvores e Decals) sobre o terreno"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any):
            props = context.scene.proc_env_settings
            params = _build_params_from_props(props)
            engine = ProceduralEnvironmentEngine(bpy_module)
            raw, _ = engine.analyze_only(scene=context.scene)
            if raw.primary_terrain is None:
                self.report({"WARNING"}, "Gere ou selecione primeiro um terreno!")
                return {"CANCELLED"}
            t_obj = context.scene.objects.get(raw.primary_terrain.name)
            cols = engine.state_manager.ensure_collection_hierarchy(scene=context.scene)
            env_res = engine.environment_gen.populate_scenario(
                terrain_obj=t_obj,
                params=params,
                scene=context.scene,
                collections=cols,
            )
            props.diag_last_action = (
                f"Objetos regenerados: {env_res['total_spawned']} total "
                f"({env_res['houses_spawned']} Casas, {env_res['props_spawned']} Props, "
                f"{env_res['rocks_spawned']} Rochas, {env_res['vegetation_spawned']} Veg, "
                f"{env_res['decals_spawned']} Decals)."
            )
            self.report({"INFO"}, props.diag_last_action)
            return {"FINISHED"}

    class PROCENV_OT_clear_objects(bpy_module.types.Operator):
        bl_idname = "proc_env.clear_objects"
        bl_label = "Limpar Objetos do Cenário"
        bl_description = "Remove todas as Casas, Props, Rochas, Vegetação e Decals gerados pelo PROC_ENV sem tocar no terreno"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any):
            props = context.scene.proc_env_settings
            engine = ProceduralEnvironmentEngine(bpy_module)
            removed = engine.environment_gen.clear_scenario_objects(scene=context.scene)
            props.diag_last_action = f"{removed} objetos de cenário removidos."
            self.report({"INFO"}, props.diag_last_action)
            return {"FINISHED"}

    class PROCENV_OT_rollback_snapshot(bpy_module.types.Operator):
        bl_idname = "proc_env.rollback_snapshot"
        bl_label = "Reverter para Original (Snapshot)"
        bl_description = (
            "Remove o modifier PROC_ENV_Terrain e restaura os modifiers e material original "
            "guardados antes da geração"
        )
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any):
            props = context.scene.proc_env_settings
            engine = ProceduralEnvironmentEngine(bpy_module)
            res = engine.rollback_to_snapshot(scene=context.scene)
            if not res.get("restored"):
                self.report({"WARNING"}, str(res.get("reason", "Nada para reverter.")))
                return {"CANCELLED"}

            raw, interp = engine.analyze_only(scene=context.scene)
            _populate_ui_diagnostics(props, raw, interp, None)
            props.diag_last_action = (
                f"Revertido com sucesso: '{res.get('terrain_name')}' restaurado para '{res.get('restored_material')}'."
            )
            self.report({"INFO"}, props.diag_last_action)
            return {"FINISHED"}

    return (
        PROCENV_OT_analyze_scene,
        PROCENV_OT_generate_desert,
        PROCENV_OT_randomize_seed,
        PROCENV_OT_randomize_road,
        PROCENV_OT_create_road_curve,
        PROCENV_OT_populate_objects,
        PROCENV_OT_clear_objects,
        PROCENV_OT_rollback_snapshot,
    )
