"""
Blender PropertyGroup for Procedural Environment Engine V0.3 (Checkpoint CP-03).
Includes Multi-Biome Presets (Desert, Green Mossy Mountains, Lush Valley, Savanna Explanada,
Fantasy Game Landscapes) and the Universal Road & Path Carve System.
"""

from typing import Any
from ..config import (
    TerrainEngineParams,
    ConflictStrategy,
    OperationMode,
    PerformanceProfile,
    MappingMethod,
    DuneMorphology,
    EnvironmentBiome,
    RoadMode,
    RoadStyle,
)
from ..presets.desert_presets import apply_preset_to_params
from ..core.engine import ProceduralEnvironmentEngine


def _build_params_from_props(props: Any) -> TerrainEngineParams:
    return TerrainEngineParams(
        environment_type=props.environment_type,
        preset_name=props.preset_name,
        operation_mode=props.operation_mode,
        conflict_strategy=props.conflict_strategy,
        performance_profile=props.performance_profile,
        seed=props.seed,
        world_size_x=props.world_size_x,
        world_size_y=props.world_size_y,
        dune_morphology=props.dune_morphology,
        existing_relief_keep=props.existing_relief_keep,
        dune_scale=props.dune_scale,
        dune_density=props.dune_density,
        dune_height=props.dune_height,
        dune_variation=props.dune_variation,
        wind_turbulence=props.wind_turbulence,
        wind_direction_deg=props.wind_direction_deg,
        dune_branching=props.dune_branching,
        branch_anisotropy=props.branch_anisotropy,
        crest_roundness=props.crest_roundness,
        dune_sharpness=props.dune_sharpness,
        plateau_flattening=props.plateau_flattening,
        terrace_steps=props.terrace_steps,
        macro_basin_height=props.macro_basin_height,
        macro_basin_scale=props.macro_basin_scale,
        medium_undulation_height=props.medium_undulation_height,
        mesh_smooth_iterations=props.mesh_smooth_iterations,
        mesh_smooth_factor=props.mesh_smooth_factor,
        shade_smooth=props.shade_smooth,
        # Universal Road & Path Creator
        enable_road=props.enable_road,
        road_mode=props.road_mode,
        road_style=props.road_style,
        road_width_m=props.road_width_m,
        road_shoulder_m=props.road_shoulder_m,
        road_flatten_strength=props.road_flatten_strength,
        road_elevation_follow=props.road_elevation_follow,
        road_carve_depth_m=props.road_carve_depth_m,
        road_berm_height_m=props.road_berm_height_m,
        road_direction_deg=props.road_direction_deg,
        road_offset_m=props.road_offset_m,
        road_meander_amplitude=props.road_meander_amplitude,
        road_meander_scale=props.road_meander_scale,
        road_secondary_branch=props.road_secondary_branch,
        # Layer 4 Surface & Ecology
        sand_color_variation=props.sand_color_variation,
        sand_detail=props.sand_detail,
        sand_ripple_scale=props.sand_ripple_scale,
        sand_bump_strength=props.sand_bump_strength,
        sand_roughness_base=props.sand_roughness_base,
        rock_slope_threshold=props.rock_slope_threshold,
        rock_blend_sharpness=props.rock_blend_sharpness,
        moss_moisture_amount=props.moss_moisture_amount,
        use_pbr_maps=props.use_pbr_maps,
        mapping_method=props.mapping_method,
        pbr_tile_size_meters=props.pbr_tile_size_meters,
        pbr_blend_factor=props.pbr_blend_factor,
        pbr_normal_strength=props.pbr_normal_strength,
        anti_tiling_strength=props.anti_tiling_strength,
        color_sand_primary=tuple(props.color_sand_primary),
        color_sand_crest=tuple(props.color_sand_crest),
        color_sand_trough=tuple(props.color_sand_trough),
        color_rock=tuple(props.color_rock),
        color_moss=tuple(props.color_moss),
        color_road=tuple(props.color_road),
        # Layer 5 Complete Scenario Objects
        enable_scenario_objects=props.enable_scenario_objects,
        house_style=props.house_style,
        house_count=props.house_count,
        house_scale=props.house_scale,
        house_clustering=props.house_clustering,
        prop_count=props.prop_count,
        prop_scale=props.prop_scale,
        rock_count=props.rock_count,
        rock_scale=props.rock_scale,
        vegetation_count=props.vegetation_count,
        vegetation_scale=props.vegetation_scale,
        decal_count=props.decal_count,
        decal_scale=props.decal_scale,
    )


def _on_live_param_update(self: Any, context: Any) -> None:
    """Triggered when a user drags any parameter slider in the N-Panel."""
    if not getattr(self, "live_update", True) or getattr(self, "_is_applying_preset", False):
        return
    try:
        engine = ProceduralEnvironmentEngine()
        params = _build_params_from_props(self)
        engine.live_update_parameters(params=params, scene=context.scene)
    except Exception:
        pass


def _on_preset_change(self: Any, context: Any) -> None:
    """Applies the chosen multi-biome preset values into the UI properties and triggers a live update."""
    self._is_applying_preset = True
    try:
        params = _build_params_from_props(self)
        apply_preset_to_params(params, self.preset_name)
        self.environment_type = params.environment_type
        self.dune_morphology = params.dune_morphology
        self.existing_relief_keep = params.existing_relief_keep
        self.dune_scale = params.dune_scale
        self.dune_density = params.dune_density
        self.dune_height = params.dune_height
        self.dune_variation = params.dune_variation
        self.wind_turbulence = params.wind_turbulence
        self.wind_direction_deg = params.wind_direction_deg
        self.dune_branching = params.dune_branching
        self.branch_anisotropy = params.branch_anisotropy
        self.crest_roundness = params.crest_roundness
        self.dune_sharpness = params.dune_sharpness
        self.plateau_flattening = params.plateau_flattening
        self.terrace_steps = params.terrace_steps
        self.macro_basin_height = params.macro_basin_height
        self.macro_basin_scale = params.macro_basin_scale
        self.medium_undulation_height = params.medium_undulation_height
        self.mesh_smooth_iterations = params.mesh_smooth_iterations
        self.mesh_smooth_factor = params.mesh_smooth_factor
        self.enable_road = params.enable_road
        self.road_style = params.road_style
        self.road_width_m = params.road_width_m
        self.road_shoulder_m = params.road_shoulder_m
        self.road_flatten_strength = params.road_flatten_strength
        self.road_elevation_follow = params.road_elevation_follow
        self.road_carve_depth_m = params.road_carve_depth_m
        self.road_berm_height_m = params.road_berm_height_m
        self.road_meander_amplitude = params.road_meander_amplitude
        self.road_meander_scale = params.road_meander_scale
        self.road_secondary_branch = params.road_secondary_branch
        self.sand_color_variation = params.sand_color_variation
        self.sand_detail = params.sand_detail
        self.sand_ripple_scale = params.sand_ripple_scale
        self.sand_bump_strength = params.sand_bump_strength
        self.rock_slope_threshold = params.rock_slope_threshold
        self.moss_moisture_amount = params.moss_moisture_amount
        self.pbr_tile_size_meters = params.pbr_tile_size_meters
        self.pbr_blend_factor = params.pbr_blend_factor
        self.color_sand_primary = params.color_sand_primary
        self.color_sand_crest = params.color_sand_crest
        self.color_sand_trough = params.color_sand_trough
        self.color_rock = params.color_rock
        self.color_moss = params.color_moss
        self.color_road = params.color_road
    finally:
        self._is_applying_preset = False
    _on_live_param_update(self, context)


def get_properties_class(bpy_module: Any):
    from bpy.props import (
        EnumProperty,
        IntProperty,
        FloatProperty,
        FloatVectorProperty,
        BoolProperty,
        StringProperty,
    )

    class ProcEnvSceneProperties(bpy_module.types.PropertyGroup):
        _is_applying_preset: bool = False

        operation_mode: EnumProperty(
            name="Modo de Operação",
            description="Nível de intervenção humana (Auto / Guiado / Manual)",
            items=[
                (OperationMode.AUTO, "⚡ AUTO (Preguiçoso)", "1-Clique: analisa a cena, otimiza e gera tudo automaticamente"),
                (OperationMode.GUIDED, "🧭 GUIDED (Guiado)", "Escolhe o bioma, estrada e política antes de gerar"),
                (OperationMode.MANUAL, "🎛️ MANUAL (Avançado)", "Controlo total sobre terreno, estradas, rochas, musgo e PBR"),
            ],
            default=OperationMode.AUTO,
        )

        preset_name: EnumProperty(
            name="Cenário / Bioma",
            description="Escolhe o tipo de ambiente, deformação e estrada",
            items=[
                (
                    "cinematic_branching_erg",
                    "🏜️ Deserto em Teia / Rio + Estrada",
                    "Dunas ramificadas em Y cortadas por uma estrada de caravana alisada",
                ),
                (
                    "green_mossy_mountains",
                    "🏔️ Montanhas Verdes (Musgo, Pedras, Relva & Estrada)",
                    "Cordilheiras verdes com penhascos de rocha nas encostas, musgo húmido e estrada de montanha",
                ),
                (
                    "lush_moss_valley",
                    "🌿 Vale Verdejante (Relva, Musgo, Pedras & Caminho)",
                    "Colinas suaves de relva e musgo com afloramentos rochosos e trilho sinuoso",
                ),
                (
                    "savanna_plains_kopjes",
                    "🦁 Savana & Explanadas (Terra Vermelha, Relva & Planaltos)",
                    "Grandes explanadas abertas intercaladas com planaltos/mesas rochosas e estrada de terra vermelha",
                ),
                (
                    "fantasy_terraced_peaks",
                    "✨ Paisagem Fantasiosa para Jogos (Terraços, Musgo & Estrada)",
                    "Cenário estilizado para jogos: terraços orgânicos, musgo esmeralda, rocha azulada e caminho real",
                ),
                (
                    "dendritic_river_dunes",
                    "🌳 Rede de Dunas Ramificadas (Árvore / Estrela / Rio)",
                    "Foco intenso em dunas que bifurcam e criam braços secundários",
                ),
                (
                    "flowing_sahara_waves",
                    "🌊 Ondas Sinuosas do Saara (Suaves & Contínuas)",
                    "Cordões longos e sinuosos moldados pelo vento, sem paredes retas",
                ),
                (
                    "namib_mega_corridors",
                    "🏜️ Megadunas & Corredores do Namibe (Com Estrada)",
                    "Dunas colossais separadas por largos vales interdunares percorridos por uma estrada",
                ),
            ],
            default="cinematic_branching_erg",
            update=_on_preset_change,
        )

        environment_type: EnumProperty(
            name="Bioma Ecológico",
            items=[
                (EnvironmentBiome.DESERT, "🏜️ Deserto", "Areia + PBR 4K + Rocha"),
                (EnvironmentBiome.MOUNTAIN_ALPINE, "🏔️ Montanha Verde", "Relva, Musgo & Penhascos de Rocha"),
                (EnvironmentBiome.LUSH_VALLEY, "🌿 Vale Verdejante", "Relva Densa, Musgo & Pedras"),
                (EnvironmentBiome.SAVANNA_PLAINS, "🦁 Savana & Explanada", "Capim Dourado, Terra Vermelha & Mesas"),
                (EnvironmentBiome.FANTASY_LANDSCAPE, "✨ Fantasia / Jogo", "Musgo Esmeralda, Terraços & Rocha Mística"),
            ],
            default=EnvironmentBiome.DESERT,
            update=_on_live_param_update,
        )

        dune_morphology: EnumProperty(
            name="Deformação do Terreno",
            description="Padrão estrutural das formações do terreno",
            items=[
                (DuneMorphology.BRANCHING_ERG, "🌐 Teia Ramificada + Ondas", "Bifurcações em Y com ondas contínuas"),
                (DuneMorphology.ALPINE_MOUNTAINS, "🏔️ Montanhas & Cristas Esculpidas", "Cadeias montanhosas e vales profundos"),
                (DuneMorphology.SAVANNA_EXPLANADA, "🦁 Explanadas & Planaltos (Mesas)", "Planícies abertas com platôs de topo achatado"),
                (DuneMorphology.FANTASY_TERRACES, "✨ Terraços & Platôs Fantasiosos", "Formações estilizadas para jogos"),
                (DuneMorphology.DENDRITIC_WEB, "🌳 Rede Dendrítica (Árvore / Rio)", "Máxima ramificação Voronoi"),
                (DuneMorphology.SINUOUS_WAVES, "🌊 Ondas Sinuosas Suaves", "Colinas/dunas longas e suaves"),
                (DuneMorphology.MEGA_CORRIDORS, "🏜️ Megadunas & Corredores", "Grandes cordilheiras e vales largos"),
            ],
            default=DuneMorphology.BRANCHING_ERG,
            update=_on_live_param_update,
        )

        conflict_strategy: EnumProperty(
            name="Ação sobre o Existente",
            items=[
                (ConflictStrategy.ENHANCE_OPTIMIZE, "✨ Aprimorar & Otimizar (Recomendado)", "Reutiliza terreno e PBR, protege contra Subdiv excessivo"),
                (ConflictStrategy.KEEP_AND_STACK, "➕ Manter Tudo & Empilhar", "Mantém todos os modifiers existentes"),
                (ConflictStrategy.CLEAN_REPLACE, "🧹 Substituição Limpa (Reversível)", "Silencia modifiers antigos com snapshot"),
                (ConflictStrategy.CREATE_NEW, "🆕 Criar Novo Terreno do Zero", "Gera uma nova malha na coleção PROC_ENV_TERRAIN"),
            ],
            default=ConflictStrategy.ENHANCE_OPTIMIZE,
        )

        performance_profile: EnumProperty(
            name="Perfil de Hardware",
            items=[
                (PerformanceProfile.LOW, "Leve (Low)", "Máxima velocidade"),
                (PerformanceProfile.BALANCED, "Equilibrado (Balanced)", "Otimizado para 1.33M vértices"),
                (PerformanceProfile.HIGH, "Alto (High)", "Máximo detalhe sem Subdiv extra"),
            ],
            default=PerformanceProfile.BALANCED,
        )

        seed: IntProperty(
            name="Seed do Mundo",
            default=847293,
            min=-9999999,
            max=9999999,
            update=_on_live_param_update,
        )

        live_update: BoolProperty(
            name="Atualização em Tempo Real",
            default=True,
        )

        # ------------------------------------------------------------------
        # LAYER 3 — TERRAIN DEFORMATION, BRANCHING & PLATEAUS
        # ------------------------------------------------------------------
        existing_relief_keep: FloatProperty(
            name="Preservar Relevo Antigo",
            default=0.0,
            min=0.0,
            max=2.0,
            soft_min=0.0,
            soft_max=1.0,
            update=_on_live_param_update,
        )

        dune_height: FloatProperty(
            name="Altura Principal (m)",
            description="Altura das dunas, montanhas ou planaltos em metros (até 1000m)",
            default=26.0,
            min=-500.0,
            max=1000.0,
            soft_min=0.0,
            soft_max=200.0,
            update=_on_live_param_update,
        )

        dune_scale: FloatProperty(
            name="Escala / Tamanho Geral",
            description="Tamanho espacial das formações (0.05 até 500.0)",
            default=12.0,
            min=0.05,
            max=500.0,
            soft_min=0.5,
            soft_max=100.0,
            update=_on_live_param_update,
        )

        dune_density: FloatProperty(
            name="Densidade / Frequência",
            description="Quantidade de cristas, montanhas ou dunas no terreno (0.05 até 100.0)",
            default=1.25,
            min=0.05,
            max=100.0,
            soft_min=0.1,
            soft_max=15.0,
            update=_on_live_param_update,
        )

        dune_variation: FloatProperty(
            name="Sinuosidade / Curvatura",
            description="Curvatura orgânica das cadeias (0.0 a 50.0)",
            default=2.4,
            min=0.0,
            max=50.0,
            soft_min=0.0,
            soft_max=15.0,
            update=_on_live_param_update,
        )

        wind_turbulence: FloatProperty(
            name="Turbulência / Erosão",
            description="Variação e recorte secundário das encostas (0.0 a 50.0)",
            default=1.6,
            min=0.0,
            max=50.0,
            soft_min=0.0,
            soft_max=15.0,
            update=_on_live_param_update,
        )

        wind_direction_deg: FloatProperty(
            name="Direção Principal (°)",
            default=32.0,
            min=-360.0,
            max=360.0,
            update=_on_live_param_update,
        )

        dune_branching: FloatProperty(
            name="Ramificação (Teia / Rio / Cristas)",
            description="Força das bifurcações em Y e braços secundários (0.0 a 10.0)",
            default=0.80,
            min=0.0,
            max=10.0,
            soft_min=0.0,
            soft_max=3.5,
            update=_on_live_param_update,
        )

        branch_anisotropy: FloatProperty(
            name="Alongamento Direcional",
            default=3.2,
            min=0.1,
            max=30.0,
            soft_min=0.5,
            soft_max=12.0,
            update=_on_live_param_update,
        )

        crest_roundness: FloatProperty(
            name="Suavidade das Cristas",
            default=0.44,
            min=0.02,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        dune_sharpness: FloatProperty(
            name="Inclinação das Encostas",
            default=1.35,
            min=0.5,
            max=3.0,
            update=_on_live_param_update,
        )

        plateau_flattening: FloatProperty(
            name="Achatamento Explanada / Planalto",
            description="Cria planícies abertas (explanadas) e achata o topo das elevações (mesas/savana)",
            default=0.0,
            min=0.0,
            max=0.95,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        terrace_steps: FloatProperty(
            name="Terraços Fantasiosos",
            default=0.0,
            min=0.0,
            max=30.0,
            update=_on_live_param_update,
        )

        macro_basin_height: FloatProperty(
            name="Altura das Bacias Macro (m)",
            default=14.0,
            min=-500.0,
            max=500.0,
            update=_on_live_param_update,
        )

        macro_basin_scale: FloatProperty(
            name="Escala das Bacias Macro",
            default=16.0,
            min=0.1,
            max=500.0,
            update=_on_live_param_update,
        )

        medium_undulation_height: FloatProperty(
            name="Relevo Médio Secundário (m)",
            default=3.2,
            min=0.0,
            max=200.0,
            update=_on_live_param_update,
        )

        mesh_smooth_iterations: IntProperty(
            name="Iterações de Suavização (Anti-Escada)",
            default=8,
            min=0,
            max=50,
            update=_on_live_param_update,
        )

        mesh_smooth_factor: FloatProperty(
            name="Força da Suavização",
            default=0.72,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        shade_smooth: BoolProperty(
            name="Shade Smooth Automático",
            default=True,
            update=_on_live_param_update,
        )

        # ------------------------------------------------------------------
        # UNIVERSAL ROAD & PATH CREATOR (CP-03)
        # ------------------------------------------------------------------
        enable_road: BoolProperty(
            name="Ativar Criador de Estrada / Caminho",
            description="Esculpe, alisa, contorna e pinta automaticamente uma estrada sobre qualquer terreno",
            default=True,
            update=_on_live_param_update,
        )

        road_mode: EnumProperty(
            name="Modo da Estrada",
            items=[
                (RoadMode.PROCEDURAL_WINDING, "🛣️ Automática Sinuosa", "Gera estrada sinuosa + bifurcação automaticamente"),
                (RoadMode.CURVE_OBJECT, "✏️ Curva 3D (PROC_ENV_Road_Curve)", "Cria/usa curva 3D editável no cenário"),
            ],
            default=RoadMode.PROCEDURAL_WINDING,
            update=_on_live_param_update,
        )

        road_style: EnumProperty(
            name="Estilo da Estrada",
            items=[
                (RoadStyle.DIRT_TRAIL, "Terra Batida / Trilho", "Caminho natural de terra compactada"),
                (RoadStyle.STONE_PAVED, "Pedra / Calçada", "Estrada de pedra para montanha ou fantasia"),
                (RoadStyle.DESERT_TRACK, "Trilho de Caravana / Areia", "Caminho alisado no deserto"),
                (RoadStyle.MOSSY_PATH, "Caminho com Musgo", "Trilho integrado em vales verdes"),
            ],
            default=RoadStyle.DESERT_TRACK,
            update=_on_live_param_update,
        )

        road_width_m: FloatProperty(
            name="Largura da Estrada (m)",
            description="Largura da faixa central alisada da estrada em metros (0.5m a 300m)",
            default=14.0,
            min=0.5,
            max=300.0,
            soft_min=2.0,
            soft_max=60.0,
            update=_on_live_param_update,
        )

        road_shoulder_m: FloatProperty(
            name="Suavização das Bordas / Talude (m)",
            description="Largura da rampa lateral onde o terreno se funde suavemente com a estrada",
            default=24.0,
            min=0.5,
            max=300.0,
            soft_min=2.0,
            soft_max=80.0,
            update=_on_live_param_update,
        )

        road_flatten_strength: FloatProperty(
            name="Força de Alisamento do Caminho",
            description="1.0 = alisa totalmente as dunas/montanhas por onde a estrada passa",
            default=0.90,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        road_elevation_follow: FloatProperty(
            name="Seguir Contorno do Relevo",
            description="1.0 = a estrada sobe e desce acompanhando as colinas; 0.0 = corta num nível plano horizontal",
            default=0.65,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        road_carve_depth_m: FloatProperty(
            name="Escavação / Aterro do Leito (m)",
            description="Negativo = escava trincheira/trilho; Positivo = cria aterro elevado",
            default=-0.4,
            min=-100.0,
            max=100.0,
            soft_min=-15.0,
            soft_max=15.0,
            update=_on_live_param_update,
        )

        road_berm_height_m: FloatProperty(
            name="Altura das Bermas Laterais (m)",
            description="Pequena elevação de terra/areia acumulada nas margens da estrada",
            default=0.8,
            min=0.0,
            max=50.0,
            soft_min=0.0,
            soft_max=5.0,
            update=_on_live_param_update,
        )

        road_direction_deg: FloatProperty(
            name="Direção da Estrada (°)",
            default=15.0,
            min=-360.0,
            max=360.0,
            update=_on_live_param_update,
        )

        road_offset_m: FloatProperty(
            name="Posição Lateral da Estrada (m)",
            description="Move a estrada para a esquerda ou direita no terreno (-500m a +500m)",
            default=0.0,
            min=-500.0,
            max=500.0,
            update=_on_live_param_update,
        )

        road_meander_amplitude: FloatProperty(
            name="Curvas / Sinuosidade da Estrada (m)",
            description="Amplitude das curvas em S que a estrada faz pelo cenário (0 a 500m)",
            default=95.0,
            min=0.0,
            max=500.0,
            soft_min=0.0,
            soft_max=250.0,
            update=_on_live_param_update,
        )

        road_meander_scale: FloatProperty(
            name="Escala das Curvas da Estrada",
            default=12.0,
            min=0.1,
            max=500.0,
            soft_min=1.0,
            soft_max=100.0,
            update=_on_live_param_update,
        )

        road_secondary_branch: BoolProperty(
            name="Criar Bifurcação / Caminho Secundário em Y",
            description="Adiciona um segundo caminho que se separa da estrada principal",
            default=True,
            update=_on_live_param_update,
        )

        world_size_x: FloatProperty(name="Largura X", default=590.0, min=10.0, max=50000.0)
        world_size_y: FloatProperty(name="Comprimento Y", default=834.0, min=10.0, max=50000.0)

        # ------------------------------------------------------------------
        # LAYER 4 — MULTI-BIOME SURFACE (SAND / GRASS / MOSS / ROCK / ROAD + PBR)
        # ------------------------------------------------------------------
        rock_slope_threshold: FloatProperty(
            name="Limite de Rocha nas Encostas",
            description="Controla onde aparece Pedra/Rocha nas subidas íngremes (maior = mais rocha exposta)",
            default=0.78,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        rock_blend_sharpness: FloatProperty(
            name="Transição Relva/Areia -> Rocha",
            default=0.12,
            min=0.01,
            max=0.5,
            update=_on_live_param_update,
        )

        moss_moisture_amount: FloatProperty(
            name="Humidade / Musgo nos Vales",
            default=0.55,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        use_pbr_maps: BoolProperty(
            name="Integrar Mapas PBR 4K",
            default=True,
        )

        mapping_method: EnumProperty(
            name="Mapeamento Anti-Estiramento",
            items=[
                (MappingMethod.METRIC_OBJECT, "📏 Métrico Real (Object/World)", "Zero estiramento em metros reais"),
                (MappingMethod.ASPECT_CORRECTED_UV, "🗺️ UV com Proporção Corrigida", "Compensa 590m x 834m"),
            ],
            default=MappingMethod.METRIC_OBJECT,
            update=_on_live_param_update,
        )

        pbr_tile_size_meters: FloatProperty(
            name="Tamanho do Tile PBR (m)",
            default=2.8,
            min=0.1,
            max=500.0,
            soft_min=0.5,
            soft_max=50.0,
            update=_on_live_param_update,
        )

        pbr_blend_factor: FloatProperty(
            name="Mistura Textura PBR vs Cores do Bioma",
            description="Baixe em Montanhas/Savana/Fantasia para destacar o Verde/Musgo mantendo o relevo 4K!",
            default=0.72,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        anti_tiling_strength: FloatProperty(
            name="Quebra de Repetição (Anti-Tiling)",
            default=0.55,
            min=0.0,
            max=10.0,
            update=_on_live_param_update,
        )

        sand_color_variation: FloatProperty(
            name="Variação Macro/Média de Cor",
            default=0.52,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        sand_detail: FloatProperty(
            name="Detalhe Micro Superficial",
            default=0.80,
            min=0.0,
            max=2.0,
            update=_on_live_param_update,
        )

        sand_ripple_scale: FloatProperty(
            name="Frequência Micro-Ondas / Relva",
            default=22.0,
            min=0.5,
            max=500.0,
            update=_on_live_param_update,
        )

        sand_bump_strength: FloatProperty(
            name="Força do Bump Procedural",
            default=0.34,
            min=0.0,
            max=2.0,
            update=_on_live_param_update,
        )

        pbr_normal_strength: FloatProperty(
            name="Força do Normal Map 4K",
            default=0.85,
            min=0.0,
            max=5.0,
            update=_on_live_param_update,
        )

        sand_roughness_base: FloatProperty(
            name="Roughness Base",
            default=0.86,
            min=0.1,
            max=1.0,
            subtype="FACTOR",
            update=_on_live_param_update,
        )

        # Customizable Biome Colors (Linear RGBA)
        color_sand_primary: FloatVectorProperty(
            name="Cor Principal (Areia / Relva)",
            subtype="COLOR",
            size=4,
            min=0.0,
            max=1.0,
            default=(0.72, 0.34, 0.18, 1.0),
            update=_on_live_param_update,
        )
        color_sand_crest: FloatVectorProperty(
            name="Cor Topo / Sol (Crista / Relva Clara)",
            subtype="COLOR",
            size=4,
            min=0.0,
            max=1.0,
            default=(0.86, 0.48, 0.26, 1.0),
            update=_on_live_param_update,
        )
        color_sand_trough: FloatVectorProperty(
            name="Cor Vale / Terra Profunda",
            subtype="COLOR",
            size=4,
            min=0.0,
            max=1.0,
            default=(0.46, 0.19, 0.10, 1.0),
            update=_on_live_param_update,
        )
        color_moss: FloatVectorProperty(
            name="Cor Musgo / Vegetação Húmida",
            subtype="COLOR",
            size=4,
            min=0.0,
            max=1.0,
            default=(0.14, 0.32, 0.09, 1.0),
            update=_on_live_param_update,
        )
        color_rock: FloatVectorProperty(
            name="Cor Pedra / Rocha nas Encostas",
            subtype="COLOR",
            size=4,
            min=0.0,
            max=1.0,
            default=(0.22, 0.19, 0.17, 1.0),
            update=_on_live_param_update,
        )
        color_road: FloatVectorProperty(
            name="Cor da Estrada / Caminho",
            subtype="COLOR",
            size=4,
            min=0.0,
            max=1.0,
            default=(0.34, 0.25, 0.18, 1.0),
            update=_on_live_param_update,
        )

        # ------------------------------------------------------------------
        # LAYER 5 — PROCEDURAL HOUSES, PROPS, ROCKS, VEGETATION & DECALS (CP-04)
        # ------------------------------------------------------------------
        enable_scenario_objects: BoolProperty(
            name="Gerar Casas, Props, Rochas, Vegetação & Decals",
            description="Popula o cenário automaticamente com meshes procedurais (respeitando estradas e encostas)",
            default=True,
        )

        house_style: EnumProperty(
            name="Estilo Arquitetónico das Casas",
            items=[
                ("AUTO_BIOME", "🏠 Automático pelo Bioma", "Adapta o estilo das casas ao bioma selecionado"),
                ("DESERT_ADOBE", "🏜️ Casas de Adobe / Oásis", "Paredes de adobe, telhado plano com vigas e torre lateral"),
                ("MEDIEVAL_MOUNTAIN", "🏔️ Chalés de Montanha / Aldeia", "Telhado de duas águas, chaminé de pedra e alpendre"),
                ("SAVANNA_VILLAGE", "🦁 Cabanas da Savana", "Paredes de barro e cobertura cónica de colmo"),
                ("FANTASY_TOWER", "✨ Torres & Templos de Fantasia", "Estruturas escalonadas com pináculo alto"),
            ],
            default="AUTO_BIOME",
        )

        house_count: IntProperty(
            name="Quantidade de Casas / Edifícios",
            default=12,
            min=0,
            max=300,
        )

        house_scale: FloatProperty(
            name="Escala das Casas",
            default=1.6,
            min=0.1,
            max=30.0,
        )

        house_clustering: FloatProperty(
            name="Agrupamento em Vila / Estrada",
            description="1.0 = agrupa as casas em aldeias junto à estrada; 0.0 = espalha pelo mapa",
            default=0.72,
            min=0.0,
            max=1.0,
            subtype="FACTOR",
        )

        prop_count: IntProperty(
            name="Props de Estrada (Postes / Pilares / Caixas)",
            default=24,
            min=0,
            max=500,
        )

        prop_scale: FloatProperty(
            name="Escala dos Props",
            default=1.4,
            min=0.1,
            max=20.0,
        )

        rock_count: IntProperty(
            name="Quantidade de Rochas / Pedras 3D",
            default=45,
            min=0,
            max=1000,
        )

        rock_scale: FloatProperty(
            name="Escala das Rochas 3D",
            default=1.8,
            min=0.1,
            max=50.0,
        )

        vegetation_count: IntProperty(
            name="Vegetação 3D (Árvores / Palmas / Acácias)",
            default=55,
            min=0,
            max=1000,
        )

        vegetation_scale: FloatProperty(
            name="Escala da Vegetação",
            default=1.6,
            min=0.1,
            max=30.0,
        )

        decal_count: IntProperty(
            name="Decals de Chão & Estrada (Lajes / Musgo)",
            default=30,
            min=0,
            max=500,
        )

        decal_scale: FloatProperty(
            name="Escala dos Decals",
            default=2.0,
            min=0.1,
            max=30.0,
        )

        # Stored Diagnostic Summary for UI Display
        diag_has_run: BoolProperty(default=False)
        diag_terrain_summary: StringProperty(default="Ainda não analisado — clique em 'Analisar Cena' ou 'Gerar Cenário'")
        diag_geometry_status: StringProperty(default="-")
        diag_pbr_status: StringProperty(default="-")
        diag_stretch_status: StringProperty(default="-")
        diag_last_action: StringProperty(default="Pronto para iniciar (CP-03 Multi-Bioma + Estradas).")

    return ProcEnvSceneProperties
