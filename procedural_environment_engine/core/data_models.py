"""
Core Data Models for the Procedural Environment Engine (V0).
Strictly separates FACT (measured), INFERRED (interpreted), and UNKNOWN (untested/unclassified),
as well as EXISTS, INCOMPLETE, MISSING, and UNKNOWN states.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple


class EpistemicTag:
    """Methodology classification (Section 13)."""
    FACT = "FACT"            # Measured/observed directly via bpy
    INFERRED = "INFERRED"    # Technical deduction based on measured facts
    UNKNOWN = "UNKNOWN"      # Not yet tested or semantically unclassified (UNKNOWN != FALSE)


class ExistenceStatus:
    """Component status classification (Sections 2 & 5)."""
    EXISTS = "EXISTS"
    CORRECTLY_CONFIGURED = "CORRECTLY_CONFIGURED"
    INCOMPLETE = "INCOMPLETE"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    NOT_TESTED = "NOT_TESTED"
    VISUALLY_VALIDATED = "VISUALLY_VALIDATED"


class ActionDecision:
    """What the engine recommends doing with a detected scene component."""
    KEEP = "KEEP"
    REUSE = "REUSE"
    MODIFY = "MODIFY"
    OPTIMIZE_MUTE = "OPTIMIZE_MUTE"
    GENERATE = "GENERATE"
    PRESERVE_UNTOUCHED = "PRESERVE_UNTOUCHED"


@dataclass
class EpistemicFinding:
    """A single diagnostic statement tagged as FACT, INFERRED, or UNKNOWN."""
    tag: str          # EpistemicTag.FACT | INFERRED | UNKNOWN
    component: str    # e.g., 'TERRAIN', 'GEOMETRY', 'PBR', 'MATERIAL', 'CONE', 'LIGHTING'
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModifierMetrics:
    name: str
    mod_type: str
    show_viewport: bool
    show_render: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PBRMapInfo:
    image_name: str
    channel_role: str          # 'DIFFUSE', 'NORMAL', 'ROUGHNESS', 'DISPLACEMENT', 'AO', 'OTHER'
    resolution: Tuple[int, int]
    source: str
    colorspace: str
    is_packed: bool
    has_data: bool
    is_connected_to_active_material: bool = False


@dataclass
class MaterialMetrics:
    name: str
    use_nodes: bool
    node_count: int
    node_types: List[str] = field(default_factory=list)
    node_names: List[str] = field(default_factory=list)
    connected_image_names: List[str] = field(default_factory=list)
    uses_pbr_maps: bool = False
    has_explicit_mapping_node: bool = False
    has_proc_env_signature: bool = False


@dataclass
class TerrainObjectMetrics:
    name: str
    dimensions_m: Tuple[float, float, float]
    area_m2: float
    area_km2: float
    aspect_ratio_xy: float
    local_bounds_x: Tuple[float, float]
    local_bounds_y: Tuple[float, float]
    local_bounds_z: Tuple[float, float]
    scale: Tuple[float, float, float]
    base_vertices: int
    base_edges: int
    base_polygons: int
    uv_maps: List[str] = field(default_factory=list)
    modifiers: List[ModifierMetrics] = field(default_factory=list)
    active_material: Optional[MaterialMetrics] = None
    estimated_viewport_polygons: int = 0
    estimated_render_polygons: int = 0


@dataclass
class OtherObjectMetrics:
    name: str
    obj_type: str
    dimensions_m: Tuple[float, float, float]
    scale: Tuple[float, float, float]
    vertices: int
    polygons: int
    material_names: List[str] = field(default_factory=list)
    semantic_role: str = EpistemicTag.UNKNOWN


@dataclass
class SceneRawAnalysis:
    """Output of Layer 1 — Scene Analyzer (pure observation, zero modification)."""
    blender_version: str
    scene_name: str
    unit_system: str
    unit_scale: float
    render_engine: str
    resolution_x: int
    resolution_y: int
    resolution_percentage: int
    total_objects: int
    mesh_objects_count: int
    camera_objects_count: int
    light_objects_count: int
    primary_terrain: Optional[TerrainObjectMetrics] = None
    other_objects: List[OtherObjectMetrics] = field(default_factory=list)
    available_pbr_maps: Dict[str, PBRMapInfo] = field(default_factory=dict)  # keyed by role ('DIFFUSE', 'NORMAL', 'ROUGHNESS')
    all_blend_images: List[PBRMapInfo] = field(default_factory=list)
    world_name: Optional[str] = None
    world_has_sky_texture: bool = False
    has_existing_snapshot: bool = False


@dataclass
class ComponentDiagnosis:
    component: str
    existence_status: str     # ExistenceStatus.*
    config_status: str        # ExistenceStatus.CORRECTLY_CONFIGURED | INCOMPLETE | NOT_TESTED | UNKNOWN
    recommended_action: str   # ActionDecision.*
    reason: str


@dataclass
class ContextInterpretationReport:
    """Output of Layer 2 — Context Interpreter."""
    findings: List[EpistemicFinding] = field(default_factory=list)
    component_diagnoses: Dict[str, ComponentDiagnosis] = field(default_factory=dict)
    geometry_load_level: str = "NORMAL"   # LOW | NORMAL | HIGH | CRITICAL_SUBDIV_RISK
    has_pbr_stretch_risk: bool = False
    pbr_stretch_explanation: str = ""
    recommended_conflict_strategy: str = "ENHANCE_OPTIMIZE"
    what_i_have: List[str] = field(default_factory=list)
    what_i_can_keep: List[str] = field(default_factory=list)
    what_i_should_modify: List[str] = field(default_factory=list)
    what_is_missing: List[str] = field(default_factory=list)
    what_i_should_generate: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    """Output of the Validator after Layer 3 & Layer 4 execution (Section 19)."""
    success: bool
    execution_time_ms: float
    terrain_object_name: str
    before_dimensions_m: Tuple[float, float, float]
    after_dimensions_m: Tuple[float, float, float]
    before_base_vertices: int
    after_base_vertices: int
    before_estimated_render_polys: int
    after_estimated_render_polys: int
    dunes_modifier_active: bool
    surface_material_name: str
    pbr_maps_connected: List[str] = field(default_factory=list)
    mapping_method_used: str = ""
    pbr_tile_size_m: float = 0.0
    backup_created: bool = False
    backup_material_name: str = ""
    parameter_verification: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
