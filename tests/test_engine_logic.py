"""
Unit & Integration Tests for Procedural Environment Engine V0.
Simulates the exact Blender 5.2.1 LTS Desert Scene from the specification:
  - Plane: 590.212 x 833.532 x 38.429 m, 1,329,352 vertices, UVMap
  - Modifiers: Geometry Nodes, Subdivision (View=1, Render=3), Displace (Strength=0.1)
  - Material: Desert_Sand.001 (4 nodes: Material Output, Principled BSDF, Noise Texture, Color Ramp)
  - Unconnected 4K PBR images in .blend:
      red_sand_diff_4k.jpg.001, red_sand_nor_gl_4k.exr, red_sand_rough_4k.exr
  - Other objects: Cone (24 vertices), Camera, Light (Sun), World.001 (Sky Texture)
"""

import unittest
from typing import Dict, List, Any, Optional
from procedural_environment_engine.config import (
    TerrainEngineParams,
    ConflictStrategy,
    OperationMode,
    PerformanceProfile,
    MappingMethod,
    TERRAIN_MODIFIER_NAME,
    BACKUP_SUFFIX,
)
from procedural_environment_engine.presets.desert_presets import apply_preset_to_params
from procedural_environment_engine.core.engine import ProceduralEnvironmentEngine
from procedural_environment_engine.core.data_models import EpistemicTag, ActionDecision


# ==============================================================================
# MOCK BLENDER 5.2.1 LTS API FOR AUTOMATED TESTING
# ==============================================================================

class MockSocket:
    def __init__(self, name: str, sock_type: str = "VALUE", default_value: Any = 0.0, identifier: str = ""):
        self.name = name
        self.type = sock_type
        self.default_value = default_value
        self.identifier = identifier or f"Socket_{name}"
        self.links: List[Any] = []


class MockSocketCollection(list):
    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(key)
        for item in self:
            if item.name == key:
                return item
        raise KeyError(key)

    def __contains__(self, key):
        if isinstance(key, str):
            return any(item.name == key for item in self)
        return super().__contains__(key)


class MockColorRampElement:
    def __init__(self, position: float, color=(0.0, 0.0, 0.0, 1.0)):
        self.position = position
        self.color = color


class MockColorRamp:
    def __init__(self):
        self.elements = [
            MockColorRampElement(0.0, (0.0, 0.0, 0.0, 1.0)),
            MockColorRampElement(1.0, (1.0, 1.0, 1.0, 1.0)),
        ]


class MockNode:
    def __init__(self, bl_idname: str, name: str = ""):
        self.bl_idname = bl_idname
        self.name = name or bl_idname
        self.type = bl_idname
        self.location = (0, 0)
        self.image = None
        self.operation = "ADD"
        self.rotation_type = "Z_AXIS"
        self.noise_type = "FBM"
        self.wave_type = "BANDS"
        self.bands_direction = "X"
        self.wave_profile = "SAW"
        self.data_type = "RGBA"
        self.blend_type = "MIX"
        self.color_ramp = MockColorRamp()
        self.inputs = MockSocketCollection()
        self.outputs = MockSocketCollection()
        self._populate_default_sockets(bl_idname)

    def _populate_default_sockets(self, bl_idname: str):
        if bl_idname in ("NodeGroupInput",):
            self.outputs.append(MockSocket("Geometry", "GEOMETRY"))
        elif bl_idname in ("NodeGroupOutput",):
            self.inputs.append(MockSocket("Geometry", "GEOMETRY"))
        elif bl_idname == "GeometryNodeInputPosition":
            self.outputs.append(MockSocket("Position", "VECTOR"))
        elif bl_idname == "GeometryNodeSetPosition":
            self.inputs.append(MockSocket("Geometry", "GEOMETRY"))
            self.inputs.append(MockSocket("Selection", "BOOLEAN", True))
            self.inputs.append(MockSocket("Position", "VECTOR", (0.0, 0.0, 0.0)))
            self.inputs.append(MockSocket("Offset", "VECTOR", (0.0, 0.0, 0.0)))
            self.outputs.append(MockSocket("Geometry", "GEOMETRY"))
        elif bl_idname == "ShaderNodeSeparateXYZ":
            self.inputs.append(MockSocket("Vector", "VECTOR"))
            self.outputs.extend([MockSocket("X"), MockSocket("Y"), MockSocket("Z")])
        elif bl_idname == "ShaderNodeCombineXYZ":
            self.inputs.extend([MockSocket("X"), MockSocket("Y"), MockSocket("Z")])
            self.outputs.append(MockSocket("Vector", "VECTOR"))
        elif bl_idname == "ShaderNodeVectorRotate":
            self.inputs.extend([
                MockSocket("Vector", "VECTOR"),
                MockSocket("Center", "VECTOR"),
                MockSocket("Axis", "VECTOR"),
                MockSocket("Angle", "VALUE", 0.0),
            ])
            self.outputs.append(MockSocket("Vector", "VECTOR"))
        elif bl_idname == "ShaderNodeVectorMath":
            self.inputs.extend([
                MockSocket("Vector", "VECTOR", (0.0, 0.0, 0.0)),
                MockSocket("Vector_001", "VECTOR", (0.0, 0.0, 0.0)),
                MockSocket("Vector_002", "VECTOR", (0.0, 0.0, 0.0)),
                MockSocket("Scale", "VALUE", 1.0),
            ])
            self.outputs.extend([MockSocket("Vector", "VECTOR"), MockSocket("Value", "VALUE")])
        elif bl_idname == "ShaderNodeMath":
            self.inputs.extend([
                MockSocket("Value", "VALUE", 0.0),
                MockSocket("Value_001", "VALUE", 0.0),
                MockSocket("Value_002", "VALUE", 0.0),
            ])
            self.outputs.append(MockSocket("Value", "VALUE"))
        elif bl_idname == "ShaderNodeTexNoise":
            self.inputs.extend([
                MockSocket("Vector", "VECTOR"),
                MockSocket("W", "VALUE"),
                MockSocket("Scale", "VALUE", 5.0),
                MockSocket("Detail", "VALUE", 2.0),
                MockSocket("Roughness", "VALUE", 0.5),
                MockSocket("Lacunarity", "VALUE", 2.0),
                MockSocket("Distortion", "VALUE", 0.0),
            ])
            self.outputs.extend([MockSocket("Fac", "VALUE"), MockSocket("Color", "RGBA")])
        elif bl_idname == "ShaderNodeTexWave":
            self.inputs.extend([
                MockSocket("Vector", "VECTOR"),
                MockSocket("Scale", "VALUE", 5.0),
                MockSocket("Distortion", "VALUE", 0.0),
                MockSocket("Detail", "VALUE", 2.0),
                MockSocket("Detail Scale", "VALUE", 1.0),
                MockSocket("Detail Roughness", "VALUE", 0.5),
                MockSocket("Phase Offset", "VALUE", 0.0),
            ])
            self.outputs.extend([MockSocket("Color", "RGBA"), MockSocket("Fac", "VALUE")])
        elif bl_idname == "ShaderNodeOutputMaterial":
            self.inputs.extend([MockSocket("Surface", "SHADER"), MockSocket("Volume", "SHADER"), MockSocket("Displacement", "VECTOR")])
        elif bl_idname == "ShaderNodeBsdfPrincipled":
            self.inputs.extend([
                MockSocket("Base Color", "RGBA", (0.8, 0.8, 0.8, 1.0)),
                MockSocket("Roughness", "VALUE", 0.5),
                MockSocket("IOR", "VALUE", 1.45),
                MockSocket("Specular IOR Level", "VALUE", 0.5),
                MockSocket("Normal", "VECTOR"),
            ])
            self.outputs.append(MockSocket("BSDF", "SHADER"))
        elif bl_idname == "ShaderNodeTexCoord":
            self.outputs.extend([
                MockSocket("Generated", "VECTOR"),
                MockSocket("Normal", "VECTOR"),
                MockSocket("UV", "VECTOR"),
                MockSocket("Object", "VECTOR"),
            ])
        elif bl_idname == "ShaderNodeMapping":
            self.inputs.extend([
                MockSocket("Vector", "VECTOR"),
                MockSocket("Location", "VECTOR", (0.0, 0.0, 0.0)),
                MockSocket("Rotation", "VECTOR", (0.0, 0.0, 0.0)),
                MockSocket("Scale", "VECTOR", (1.0, 1.0, 1.0)),
            ])
            self.outputs.append(MockSocket("Vector", "VECTOR"))
        elif bl_idname == "ShaderNodeValToRGB":
            self.inputs.append(MockSocket("Fac", "VALUE", 0.5))
            self.outputs.extend([MockSocket("Color", "RGBA"), MockSocket("Alpha", "VALUE")])
        elif bl_idname == "ShaderNodeMix":
            # Matches Blender 4.0+/5.2.1 ShaderNodeMix layout
            self.inputs.extend([
                MockSocket("Factor", "VALUE", 0.5),
                MockSocket("Factor_Vector", "VECTOR"),
                MockSocket("A_Float", "VALUE"),
                MockSocket("B_Float", "VALUE"),
                MockSocket("A_Vector", "VECTOR"),
                MockSocket("B_Vector", "VECTOR"),
                MockSocket("A", "RGBA", (0.0, 0.0, 0.0, 1.0)),
                MockSocket("B", "RGBA", (1.0, 1.0, 1.0, 1.0)),
            ])
            self.outputs.extend([
                MockSocket("Result_Float", "VALUE"),
                MockSocket("Result_Vector", "VECTOR"),
                MockSocket("Result", "RGBA"),
            ])
        elif bl_idname == "ShaderNodeTexImage":
            self.inputs.append(MockSocket("Vector", "VECTOR"))
            self.outputs.extend([MockSocket("Color", "RGBA"), MockSocket("Alpha", "VALUE")])
        elif bl_idname == "ShaderNodeMapRange":
            self.inputs.extend([
                MockSocket("Value", "VALUE", 0.5),
                MockSocket("From Min", "VALUE", 0.0),
                MockSocket("From Max", "VALUE", 1.0),
                MockSocket("To Min", "VALUE", 0.0),
                MockSocket("To Max", "VALUE", 1.0),
            ])
            self.outputs.append(MockSocket("Result", "VALUE"))
        elif bl_idname == "ShaderNodeBump":
            self.inputs.extend([
                MockSocket("Strength", "VALUE", 1.0),
                MockSocket("Distance", "VALUE", 1.0),
                MockSocket("Height", "VALUE", 0.0),
                MockSocket("Normal", "VECTOR"),
            ])
            self.outputs.append(MockSocket("Normal", "VECTOR"))
        elif bl_idname == "ShaderNodeNormalMap":
            self.inputs.extend([
                MockSocket("Strength", "VALUE", 1.0),
                MockSocket("Color", "RGBA", (0.5, 0.5, 1.0, 1.0)),
            ])
            self.outputs.append(MockSocket("Normal", "VECTOR"))
        elif bl_idname == "ShaderNodeTexVoronoi":
            self.feature = "SMOOTH_F1"
            self.distance = "EUCLIDEAN"
            self.inputs.extend([
                MockSocket("Vector", "VECTOR"),
                MockSocket("W", "VALUE"),
                MockSocket("Scale", "VALUE", 5.0),
                MockSocket("Detail", "VALUE", 0.0),
                MockSocket("Roughness", "VALUE", 0.5),
                MockSocket("Lacunarity", "VALUE", 2.0),
                MockSocket("Smoothness", "VALUE", 0.5),
                MockSocket("Exponent", "VALUE", 0.5),
                MockSocket("Randomness", "VALUE", 1.0),
            ])
            self.outputs.extend([
                MockSocket("Distance", "VALUE"),
                MockSocket("Color", "RGBA"),
                MockSocket("Position", "VECTOR"),
            ])
        elif bl_idname == "GeometryNodeBlurAttribute":
            self.data_type = "FLOAT"
            self.inputs.extend([
                MockSocket("Value", "VALUE", 0.0),
                MockSocket("Iterations", "INT", 4),
                MockSocket("Weight", "VALUE", 1.0),
            ])
            self.outputs.append(MockSocket("Value", "VALUE"))
        elif bl_idname == "GeometryNodeSetShadeSmooth":
            self.inputs.extend([
                MockSocket("Geometry", "GEOMETRY"),
                MockSocket("Selection", "BOOLEAN", True),
                MockSocket("Shade Smooth", "BOOLEAN", True),
            ])
            self.outputs.append(MockSocket("Geometry", "GEOMETRY"))
        elif bl_idname == "GeometryNodeStoreNamedAttribute":
            self.data_type = "FLOAT"
            self.domain = "POINT"
            self.inputs.extend([
                MockSocket("Geometry", "GEOMETRY"),
                MockSocket("Selection", "BOOLEAN", True),
                MockSocket("Name", "STRING", ""),
                MockSocket("Value", "VALUE", 0.0),
            ])
            self.outputs.append(MockSocket("Geometry", "GEOMETRY"))
        elif bl_idname == "ShaderNodeNewGeometry":
            self.outputs.extend([
                MockSocket("Position", "VECTOR"),
                MockSocket("Normal", "VECTOR"),
                MockSocket("True Normal", "VECTOR"),
            ])
        elif bl_idname == "ShaderNodeAttribute":
            self.attribute_name = ""
            self.outputs.extend([
                MockSocket("Color", "RGBA"),
                MockSocket("Vector", "VECTOR"),
                MockSocket("Fac", "VALUE"),
                MockSocket("Alpha", "VALUE"),
            ])


class MockLink:
    def __init__(self, from_socket: MockSocket, to_socket: MockSocket, from_node: MockNode, to_node: MockNode):
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.from_node = from_node
        self.to_node = to_node


class MockNodeCollection(list):
    def __init__(self, tree):
        super().__init__()
        self._tree = tree

    def new(self, bl_idname: str) -> MockNode:
        node = MockNode(bl_idname)
        self.append(node)
        return node

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(key)
        for n in self:
            if n.name == key:
                return n
        raise KeyError(key)

    def __contains__(self, key):
        if isinstance(key, str):
            return any(n.name == key for n in self)
        return super().__contains__(key)


class MockLinkCollection(list):
    def __init__(self, tree):
        super().__init__()
        self._tree = tree

    def new(self, from_sock: MockSocket, to_sock: MockSocket) -> MockLink:
        from_node = next((n for n in self._tree.nodes if from_sock in n.outputs), None)
        to_node = next((n for n in self._tree.nodes if to_sock in n.inputs), None)
        link = MockLink(from_sock, to_sock, from_node, to_node)
        to_sock.links.append(link)
        self.append(link)
        return link


class MockInterfaceSocket:
    def __init__(self, name: str, in_out: str, socket_type: str, identifier: str):
        self.item_type = "SOCKET"
        self.name = name
        self.in_out = in_out
        self.socket_type = socket_type
        self.identifier = identifier
        self.default_value = None
        self.min_value = None
        self.max_value = None


class MockNodeTreeInterface:
    def __init__(self):
        self.items_tree: List[MockInterfaceSocket] = []

    def new_socket(self, name: str, in_out: str = "INPUT", socket_type: str = "NodeSocketFloat"):
        ident = f"Socket_{len(self.items_tree) + 1}"
        item = MockInterfaceSocket(name, in_out, socket_type, ident)
        self.items_tree.append(item)
        return item


class MockNodeTree:
    def __init__(self, name: str, tree_type: str = "ShaderNodeTree"):
        self.name = name
        self.type = tree_type
        self.interface = MockNodeTreeInterface()
        self.nodes = MockNodeCollection(self)
        self.links = MockLinkCollection(self)


class MockMaterial:
    def __init__(self, name: str, collection=None):
        self.name = name
        self.use_nodes = True
        self.use_fake_user = False
        self.node_tree = MockNodeTree(f"{name}_nt")
        self._collection = collection

    def copy(self):
        m = MockMaterial(f"{self.name}_copy", collection=self._collection)
        for n in self.node_tree.nodes:
            new_n = m.node_tree.nodes.new(n.bl_idname)
            new_n.name = n.name
        if self._collection is not None:
            self._collection.append(m)
        return m


class MockImage:
    def __init__(self, name: str, size=(4096, 4096), colorspace="sRGB"):
        self.name = name
        self.size = size
        self.source = "FILE"
        self.packed_file = True
        self.has_data = True
        self.colorspace_settings = type("CS", (), {"name": colorspace})()


class MockModifier(dict):
    def __init__(self, name: str, mod_type: str):
        super().__init__()
        self.name = name
        self.type = mod_type
        self.show_viewport = True
        self.show_render = True
        self.levels = 1
        self.render_levels = 3
        self.strength = 0.1
        self.mid_level = 0.5
        self.texture = type("Tex", (), {"name": "Texture", "type": "IMAGE"})()
        self.node_group = None


class MockModifierCollection(list):
    def new(self, name: str, type: str) -> MockModifier:
        mod = MockModifier(name, type)
        self.append(mod)
        return mod

    def remove(self, mod: MockModifier) -> None:
        super().remove(mod)


class DummyCountList:
    """Memory-efficient list stand-in for 1,329,352 vertices in unit tests."""
    def __init__(self, count: int):
        self._count = count

    def __len__(self) -> int:
        return self._count

    def __iter__(self):
        return iter(())


class MockMesh:
    def __init__(self, verts: int = 0, edges: int = 0, polys: int = 0, uv_names=("UVMap",), name: str = ""):
        self.name = name
        self.vertices = DummyCountList(verts)
        self.edges = DummyCountList(edges)
        self.polygons = DummyCountList(polys)
        self.uv_layers = [type("UV", (), {"name": u})() for u in uv_names]
        self.materials: List[MockMaterial] = []

    def from_pydata(self, verts, edges, faces):
        self.vertices = DummyCountList(len(verts))
        self.edges = DummyCountList(len(edges))
        self.polygons = DummyCountList(len(faces))

    def update(self):
        pass


class MockObject:
    def __init__(
        self,
        name: str,
        obj_type: str,
        dimensions=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        bound_box=None,
        data=None,
        active_material=None,
    ):
        self.name = name
        self.type = obj_type
        self.dimensions = dimensions
        self.scale = scale
        self.location = (0.0, 0.0, 0.0)
        self.rotation_euler = (0.0, 0.0, 0.0)
        self.bound_box = bound_box or [
            (-dimensions[0] / 2, -dimensions[1] / 2, 0.0) for _ in range(8)
        ]
        self.data = data
        self.active_material = active_material
        self.modifiers = MockModifierCollection()

    def update_tag(self):
        pass


class NamedDataCollection(list):
    def __init__(self, factory):
        super().__init__()
        self._factory = factory

    def get(self, name: str) -> Optional[Any]:
        for item in self:
            if item.name == name:
                return item
        return None

    def new(self, name: str, *args, **kwargs) -> Any:
        item = self._factory(name, *args, **kwargs)
        self.append(item)
        return item

    def link(self, item: Any) -> None:
        if item not in self:
            self.append(item)

    def remove(self, item: Any, do_unlink: bool = True) -> None:
        if item in self:
            super().remove(item)


def build_mock_desert_blender():
    """Creates a mock `bpy` matching the user's exact Blender 5.2.1 LTS Desert Scene."""
    materials = NamedDataCollection(lambda name: None)
    materials._factory = lambda name: MockMaterial(name, collection=materials)
    node_groups = NamedDataCollection(lambda name, type="GeometryNodeTree": MockNodeTree(name, type))
    images = NamedDataCollection(lambda name: MockImage(name))
    meshes = NamedDataCollection(lambda name: MockMesh(name=name))
    objects = NamedDataCollection(lambda name, data=None: MockObject(name=name, obj_type="MESH" if data is not None else "EMPTY", data=data))
    collections = NamedDataCollection(
        lambda name: type("Col", (), {"name": name, "children": NamedDataCollection(lambda n: None), "objects": NamedDataCollection(lambda n: None)})()
    )

    # 3 PBR 4K maps in .blend (currently NOT connected to Desert_Sand.001)
    images.append(MockImage("red_sand_diff_4k.jpg.001", (4096, 4096), "sRGB"))
    images.append(MockImage("red_sand_nor_gl_4k.exr", (4096, 4096), "sRGB"))
    images.append(MockImage("red_sand_rough_4k.exr", (4096, 4096), "sRGB"))

    # Active material Desert_Sand.001 with 4 procedural nodes
    desert_mat = materials.new("Desert_Sand.001")
    out_n = desert_mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    out_n.name = "Material Output"
    bsdf_n = desert_mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_n.name = "Principled BSDF"
    noise_n = desert_mat.node_tree.nodes.new("ShaderNodeTexNoise")
    noise_n.name = "Noise Texture"
    ramp_n = desert_mat.node_tree.nodes.new("ShaderNodeValToRGB")
    ramp_n.name = "Color Ramp"
    desert_mat.node_tree.links.new(noise_n.outputs["Fac"], ramp_n.inputs["Fac"])
    desert_mat.node_tree.links.new(ramp_n.outputs["Color"], bsdf_n.inputs["Base Color"])
    desert_mat.node_tree.links.new(bsdf_n.outputs["BSDF"], out_n.inputs["Surface"])

    # Plane terrain object (590.212 x 833.532 x 38.429 m, 1,329,352 vertices)
    plane_bbox = [
        (-298.197, -413.111, -1.810),
        (293.278, -413.111, -1.810),
        (293.278, 422.327, -1.810),
        (-298.197, 422.327, -1.810),
        (-298.197, -413.111, 37.186),
        (293.278, -413.111, 37.186),
        (293.278, 422.327, 37.186),
        (-298.197, 422.327, 37.186),
    ]
    plane_mesh = MockMesh(1_329_352, 2_656_408, 1_327_057, ("UVMap",))
    plane_mesh.materials.append(desert_mat)
    plane_obj = MockObject(
        name="Plane",
        obj_type="MESH",
        dimensions=(590.212, 833.532, 38.429),
        scale=(1.0, 1.0, 1.0),
        bound_box=plane_bbox,
        data=plane_mesh,
        active_material=desert_mat,
    )
    gn_mod = plane_obj.modifiers.new("Geometry Nodes", "NODES")
    gn_mod.node_group = node_groups.new("Legacy_GN", type="GeometryNodeTree")
    sub_mod = plane_obj.modifiers.new("Subdivision", "SUBSURF")
    sub_mod.levels = 1
    sub_mod.render_levels = 3
    disp_mod = plane_obj.modifiers.new("Displace", "DISPLACE")
    disp_mod.strength = 0.1
    disp_mod.mid_level = 0.5

    # Cone object (24 vertices, unclassified)
    cone_mesh = MockMesh(24, 36, 18, ())
    cone_obj = MockObject(
        name="Cone",
        obj_type="MESH",
        dimensions=(461.705, 482.852, 232.795),
        scale=(66.636, 60.627, 59.590),
        data=cone_mesh,
        active_material=None,
    )

    cam_obj = MockObject(name="Camera", obj_type="CAMERA")
    light_obj = MockObject(name="Light", obj_type="LIGHT")

    # World.001 with Sky Texture
    world_nt = MockNodeTree("World_nt")
    sky_node = world_nt.nodes.new("ShaderNodeTexSky")
    sky_node.type = "TEX_SKY"
    world = type("World", (), {"name": "World.001", "use_nodes": True, "node_tree": world_nt})()

    class MockScene(dict):
        def __init__(self):
            super().__init__()
            self.name = "Scene"
            self.unit_settings = type("US", (), {"system": "METRIC", "scale_length": 1.0})()
            self.render = type(
                "R",
                (),
                {"engine": "CYCLES", "resolution_x": 1920, "resolution_y": 1080, "resolution_percentage": 100},
            )()
            self.objects = NamedDataCollection(lambda n: None)
            self.objects.extend([cam_obj, light_obj, plane_obj, cone_obj])
            self.world = world
            self.collection = collections.new("Scene Collection")

    scene = MockScene()
    mock_bpy = type(
        "MockBpy",
        (),
        {
            "app": type("App", (), {"version_string": "5.2.1 LTS"})(),
            "context": type("Ctx", (), {"scene": scene, "view_layer": type("VL", (), {"update": lambda self: None})()})(),
            "data": type(
                "Data",
                (),
                {
                    "materials": materials,
                    "node_groups": node_groups,
                    "images": images,
                    "collections": collections,
                    "meshes": meshes,
                    "objects": objects,
                },
            )(),
        },
    )()
    return mock_bpy


class TestProceduralEnvironmentEngineV0(unittest.TestCase):
    def setUp(self):
        self.mock_bpy = build_mock_desert_blender()
        self.engine = ProceduralEnvironmentEngine(self.mock_bpy)

    def test_layer1_and_layer2_analysis_matches_checkpoint_facts(self):
        raw, interp = self.engine.analyze_only()

        # Verify Layer 1 measurements
        self.assertEqual(raw.blender_version, "5.2.1 LTS")
        self.assertEqual(raw.total_objects, 4)
        self.assertIsNotNone(raw.primary_terrain)
        self.assertEqual(raw.primary_terrain.name, "Plane")
        self.assertEqual(raw.primary_terrain.base_vertices, 1_329_352)
        self.assertAlmostEqual(raw.primary_terrain.dimensions_m[0], 590.212)
        self.assertAlmostEqual(raw.primary_terrain.dimensions_m[1], 833.532)
        self.assertFalse(raw.primary_terrain.active_material.uses_pbr_maps)
        self.assertEqual(len(raw.available_pbr_maps), 3)
        self.assertIn("DIFFUSE", raw.available_pbr_maps)
        self.assertIn("NORMAL", raw.available_pbr_maps)
        self.assertIn("ROUGHNESS", raw.available_pbr_maps)

        # Verify Layer 2 interpretations
        self.assertEqual(interp.geometry_load_level, "CRITICAL_SUBDIV_RISK")
        self.assertTrue(interp.has_pbr_stretch_risk)

        # Verify Cone is classified as UNKNOWN and PRESERVE_UNTOUCHED
        cone_diag = interp.component_diagnoses.get("OBJECT:Cone")
        self.assertIsNotNone(cone_diag)
        self.assertEqual(cone_diag.config_status, EpistemicTag.UNKNOWN)
        self.assertEqual(cone_diag.recommended_action, ActionDecision.PRESERVE_UNTOUCHED)

    def test_full_v0_build_and_pbr_integration(self):
        params = TerrainEngineParams(
            operation_mode=OperationMode.AUTO,
            conflict_strategy=ConflictStrategy.ENHANCE_OPTIMIZE,
            performance_profile=PerformanceProfile.BALANCED,
            mapping_method=MappingMethod.METRIC_OBJECT,
            seed=847293,
        )
        apply_preset_to_params(params, "cinematic_branching_erg")

        result = self.engine.run_v0(params=params)
        val = result["validation"]

        self.assertTrue(val.success)
        self.assertEqual(val.terrain_object_name, "Plane")
        # Base vertices preserved at 1,329,352
        self.assertEqual(val.before_base_vertices, 1_329_352)
        self.assertEqual(val.after_base_vertices, 1_329_352)
        # Render polygon explosion mitigated (from ~84.9M down to ~1.327M)
        self.assertGreater(val.before_estimated_render_polys, 80_000_000)
        self.assertEqual(val.after_estimated_render_polys, 1_327_057)

        # All 3 4K PBR maps connected and colorspaces properly configured
        self.assertEqual(len(val.pbr_maps_connected), 3)
        self.assertIn("red_sand_diff_4k.jpg.001", val.pbr_maps_connected)
        self.assertIn("red_sand_nor_gl_4k.exr", val.pbr_maps_connected)
        self.assertIn("red_sand_rough_4k.exr", val.pbr_maps_connected)

        nor_img = self.mock_bpy.data.images.get("red_sand_nor_gl_4k.exr")
        rough_img = self.mock_bpy.data.images.get("red_sand_rough_4k.exr")
        self.assertEqual(nor_img.colorspace_settings.name, "Non-Color")
        self.assertEqual(rough_img.colorspace_settings.name, "Non-Color")

        # Backup material created cleanly without chaining _PROC_BACKUP_PROC_BACKUP
        backup_name = f"Desert_Sand.001{BACKUP_SUFFIX}"
        self.assertEqual(val.backup_material_name, backup_name)
        self.assertIsNotNone(self.mock_bpy.data.materials.get(backup_name))

        # Run multiple times to ensure _PROC_BACKUP never chains into _PROC_BACKUP_PROC_BACKUP
        self.engine.run_v0(params=params)
        self.engine.run_v0(params=params)
        for m in self.mock_bpy.data.materials:
            self.assertNotIn(f"{BACKUP_SUFFIX}{BACKUP_SUFFIX}", m.name)

        # Verify CP-02 anti-wall (SIN profile), Voronoi branching, and Blur Attribute
        self.assertEqual(val.parameter_verification.get("wave_profile"), "SIN")
        self.assertTrue(val.parameter_verification.get("branching_voronoi_active"))
        self.assertTrue(val.parameter_verification.get("topological_blur_active"))

    def test_cp02_wide_scale_above_3_and_branching_updates(self):
        params = TerrainEngineParams(dune_scale=45.0, dune_density=3.5, dune_branching=2.2)
        self.engine.run_v0(params=params)
        gn_tree = self.mock_bpy.data.node_groups.get("PROC_ENV_Dunes_GN")
        self.assertIsNotNone(gn_tree)
        self.assertIn("PROC_BranchingVoronoiMain", gn_tree.nodes)
        self.assertIn("PROC_BranchingVoronoiSub", gn_tree.nodes)
        self.assertIn("PROC_TopologicalSmoothZ", gn_tree.nodes)
        self.assertIn("PROC_SetShadeSmooth", gn_tree.nodes)
        self.assertEqual(gn_tree.nodes["PROC_PrimaryDuneWave"].wave_profile, "SIN")

    def test_cp03_multi_biome_and_universal_road_system(self):
        for preset_key in (
            "green_mossy_mountains",
            "lush_moss_valley",
            "savanna_plains_kopjes",
            "fantasy_terraced_peaks",
        ):
            params = TerrainEngineParams()
            apply_preset_to_params(params, preset_key)
            res = self.engine.run_v0(params=params)
            self.assertTrue(res["validation"].success)

        gn_tree = self.mock_bpy.data.node_groups.get("PROC_ENV_Dunes_GN")
        self.assertIn("PROC_RoadMaskRange", gn_tree.nodes)
        self.assertIn("PROC_StoreRoadMask", gn_tree.nodes)
        self.assertIn("PROC_PlateauMapRange", gn_tree.nodes)

        plane = self.mock_bpy.context.scene.objects.get("Plane")
        mat_nodes = plane.active_material.node_tree.nodes
        self.assertIn("PROC_SlopeRockMask", mat_nodes)
        self.assertIn("PROC_SlopeRockColorMix", mat_nodes)
        self.assertIn("PROC_RoadMaskAttr", mat_nodes)
        self.assertIn("PROC_RoadSurfaceColorMix", mat_nodes)

        # Verify live road parameter update
        params.road_width_m = 28.0
        params.road_shoulder_m = 36.0
        self.engine.live_update_parameters(params)
        self.assertAlmostEqual(gn_tree.nodes["PROC_RoadMaskRange"].inputs["From Min"].default_value, 14.0)
        self.assertAlmostEqual(gn_tree.nodes["PROC_RoadMaskRange"].inputs["From Max"].default_value, 50.0)

    def test_cp04_complete_scenario_houses_props_rocks_decals(self):
        for preset_key, expected_biome in (
            ("desert_caravan_road", "DESERT"),
            ("green_mossy_mountains", "MOUNTAIN_ALPINE"),
            ("savanna_plains_kopjes", "SAVANNA_PLAINS"),
            ("fantasy_terraced_peaks", "FANTASY_LANDSCAPE"),
        ):
            params = TerrainEngineParams()
            apply_preset_to_params(params, preset_key)
            res = self.engine.run_v0(params=params)
            self.assertTrue(res["validation"].success)
            self.assertEqual(params.environment_type, expected_biome)
            env_summary = res.get("environment_result", {})
            self.assertGreater(env_summary.get("houses_spawned", 0), 0)
            self.assertGreater(env_summary.get("props_spawned", 0), 0)
            self.assertGreater(env_summary.get("rocks_spawned", 0), 0)
            self.assertGreater(env_summary.get("vegetation_spawned", 0), 0)
            self.assertGreater(env_summary.get("decals_spawned", 0), 0)
            self.assertGreater(env_summary.get("total_spawned", 0), 0)

        # Verify collections and clear_scenario_objects
        buildings_col = self.mock_bpy.data.collections.get("PROC_ENV_BUILDINGS")
        props_col = self.mock_bpy.data.collections.get("PROC_ENV_PROPS")
        decals_col = self.mock_bpy.data.collections.get("PROC_ENV_DECALS")
        self.assertIsNotNone(buildings_col)
        self.assertIsNotNone(props_col)
        self.assertIsNotNone(decals_col)
        self.assertGreater(len(buildings_col.objects), 0)
        self.assertGreater(len(props_col.objects), 0)
        self.assertGreater(len(decals_col.objects), 0)

        removed = self.engine.environment_gen.clear_scenario_objects(scene=self.mock_bpy.context.scene)
        self.assertGreater(removed, 0)
        self.assertEqual(len(buildings_col.objects), 0)

    def test_live_parameter_updates_and_rollback(self):
        params = TerrainEngineParams()
        self.engine.run_v0(params=params)

        # Modify parameters via live_update_parameters
        params.dune_height = 33.5
        params.pbr_tile_size_meters = 4.0
        updated = self.engine.live_update_parameters(params)
        self.assertTrue(updated)

        gn_tree = self.mock_bpy.data.node_groups.get("PROC_ENV_Dunes_GN")
        self.assertAlmostEqual(gn_tree.nodes["PROC_DuneHeightMul"].inputs[1].default_value, 33.5)

        plane = self.mock_bpy.context.scene.objects.get("Plane")
        mapping_scale = plane.active_material.node_tree.nodes["PROC_PBR_Mapping"].inputs["Scale"].default_value
        self.assertAlmostEqual(mapping_scale[0], 0.25)

        # Rollback to snapshot
        rollback_res = self.engine.rollback_to_snapshot()
        self.assertTrue(rollback_res["restored"])
        mod_names = [m.name for m in plane.modifiers]
        self.assertNotIn(TERRAIN_MODIFIER_NAME, mod_names)

        # Original Subdivision modifier restored
        sub_mod = next(m for m in plane.modifiers if m.type == "SUBSURF")
        self.assertTrue(sub_mod.show_viewport)
        self.assertTrue(sub_mod.show_render)


if __name__ == "__main__":
    unittest.main()
