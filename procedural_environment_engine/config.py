"""
Configuration, High-Level Parameters, Biomes, Road/Path Creator Settings,
Performance Profiles, and Conflict Strategies for Procedural Environment Engine (V0.3 — CP-03).
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple


# Naming conventions for Reversibility (Section 15)
PREFIX = "PROC_ENV"
TERRAIN_MODIFIER_NAME = "PROC_ENV_Terrain"
TERRAIN_NODE_GROUP_NAME = "PROC_ENV_Dunes_GN"
SURFACE_MATERIAL_NAME = "PROC_ENV_Surface_Material"
ROAD_CURVE_OBJECT_NAME = "PROC_ENV_Road_Curve"
ROAD_MASK_ATTRIBUTE_NAME = "proc_road_mask"
BACKUP_SUFFIX = "_PROC_BACKUP"
SNAPSHOT_PROP_KEY = "proc_env_snapshot_v0"

COLLECTION_HIERARCHY = (
    "TERRAIN",
    "ROADS",
    "BUILDINGS",
    "PROPS",
    "DECALS",
    "SURFACE",
    "ROCKS",
    "VEGETATION",
    "LIGHTING",
    "CAMERA",
)


class ConflictStrategy:
    """How the engine handles existing objects, modifiers, and materials in the scene."""
    ENHANCE_OPTIMIZE = "ENHANCE_OPTIMIZE"
    KEEP_AND_STACK = "KEEP_AND_STACK"
    CLEAN_REPLACE = "CLEAN_REPLACE"
    CREATE_NEW = "CREATE_NEW"


class OperationMode:
    """User interaction modes (Section 14)."""
    AUTO = "AUTO"
    GUIDED = "GUIDED"
    MANUAL = "MANUAL"
    ANALYZE_ONLY = "ANALYZE_ONLY"


class PerformanceProfile:
    """Hardware / Performance profiles (Section 12)."""
    LOW = "LOW"
    BALANCED = "BALANCED"
    HIGH = "HIGH"
    CUSTOM = "CUSTOM"


class MappingMethod:
    """Coordinate mapping strategies to prevent stretched PBR textures on large/non-square terrains."""
    METRIC_OBJECT = "METRIC_OBJECT"
    ASPECT_CORRECTED_UV = "ASPECT_UV"


class EnvironmentBiome:
    """High-level Biome / Surface Ecology types (CP-03)."""
    DESERT = "DESERT"                        # Deserto (Areia + PBR 4K + Rocha em encostas íngremes)
    MOUNTAIN_ALPINE = "MOUNTAIN_ALPINE"      # Montanha Verde (Relva, Musgo, Rocha & Penhascos)
    LUSH_VALLEY = "LUSH_VALLEY"              # Vale Verdejante (Relva densa, Musgo húmido & Pedras)
    SAVANNA_PLAINS = "SAVANNA_PLAINS"        # Savana & Explanada (Terra vermelha, Relva dourada & Rocha)
    FANTASY_LANDSCAPE = "FANTASY_LANDSCAPE"  # Paisagem Fantasiosa (Musgo místico, Terraços & Rocha estilizada)


class DuneMorphology:
    """Terrain & Deformation Morphology families (CP-03)."""
    BRANCHING_ERG = "BRANCHING_ERG"          # Dunas em Teia Ramificada + Ondas (Efeito Rio / Árvore)
    DENDRITIC_WEB = "DENDRITIC_WEB"          # Rede Dendrítica Intensa (Árvore / Estrela / Cristas)
    SINUOUS_WAVES = "SINUOUS_WAVES"          # Ondas e Colinas Sinuosas Contínuas
    MEGA_CORRIDORS = "MEGA_CORRIDORS"        # Megadunas / Cordilheiras & Corredores Largos
    ALPINE_MOUNTAINS = "ALPINE_MOUNTAINS"    # Montanhas, Cristas Rochosas & Vales Esculpidos
    SAVANNA_EXPLANADA = "SAVANNA_EXPLANADA"  # Savana: Grandes Explanadas Planas + Planaltos (Mesas/Kopjes)
    FANTASY_TERRACES = "FANTASY_TERRACES"    # Paisagem Fantasiosa: Terraços Orgânicos, Platôs & Torres


class RoadMode:
    """How the Road / Path centerline is defined."""
    PROCEDURAL_WINDING = "PROCEDURAL_WINDING"  # Estrada sinuosa gerada automaticamente (1-Clique)
    CURVE_OBJECT = "CURVE_OBJECT"              # Segue a curva 3D `PROC_ENV_Road_Curve` na Viewport


class RoadStyle:
    """Visual surface style of the carved road/path in the Shader."""
    DIRT_TRAIL = "DIRT_TRAIL"          # Terra Batida / Trilho de Jogo
    STONE_PAVED = "STONE_PAVED"        # Pedra / Calçada Antiga / Rocha Esculpida
    DESERT_TRACK = "DESERT_TRACK"      # Areia Compactada & Cascalho
    MOSSY_PATH = "MOSSY_PATH"          # Trilho de Pedra com Musgo nas Bordas


PERFORMANCE_SETTINGS: Dict[str, Dict[str, Any]] = {
    PerformanceProfile.LOW: {
        "max_safe_base_vertices": 150_000,
        "allow_extra_subdiv": False,
        "max_viewport_subdiv": 0,
        "max_render_subdiv": 0,
        "noise_detail_cap": 2.0,
        "enable_micro_shader_ripples": True,
        "enable_anti_tiling_blend": False,
        "new_terrain_grid_res": 256,
    },
    PerformanceProfile.BALANCED: {
        "max_safe_base_vertices": 250_000,
        "allow_extra_subdiv": False,
        "max_viewport_subdiv": 0,
        "max_render_subdiv": 0,
        "noise_detail_cap": 3.5,
        "enable_micro_shader_ripples": True,
        "enable_anti_tiling_blend": True,
        "new_terrain_grid_res": 512,
    },
    PerformanceProfile.HIGH: {
        "max_safe_base_vertices": 300_000,
        "allow_extra_subdiv": False,
        "max_viewport_subdiv": 0,
        "max_render_subdiv": 0,
        "noise_detail_cap": 5.0,
        "enable_micro_shader_ripples": True,
        "enable_anti_tiling_blend": True,
        "new_terrain_grid_res": 1024,
    },
}


@dataclass
class TerrainEngineParams:
    """
    High-Level Parameter System (CP-03).
    Supports Multi-Biome Environments (Desert, Alpine Mountain, Lush Valley, Savanna Explanada,
    Fantasy Terraces) AND the Universal Road & Path Creator (Procedural Winding + 3D Curve).
    """
    # Global / Biome / Mode
    environment_type: str = EnvironmentBiome.DESERT
    preset_name: str = "cinematic_branching_erg"
    operation_mode: str = OperationMode.AUTO
    conflict_strategy: str = ConflictStrategy.ENHANCE_OPTIMIZE
    performance_profile: str = PerformanceProfile.BALANCED
    seed: int = 847293

    # World Metrics
    world_size_x: float = 590.0
    world_size_y: float = 834.0

    # Layer 3 — Terrain & Multi-Deformation Parameters
    dune_morphology: str = DuneMorphology.BRANCHING_ERG
    existing_relief_keep: float = 0.0
    dune_scale: float = 12.0                # Escala livre (0.05 a 500.0)
    dune_density: float = 1.2               # Frequência/quantidade de formações (0.05 a 100.0)
    dune_height: float = 26.0               # Altura principal em metros (-500 a 1000.0m)
    dune_variation: float = 2.4             # Sinuosidade / Curvatura (0.0 a 50.0)
    wind_turbulence: float = 1.6            # Turbulência / Erosão secundária (0.0 a 50.0)
    wind_direction_deg: float = 32.0        # Direção principal em graus (-360 a +360)

    # Branching / Web / Ridge Network & Plateau / Terrace Shaping
    dune_branching: float = 0.78            # Força do efeito Teia / Rio / Cristas Ramificadas (0.0 a 10.0)
    branch_anisotropy: float = 3.2          # Alongamento direcional (0.1 a 30.0)
    crest_roundness: float = 0.42           # Suavidade das cristas Voronoi (0.02 a 1.0)
    dune_sharpness: float = 1.35            # Perfil da encosta (0.5 a 3.0)
    plateau_flattening: float = 0.0         # Achata o topo ou base para Savanas/Explanadas/Mesas (0.0 a 1.0)
    terrace_steps: float = 0.0              # Degraus orgânicos suaves para Paisagens Fantasiosas (0.0 a 30.0)

    # Macro Basins & Secondary Undulations
    macro_basin_height: float = 14.0
    macro_basin_scale: float = 15.0
    medium_undulation_height: float = 3.0

    # Topological Smoothing & Shade Smooth
    mesh_smooth_iterations: int = 8
    mesh_smooth_factor: float = 0.72
    shade_smooth: bool = True

    # ------------------------------------------------------------------
    # UNIVERSAL ROAD & PATH CREATOR (CP-03)
    # ------------------------------------------------------------------
    enable_road: bool = True                # Ativa/desativa o sistema de estradas/caminhos no terreno
    road_mode: str = RoadMode.PROCEDURAL_WINDING
    road_style: str = RoadStyle.DIRT_TRAIL
    road_width_m: float = 14.0              # Largura do leito da estrada em metros (0.5 a 300.0m)
    road_shoulder_m: float = 24.0           # Largura da transição/talude suave nas bordas (0.5 a 300.0m)
    road_flatten_strength: float = 0.88     # Alisamento: 1.0 = alisa 100% as dunas/pedras por onde a estrada passa
    road_elevation_follow: float = 0.65     # Contorno: 1.0 = segue a altura macro das colinas; 0.0 = corta plano
    road_carve_depth_m: float = -0.5        # Escavação (<0) ou Aterro elevado (>0) do caminho em metros
    road_berm_height_m: float = 0.8         # Altura das bermas/acumulação lateral nas bordas da estrada (m)
    road_direction_deg: float = 15.0        # Ângulo da estrada procedural (-360 a +360)
    road_offset_m: float = 0.0              # Deslocamento lateral da estrada no terreno (-500m a +500m)
    road_meander_amplitude: float = 95.0    # Amplitude das curvas sinuosas da estrada em metros (0 a 500m)
    road_meander_scale: float = 12.0        # Escala/comprimento das curvas da estrada (0.1 a 500.0)
    road_secondary_branch: bool = True      # Cria uma bifurcação / caminho secundário que sai da estrada principal!

    # ------------------------------------------------------------------
    # LAYER 4 — MULTI-BIOME SURFACE (SAND / GRASS / MOSS / ROCK / ROAD + PBR)
    # ------------------------------------------------------------------
    sand_color_variation: float = 0.50      # Variação macro/média de cor (Areia / Relva / Musgo)
    sand_detail: float = 0.80               # Intensidade de micro-detalhes superficiais
    sand_ripple_scale: float = 22.0         # Frequência das micro-ondas ou tufos de relva/musgo
    sand_bump_strength: float = 0.36        # Força do Bump procedural
    sand_roughness_base: float = 0.86       # Rugosidade média da superfície

    # Rock & Moss / Grass Ecology Controls (CP-03)
    rock_slope_threshold: float = 0.78      # Inclinação (Normal.Z) abaixo da qual surge Rocha exposta (0.0 a 1.0)
    rock_blend_sharpness: float = 0.12      # Nitidez da transição entre Relva/Areia e Penhasco de Rocha
    moss_moisture_amount: float = 0.55      # Quantidade de Musgo / Vegetação nas zonas húmidas e bacias (0.0 a 1.0)

    # PBR 4K Integration & Anti-Stretching Control
    use_pbr_maps: bool = True               # Em Deserto usa red_sand_4k; em Montanha/Savana mistura detalhe físico PBR
    mapping_method: str = MappingMethod.METRIC_OBJECT
    pbr_tile_size_meters: float = 2.8
    pbr_blend_factor: float = 0.72
    pbr_normal_strength: float = 0.85
    anti_tiling_strength: float = 0.55

    # Palette Colors (Linear RGB — automatically set by Biome Preset or customizable)
    color_sand_primary: Tuple[float, float, float, float] = (0.72, 0.34, 0.18, 1.0)
    color_sand_crest: Tuple[float, float, float, float] = (0.86, 0.48, 0.26, 1.0)
    color_sand_trough: Tuple[float, float, float, float] = (0.46, 0.19, 0.10, 1.0)
    color_rock: Tuple[float, float, float, float] = (0.22, 0.19, 0.17, 1.0)
    color_moss: Tuple[float, float, float, float] = (0.14, 0.32, 0.09, 1.0)
    color_road: Tuple[float, float, float, float] = (0.34, 0.25, 0.18, 1.0)

    # ------------------------------------------------------------------
    # LAYER 5 — COMPLETE SCENARIO: PROCEDURAL HOUSES, PROPS, ROCKS, VEG & DECALS (CP-04)
    # ------------------------------------------------------------------
    enable_scenario_objects: bool = True    # Ativa a geração automática de Casas, Props, Rochas, Árvores e Decals
    house_style: str = "AUTO_BIOME"         # AUTO_BIOME | DESERT_ADOBE | MEDIEVAL_MOUNTAIN | SAVANNA_VILLAGE | FANTASY_TOWER
    house_count: int = 12                   # Quantidade de Casas / Edifícios procedurais (0 a 300)
    house_scale: float = 1.6                # Escala das casas (0.2 a 25.0)
    house_clustering: float = 0.72          # Agrupamento em Vila junto à estrada (0.0 = espalhado, 1.0 = aldeias)
    prop_count: int = 24                    # Postes de luz, placas, pilares de ruína e caixas à beira da estrada
    prop_scale: float = 1.4
    rock_count: int = 45                    # Pedras e rochedos procedurais espalhados pelas encostas
    rock_scale: float = 1.8
    vegetation_count: int = 55              # Árvores, palmeiras, cactos, acácias ou pinheiros do bioma
    vegetation_scale: float = 1.6
    decal_count: int = 30                   # Decals de chão e estrada (lajes de pedra, musgo, areia acumulada)
    decal_scale: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
