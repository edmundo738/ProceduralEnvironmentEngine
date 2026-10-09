"""
N-Panel UI Panels (`View3D > Sidebar > ProcEnv`) for Blender 5.2+ LTS (CP-03).
Includes:
  - Multi-Biome & Deformation Presets (Desert, Green Mossy Mountains, Lush Valley, Savanna Explanada, Fantasy)
  - Universal Road & Path Creator (contours, flattens, carves, and paints roads + Y-branches)
  - Multi-Biome Surface Controls (Grass, Moss, Slope Rock, Sand, Road & 4K PBR Anti-Stretching)
"""

from typing import Any
from ..config import OperationMode, SNAPSHOT_PROP_KEY


def get_panel_classes(bpy_module: Any):
    class PROCENV_PT_main_panel(bpy_module.types.Panel):
        bl_label = "Procedural Environment Engine V0.3"
        bl_idname = "PROCENV_PT_main_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "ProcEnv"

        def draw(self, context: Any):
            layout = self.layout
            scene = context.scene
            props = scene.proc_env_settings

            box_mode = layout.box()
            box_mode.label(text="Modo de Interação:", icon="SETTINGS")
            box_mode.prop(props, "operation_mode", expand=True)

            box_quick = layout.box()
            box_quick.label(text="Bioma, Deformação & Seed:", icon="WORLD")
            box_quick.prop(props, "preset_name", text="Cenário")
            box_quick.prop(props, "dune_morphology", text="Deformação")
            box_quick.prop(props, "performance_profile", text="Performance")

            row_seed = box_quick.row(align=True)
            row_seed.prop(props, "seed", text="Seed")
            row_seed.operator("proc_env.randomize_seed", text="", icon="FILE_REFRESH")

            row_road_toggle = box_quick.row(align=True)
            row_road_toggle.prop(props, "enable_road", text="Ativar Estrada / Caminho")
            row_road_toggle.operator("proc_env.randomize_road", text="", icon="FORCE_CURVE")
            box_quick.prop(props, "enable_scenario_objects", text="Gerar Casas, Props, Rochas, Árvores & Decals")

            if props.operation_mode in (OperationMode.GUIDED, OperationMode.MANUAL):
                box_quick.separator()
                box_quick.label(text="Política sobre Trabalho Existente:", icon="MODIFIER")
                box_quick.prop(props, "conflict_strategy", text="")

            col_act = layout.column(align=True)
            col_act.scale_y = 1.6
            col_act.operator(
                "proc_env.generate_desert",
                text="GERAR CENÁRIO COMPLETO (CP-04)",
                icon="SHADING_RENDERED",
            )

            row_sub = layout.row(align=True)
            row_sub.operator("proc_env.analyze_scene", text="Analisar Cena", icon="VIEWZOOM")
            has_snap = False
            try:
                has_snap = SNAPSHOT_PROP_KEY in scene
            except Exception:
                has_snap = False
            sub_rev = row_sub.row(align=True)
            sub_rev.enabled = has_snap
            sub_rev.operator("proc_env.rollback_snapshot", text="Reverter Original", icon="LOOP_BACK")

            layout.prop(props, "live_update", text="Atualização em Tempo Real nos Sliders")

    class PROCENV_PT_diagnostic_panel(bpy_module.types.Panel):
        bl_label = "1. Diagnóstico da Cena (Analyzer)"
        bl_idname = "PROCENV_PT_diagnostic_panel"
        bl_parent_id = "PROCENV_PT_main_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "ProcEnv"

        def draw(self, context: Any):
            layout = self.layout
            props = context.scene.proc_env_settings

            box = layout.box()
            col = box.column(align=True)
            col.label(text=f"Terreno: {props.diag_terrain_summary}", icon="MESH_GRID")
            col.label(text=f"Geometria: {props.diag_geometry_status}", icon="VERTEXSEL")
            col.label(text=f"Mapas PBR: {props.diag_pbr_status}", icon="TEXTURE")
            col.label(text=f"Mapeamento: {props.diag_stretch_status}", icon="UV")
            col.separator()
            col.label(text=f"Estado: {props.diag_last_action}", icon="INFO")

    class PROCENV_PT_road_panel(bpy_module.types.Panel):
        bl_label = "2. Criador de Estradas & Caminhos"
        bl_idname = "PROCENV_PT_road_panel"
        bl_parent_id = "PROCENV_PT_main_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "ProcEnv"

        def draw(self, context: Any):
            layout = self.layout
            props = context.scene.proc_env_settings

            row_top = layout.row(align=True)
            row_top.prop(props, "enable_road", text="Ativar Estrada / Caminho")
            row_top.operator("proc_env.randomize_road", text="Nova Estrada Aleatória", icon="FILE_REFRESH")

            col_main = layout.column()
            col_main.enabled = props.enable_road

            # A. Alisamento, Largura & Contorno do Terreno
            box_carve = col_main.box()
            box_carve.label(text="Alisamento, Largura & Contorno:", icon="MOD_SHRINKWRAP")
            c1 = box_carve.column(align=True)
            c1.prop(props, "road_width_m")
            c1.prop(props, "road_shoulder_m")
            c1.prop(props, "road_flatten_strength", slider=True)
            c1.prop(props, "road_elevation_follow", slider=True)
            c1.prop(props, "road_carve_depth_m")
            c1.prop(props, "road_berm_height_m")

            # B. Traçado, Curvas Sinuosas & Bifurcação
            box_path = col_main.box()
            box_path.label(text="Traçado, Curvas & Bifurcação:", icon="FORCE_CURVE")
            c2 = box_path.column(align=True)
            c2.prop(props, "road_direction_deg")
            c2.prop(props, "road_offset_m")
            c2.prop(props, "road_meander_amplitude")
            c2.prop(props, "road_meander_scale")
            c2.prop(props, "road_secondary_branch")
            c2.separator()
            c2.operator("proc_env.create_road_curve", text="Criar Guia Curva 3D no Cenário", icon="CURVE_BEZCURVE")

    class PROCENV_PT_environment_objects_panel(bpy_module.types.Panel):
        bl_label = "3. Casas Procedurais, Props, Rochas & Decals (Layer 5)"
        bl_idname = "PROCENV_PT_environment_objects_panel"
        bl_parent_id = "PROCENV_PT_main_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "ProcEnv"

        def draw(self, context: Any):
            layout = self.layout
            props = context.scene.proc_env_settings

            layout.prop(props, "enable_scenario_objects", text="Ativar Objetos 3D do Cenário")
            row_btns = layout.row(align=True)
            row_btns.operator("proc_env.populate_objects", text="Regenerar Objetos 3D", icon="HOME")
            row_btns.operator("proc_env.clear_objects", text="Limpar", icon="TRASH")

            col = layout.column()
            col.enabled = props.enable_scenario_objects

            # A. Casas & Edifícios Procedurais
            box_h = col.box()
            box_h.label(text="Casas & Edifícios Procedurais:", icon="HOME")
            ch = box_h.column(align=True)
            ch.prop(props, "house_style", text="Estilo")
            ch.prop(props, "house_count")
            ch.prop(props, "house_scale")
            ch.prop(props, "house_clustering", slider=True)

            # B. Props de Beira de Estrada & Decals
            box_p = col.box()
            box_p.label(text="Props de Estrada & Decals de Chão:", icon="LIGHT_SUN")
            cp = box_p.column(align=True)
            cp.prop(props, "prop_count")
            cp.prop(props, "prop_scale")
            cp.separator()
            cp.prop(props, "decal_count")
            cp.prop(props, "decal_scale")

            # C. Rochas 3D & Vegetação por Bioma
            box_rv = col.box()
            box_rv.label(text="Rochas 3D & Vegetação do Bioma:", icon="OUTLINER_OB_FORCE_FIELD")
            crv = box_rv.column(align=True)
            crv.prop(props, "rock_count")
            crv.prop(props, "rock_scale")
            crv.separator()
            crv.prop(props, "vegetation_count")
            crv.prop(props, "vegetation_scale")

    class PROCENV_PT_terrain_panel(bpy_module.types.Panel):
        bl_label = "4. Terreno, Deformações & Teia (Layer 3)"
        bl_idname = "PROCENV_PT_terrain_panel"
        bl_parent_id = "PROCENV_PT_main_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "ProcEnv"

        def draw(self, context: Any):
            layout = self.layout
            props = context.scene.proc_env_settings

            box_scale = layout.box()
            box_scale.label(text="Escala Livre, Densidade & Altura:", icon="FULLSCREEN_ENTER")
            col_sc = box_scale.column(align=True)
            col_sc.prop(props, "dune_height")
            col_sc.prop(props, "dune_scale")
            col_sc.prop(props, "dune_density")
            col_sc.prop(props, "plateau_flattening", slider=True)

            box_wind = layout.box()
            box_wind.label(text="Direção, Sinuosidade & Erosão:", icon="FORCE_WIND")
            col_w = box_wind.column(align=True)
            col_w.prop(props, "wind_direction_deg")
            col_w.prop(props, "dune_variation")
            col_w.prop(props, "wind_turbulence")

            box_branch = layout.box()
            box_branch.label(text="Ramificação (Teia / Rio / Cristas):", icon="OUTLINER_OB_CURVES")
            col_br = box_branch.column(align=True)
            col_br.prop(props, "dune_branching")
            col_br.prop(props, "branch_anisotropy")
            col_br.prop(props, "crest_roundness", slider=True)
            col_br.prop(props, "dune_sharpness")

            box_smooth = layout.box()
            box_smooth.label(text="Suavização da Malha (Anti-Escada / Quadrados):", icon="MOD_SMOOTH")
            col_sm = box_smooth.column(align=True)
            col_sm.prop(props, "mesh_smooth_iterations")
            col_sm.prop(props, "mesh_smooth_factor", slider=True)
            col_sm.prop(props, "shade_smooth")

            box_macro = layout.box()
            box_macro.label(text="Bacias Macro, Relevo Médio & Base:", icon="RNDCURVE")
            col_m = box_macro.column(align=True)
            col_m.prop(props, "macro_basin_height")
            col_m.prop(props, "macro_basin_scale")
            col_m.prop(props, "medium_undulation_height")
            col_m.prop(props, "existing_relief_keep")

    class PROCENV_PT_surface_panel(bpy_module.types.Panel):
        bl_label = "5. Superfície: Relva, Musgo, Rocha, Areia & PBR"
        bl_idname = "PROCENV_PT_surface_panel"
        bl_parent_id = "PROCENV_PT_main_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "ProcEnv"

        def draw(self, context: Any):
            layout = self.layout
            props = context.scene.proc_env_settings

            box_eco = layout.box()
            box_eco.label(text="Rocha nas Encostas & Cores do Bioma:", icon="SHADING_TEXTURE")
            col_e = box_eco.column(align=True)
            col_e.prop(props, "rock_slope_threshold", slider=True)
            col_e.prop(props, "rock_blend_sharpness", slider=True)
            col_e.prop(props, "sand_color_variation", slider=True)
            col_e.separator()
            col_e.prop(props, "color_sand_primary", text="Cor Principal (Relva/Areia)")
            col_e.prop(props, "color_sand_crest", text="Cor Topo / Sol")
            col_e.prop(props, "color_sand_trough", text="Cor Vale / Terra")
            col_e.prop(props, "color_moss", text="Cor Musgo / Húmido")
            col_e.prop(props, "color_rock", text="Cor Pedra / Rocha")
            col_e.prop(props, "color_road", text="Cor da Estrada")

            box_pbr = layout.box()
            box_pbr.label(text="Integração PBR 4K & Anti-Estiramento:", icon="NODE_MATERIAL")
            box_pbr.prop(props, "use_pbr_maps")
            col_p = box_pbr.column(align=True)
            col_p.enabled = props.use_pbr_maps
            col_p.prop(props, "mapping_method", text="Coordenadas")
            col_p.prop(props, "pbr_tile_size_meters")
            col_p.prop(props, "pbr_blend_factor", slider=True)
            col_p.prop(props, "anti_tiling_strength")
            col_p.prop(props, "pbr_normal_strength")

            box_sand = layout.box()
            box_sand.label(text="Micro-Detalhe, Ondas & Rugosidade:", icon="MATERIAL")
            col_s = box_sand.column(align=True)
            col_s.prop(props, "sand_detail", slider=True)
            col_s.prop(props, "sand_ripple_scale")
            col_s.prop(props, "sand_bump_strength")
            col_s.prop(props, "sand_roughness_base", slider=True)

    return (
        PROCENV_PT_main_panel,
        PROCENV_PT_diagnostic_panel,
        PROCENV_PT_road_panel,
        PROCENV_PT_environment_objects_panel,
        PROCENV_PT_terrain_panel,
        PROCENV_PT_surface_panel,
    )
