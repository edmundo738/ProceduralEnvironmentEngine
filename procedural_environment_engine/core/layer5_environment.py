"""
LAYER 5 — ENVIRONMENT, PROCEDURAL HOUSES, PROPS, VEGETATION, ROCKS & DECALS GENERATOR (CP-04)
Transforms the terrain + road foundation into a complete, ready-made 3D scenario:
1. Procedural Houses & Buildings (`PROC_ENV_BUILDINGS`):
   - Desert Adobe Houses, Mountain Timber Chalets, Savanna Thatched Huts, Fantasy Towers/Temples
   - Includes stone foundation plinths so houses never float on slopes, oriented toward roads/clusters.
2. Roadside & Scenario Props (`PROC_ENV_PROPS`):
   - Lantern Posts (with warm emissive light), Signposts, Ruin Pillars, Crates/Wagons along road shoulders.
3. Biome Rocks & Boulders (`PROC_ENV_ROCKS`):
   - Multi-faceted procedural rocks/crystals clustered on slopes and outcrops.
4. Biome Vegetation (`PROC_ENV_VEGETATION`):
   - Alpine Pines, Savanna Flat-Top Acacias, Desert Palms/Cacti, Lush Shrubs, Fantasy Flora.
5. Surface & Road Decals (`PROC_ENV_DECALS`):
   - Stone Paver Decals, Moss Patches, Sand Drifts & Cracked Earth conformed to surface normals.
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple
from ..config import (
    TerrainEngineParams,
    EnvironmentBiome,
    PREFIX,
)


class HouseStyle:
    AUTO_BIOME = "AUTO_BIOME"
    DESERT_ADOBE = "DESERT_ADOBE"
    MEDIEVAL_MOUNTAIN = "MEDIEVAL_MOUNTAIN"
    SAVANNA_VILLAGE = "SAVANNA_VILLAGE"
    FANTASY_TOWER = "FANTASY_TOWER"


class EnvironmentGenerator:
    """
    Layer 5: Generates and distributes procedural 3D meshes (Houses, Props, Rocks,
    Vegetation, and Ground Decals) following spatial composition rules (Road corridors,
    Slope thresholds, Village clustering).
    """

    def __init__(self, bpy_module: Any = None):
        if bpy_module is None:
            import bpy as _bpy
            self.bpy = _bpy
        else:
            self.bpy = bpy_module

    def populate_scenario(
        self,
        terrain_obj: Any,
        params: TerrainEngineParams,
        scene: Any = None,
        collections: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Clears previous `PROC_ENV` generated scenario objects and populates the new
        houses, props, rocks, vegetation, and decals according to `params`.
        """
        if scene is None:
            scene = self.bpy.context.scene

        self.clear_scenario_objects(scene=scene)

        if not getattr(params, "enable_scenario_objects", True):
            return {
                "houses_spawned": 0,
                "props_spawned": 0,
                "rocks_spawned": 0,
                "vegetation_spawned": 0,
                "decals_spawned": 0,
                "total_spawned": 0,
            }

        rng = random.Random(int(params.seed) + 777)

        # Ensure sub-collections for Buildings, Props, Rocks, Vegetation, Decals
        cols = self._ensure_scenario_collections(scene, collections)

        # Prepare materials for generated assets
        mats = self._ensure_asset_materials(params)

        # Build reusable procedural mesh archetypes (instanced for fast performance)
        archetypes = self._build_procedural_mesh_archetypes(params, mats, rng)

        # Measure terrain footprint
        dims = getattr(terrain_obj, "dimensions", (params.world_size_x, params.world_size_y, 38.0))
        span_x = max(float(dims[0]) * 0.86, 40.0)
        span_y = max(float(dims[1]) * 0.86, 40.0)

        # Obtain evaluated terrain object for exact raycast snapping if in real Blender
        eval_terrain = self._get_evaluated_terrain(terrain_obj)

        houses_count = 0
        props_count = 0
        rocks_count = 0
        veg_count = 0
        decals_count = 0

        # ------------------------------------------------------------------
        # 1. PROCEDURAL HOUSES & BUILDINGS (Along Road Shoulders & Village Clusters)
        # ------------------------------------------------------------------
        target_houses = int(getattr(params, "house_count", 12))
        h_scale_base = float(getattr(params, "house_scale", 1.5))
        road_half_w = max(float(params.road_width_m) * 0.5, 2.0)
        road_outer = road_half_w + max(float(params.road_shoulder_m) * 0.55, 6.0)

        # Pick 2-3 village cluster centers near the road
        village_centers: List[Tuple[float, float]] = []
        for i in range(3):
            vx = rng.uniform(-span_x * 0.35, span_x * 0.35)
            vy = self._estimate_road_center_y(vx, params) + rng.choice([-1.0, 1.0]) * (road_outer + rng.uniform(14.0, 38.0))
            village_centers.append((vx, vy))

        house_meshes = archetypes["HOUSES"]
        if house_meshes and target_houses > 0:
            attempts = 0
            while houses_count < target_houses and attempts < target_houses * 5:
                attempts += 1
                if rng.random() < float(getattr(params, "house_clustering", 0.7)) and village_centers:
                    cx, cy = rng.choice(village_centers)
                    px = cx + rng.gauss(0.0, 22.0)
                    py = cy + rng.gauss(0.0, 22.0)
                else:
                    px = rng.uniform(-span_x * 0.45, span_x * 0.45)
                    py = rng.uniform(-span_y * 0.45, span_y * 0.45)

                d_road = self._estimate_road_distance(px, py, params)
                # Never place a house on the road bed!
                if params.enable_road and d_road < (road_half_w + 6.5):
                    continue

                hit_z, normal = self._sample_surface(eval_terrain, px, py, params)
                # Prefer reasonably flat ground for houses
                if normal[2] < 0.72:
                    continue

                mesh_data = rng.choice(house_meshes)
                obj_name = f"{PREFIX}_House_{houses_count + 1:03d}"
                rot_z = math.atan2(-py, -px) + rng.uniform(-0.35, 0.35)
                s_var = h_scale_base * rng.uniform(0.82, 1.25)

                self._spawn_instance(
                    name=obj_name,
                    mesh_data=mesh_data,
                    location=(px, py, hit_z - 0.35),  # Sink foundation plinth slightly into ground
                    rotation_euler=(0.0, 0.0, rot_z),
                    scale=(s_var, s_var, s_var * rng.uniform(0.9, 1.15)),
                    collection=cols["BUILDINGS"],
                )
                houses_count += 1

        # ------------------------------------------------------------------
        # 2. ROADSIDE & SCENARIO PROPS (Lanterns, Signposts, Pillars, Crates)
        # ------------------------------------------------------------------
        target_props = int(getattr(params, "prop_count", 24))
        p_scale_base = float(getattr(params, "prop_scale", 1.4))
        prop_meshes = archetypes["PROPS"]
        if prop_meshes and target_props > 0:
            for i in range(target_props):
                if params.enable_road and i < int(target_props * 0.75):
                    # Place along road shoulder!
                    rx = rng.uniform(-span_x * 0.46, span_x * 0.46)
                    ry_center = self._estimate_road_center_y(rx, params)
                    side = -1.0 if (i % 2 == 0) else 1.0
                    ry = ry_center + side * (road_half_w + rng.uniform(2.2, 6.5))
                    px, py = self._unrotate_road_xy(rx, ry, params)
                else:
                    # Place near village houses
                    cx, cy = rng.choice(village_centers) if village_centers else (0.0, 0.0)
                    px = cx + rng.uniform(-25.0, 25.0)
                    py = cy + rng.uniform(-25.0, 25.0)

                hit_z, _ = self._sample_surface(eval_terrain, px, py, params)
                mesh_data = rng.choice(prop_meshes)
                s_var = p_scale_base * rng.uniform(0.85, 1.20)
                self._spawn_instance(
                    name=f"{PREFIX}_Prop_{props_count + 1:03d}",
                    mesh_data=mesh_data,
                    location=(px, py, hit_z - 0.1),
                    rotation_euler=(0.0, 0.0, rng.uniform(0.0, math.tau)),
                    scale=(s_var, s_var, s_var),
                    collection=cols["PROPS"],
                )
                props_count += 1

        # ------------------------------------------------------------------
        # 3. GROUND & ROAD DECALS (Stone Slabs, Moss Patches, Sand Drifts)
        # ------------------------------------------------------------------
        target_decals = int(getattr(params, "decal_count", 30))
        d_scale_base = float(getattr(params, "decal_scale", 2.0))
        decal_meshes = archetypes["DECALS"]
        if decal_meshes and target_decals > 0:
            for i in range(target_decals):
                if params.enable_road and i < int(target_decals * 0.65):
                    # Place directly on the road bed and shoulders!
                    rx = rng.uniform(-span_x * 0.46, span_x * 0.46)
                    ry = self._estimate_road_center_y(rx, params) + rng.uniform(-road_half_w * 0.9, road_half_w * 0.9)
                    px, py = self._unrotate_road_xy(rx, ry, params)
                else:
                    px = rng.uniform(-span_x * 0.45, span_x * 0.45)
                    py = rng.uniform(-span_y * 0.45, span_y * 0.45)

                hit_z, normal = self._sample_surface(eval_terrain, px, py, params)
                tilt_x, tilt_y = self._normal_to_tilt(normal)
                mesh_data = rng.choice(decal_meshes)
                s_var = d_scale_base * rng.uniform(0.7, 1.45)
                self._spawn_instance(
                    name=f"{PREFIX}_Decal_{decals_count + 1:03d}",
                    mesh_data=mesh_data,
                    location=(px, py, hit_z + 0.08),
                    rotation_euler=(tilt_x, tilt_y, rng.uniform(0.0, math.tau)),
                    scale=(s_var, s_var, s_var),
                    collection=cols["DECALS"],
                )
                decals_count += 1

        # ------------------------------------------------------------------
        # 4. BIOME ROCKS & BOULDERS (Clustered on Slopes & Outcrops)
        # ------------------------------------------------------------------
        target_rocks = int(getattr(params, "rock_count", 45))
        r_scale_base = float(getattr(params, "rock_scale", 1.8))
        rock_meshes = archetypes["ROCKS"]
        if rock_meshes and target_rocks > 0:
            for i in range(target_rocks):
                px = rng.uniform(-span_x * 0.47, span_x * 0.47)
                py = rng.uniform(-span_y * 0.47, span_y * 0.47)
                if params.enable_road and self._estimate_road_distance(px, py, params) < (road_half_w + 3.5):
                    continue
                hit_z, _ = self._sample_surface(eval_terrain, px, py, params)
                mesh_data = rng.choice(rock_meshes)
                s_var = r_scale_base * rng.uniform(0.5, 2.2)
                self._spawn_instance(
                    name=f"{PREFIX}_Rock_{rocks_count + 1:03d}",
                    mesh_data=mesh_data,
                    location=(px, py, hit_z - 0.25),
                    rotation_euler=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0.0, math.tau)),
                    scale=(s_var * rng.uniform(0.8, 1.3), s_var * rng.uniform(0.8, 1.3), s_var * rng.uniform(0.6, 1.4)),
                    collection=cols["ROCKS"],
                )
                rocks_count += 1

        # ------------------------------------------------------------------
        # 5. BIOME VEGETATION (Trees, Acacias, Palms, Pines, Shrubs)
        # ------------------------------------------------------------------
        target_veg = int(getattr(params, "vegetation_count", 55))
        v_scale_base = float(getattr(params, "vegetation_scale", 1.6))
        veg_meshes = archetypes["VEGETATION"]
        if veg_meshes and target_veg > 0:
            for i in range(target_veg):
                px = rng.uniform(-span_x * 0.47, span_x * 0.47)
                py = rng.uniform(-span_y * 0.47, span_y * 0.47)
                if params.enable_road and self._estimate_road_distance(px, py, params) < (road_half_w + 4.0):
                    continue
                hit_z, normal = self._sample_surface(eval_terrain, px, py, params)
                if normal[2] < 0.65:
                    continue
                mesh_data = rng.choice(veg_meshes)
                s_var = v_scale_base * rng.uniform(0.65, 1.55)
                self._spawn_instance(
                    name=f"{PREFIX}_Veg_{veg_count + 1:03d}",
                    mesh_data=mesh_data,
                    location=(px, py, hit_z - 0.15),
                    rotation_euler=(0.0, 0.0, rng.uniform(0.0, math.tau)),
                    scale=(s_var, s_var, s_var * rng.uniform(0.85, 1.25)),
                    collection=cols["VEGETATION"],
                )
                veg_count += 1

        total = houses_count + props_count + rocks_count + veg_count + decals_count
        return {
            "houses_spawned": houses_count,
            "props_spawned": props_count,
            "rocks_spawned": rocks_count,
            "vegetation_spawned": veg_count,
            "decals_spawned": decals_count,
            "total_spawned": total,
        }

    def clear_scenario_objects(self, scene: Any = None) -> int:
        """Removes all previously spawned `PROC_ENV_House_*`, `Prop_*`, `Rock_*`, `Veg_*`, `Decal_*` objects."""
        if scene is None:
            scene = self.bpy.context.scene
        objects = getattr(self.bpy.data, "objects", None)
        if objects is None:
            return 0

        prefixes = (
            f"{PREFIX}_House_",
            f"{PREFIX}_Prop_",
            f"{PREFIX}_Rock_",
            f"{PREFIX}_Veg_",
            f"{PREFIX}_Decal_",
        )
        to_remove = [o for o in list(objects) if any(str(o.name).startswith(p) for p in prefixes)]
        col_data = getattr(self.bpy.data, "collections", None)
        for obj in to_remove:
            try:
                if col_data is not None:
                    for col in col_data:
                        if hasattr(col, "objects") and obj in col.objects:
                            if hasattr(col.objects, "unlink"):
                                col.objects.unlink(obj)
                            else:
                                col.objects.remove(obj)
                if hasattr(objects, "remove"):
                    objects.remove(obj, do_unlink=True)
                elif obj in objects:
                    objects.remove(obj)
            except Exception:
                pass
        return len(to_remove)

    def _ensure_scenario_collections(
        self,
        scene: Any,
        collections: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        cols: Dict[str, Any] = dict(collections) if collections else {}
        col_data = getattr(self.bpy.data, "collections", None)
        if col_data is None:
            return cols

        root = col_data.get(PREFIX)
        if root is None:
            root = col_data.new(PREFIX)
            if hasattr(scene, "collection") and hasattr(scene.collection, "children"):
                scene.collection.children.link(root)

        for key in ("BUILDINGS", "PROPS", "DECALS", "ROCKS", "VEGETATION"):
            full_name = f"{PREFIX}_{key}"
            sub = col_data.get(full_name)
            if sub is None:
                sub = col_data.new(full_name)
            if hasattr(root, "children") and sub.name not in [c.name for c in root.children]:
                root.children.link(sub)
            cols[key] = sub
        return cols

    def _ensure_asset_materials(self, params: TerrainEngineParams) -> Dict[str, Any]:
        """Creates clean, stylized PBR materials for Houses, Roofs, Wood/Props, Rocks, Vegetation, and Decals."""
        materials = getattr(self.bpy.data, "materials", None)
        if materials is None:
            return {}

        biome = params.environment_type
        if biome == EnvironmentBiome.DESERT:
            wall_col = (0.76, 0.52, 0.34, 1.0)
            roof_col = (0.58, 0.34, 0.18, 1.0)
            foliage_col = (0.24, 0.42, 0.14, 1.0)
        elif biome in (EnvironmentBiome.MOUNTAIN_ALPINE, EnvironmentBiome.LUSH_VALLEY):
            wall_col = (0.68, 0.62, 0.54, 1.0)
            roof_col = (0.28, 0.14, 0.09, 1.0)
            foliage_col = (0.10, 0.34, 0.08, 1.0)
        elif biome == EnvironmentBiome.SAVANNA_PLAINS:
            wall_col = (0.62, 0.36, 0.20, 1.0)
            roof_col = (0.66, 0.52, 0.22, 1.0)
            foliage_col = (0.26, 0.40, 0.10, 1.0)
        else:  # FANTASY_LANDSCAPE
            wall_col = (0.28, 0.32, 0.44, 1.0)
            roof_col = (0.14, 0.48, 0.42, 1.0)
            foliage_col = (0.12, 0.55, 0.32, 1.0)

        specs = {
            "WALL": (f"{PREFIX}_Mat_HouseWall", wall_col, 0.85, 0.0),
            "ROOF": (f"{PREFIX}_Mat_HouseRoof", roof_col, 0.78, 0.0),
            "WOOD": (f"{PREFIX}_Mat_Wood", (0.26, 0.15, 0.08, 1.0), 0.82, 0.0),
            "ROCK": (f"{PREFIX}_Mat_RockAsset", params.color_rock, 0.88, 0.0),
            "FOLIAGE": (f"{PREFIX}_Mat_Foliage", foliage_col, 0.75, 0.0),
            "DECAL": (f"{PREFIX}_Mat_Decal", params.color_road, 0.90, 0.0),
            "LANTERN": (f"{PREFIX}_Mat_LanternGlow", (1.0, 0.68, 0.22, 1.0), 0.3, 8.0),
        }

        out: Dict[str, Any] = {}
        for key, (m_name, col, rough, emit) in specs.items():
            mat = materials.get(m_name)
            if mat is None:
                mat = materials.new(m_name)
            mat.use_nodes = True
            if hasattr(mat, "diffuse_color"):
                mat.diffuse_color = col
            nt = getattr(mat, "node_tree", None)
            if nt and getattr(nt, "nodes", None):
                bsdf = next(
                    (n for n in nt.nodes if getattr(n, "bl_idname", "") == "ShaderNodeBsdfPrincipled" or "Principled" in n.name),
                    None,
                )
                if bsdf is None:
                    nt.nodes.clear()
                    n_out = nt.nodes.new("ShaderNodeOutputMaterial")
                    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
                    nt.links.new(bsdf.outputs["BSDF"], n_out.inputs["Surface"])
                if "Base Color" in bsdf.inputs:
                    bsdf.inputs["Base Color"].default_value = col
                if "Roughness" in bsdf.inputs:
                    bsdf.inputs["Roughness"].default_value = rough
                if emit > 0.0 and "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = col
                    if "Emission Strength" in bsdf.inputs:
                        bsdf.inputs["Emission Strength"].default_value = emit
            out[key] = mat
        return out

    def _build_procedural_mesh_archetypes(
        self,
        params: TerrainEngineParams,
        mats: Dict[str, Any],
        rng: random.Random,
    ) -> Dict[str, List[Any]]:
        """
        Generates procedural 3D meshes (`House`, `Prop`, `Rock`, `Vegetation`, `Decal`)
        using `mesh.from_pydata(verts, [], faces)` so it works universally with zero external dependencies!
        """
        meshes_data = getattr(self.bpy.data, "meshes", None)
        if meshes_data is None:
            return {"HOUSES": [], "PROPS": [], "ROCKS": [], "VEGETATION": [], "DECALS": []}

        style = getattr(params, "house_style", HouseStyle.AUTO_BIOME)
        if style == HouseStyle.AUTO_BIOME:
            if params.environment_type == EnvironmentBiome.DESERT:
                style = HouseStyle.DESERT_ADOBE
            elif params.environment_type == EnvironmentBiome.SAVANNA_PLAINS:
                style = HouseStyle.SAVANNA_VILLAGE
            elif params.environment_type == EnvironmentBiome.FANTASY_LANDSCAPE:
                style = HouseStyle.FANTASY_TOWER
            else:
                style = HouseStyle.MEDIEVAL_MOUNTAIN

        houses = [
            self._create_procedural_house_mesh(meshes_data, f"{PREFIX}_Mesh_House_{i}", style, mats, rng, i)
            for i in range(2)
        ]
        props = [
            self._create_procedural_prop_mesh(meshes_data, f"{PREFIX}_Mesh_Prop_{i}", mats, i)
            for i in range(2)
        ]
        rocks = [
            self._create_procedural_rock_mesh(meshes_data, f"{PREFIX}_Mesh_Rock_{i}", mats, rng, i)
            for i in range(2)
        ]
        veg = [
            self._create_procedural_vegetation_mesh(meshes_data, f"{PREFIX}_Mesh_Veg_{i}", params.environment_type, mats, rng, i)
            for i in range(2)
        ]
        decals = [
            self._create_procedural_decal_mesh(meshes_data, f"{PREFIX}_Mesh_Decal_{i}", mats, rng, i)
            for i in range(2)
        ]

        return {
            "HOUSES": houses,
            "PROPS": props,
            "ROCKS": rocks,
            "VEGETATION": veg,
            "DECALS": decals,
        }

    def _create_procedural_house_mesh(
        self,
        meshes_data: Any,
        name: str,
        style: str,
        mats: Dict[str, Any],
        rng: random.Random,
        variant: int,
    ) -> Any:
        """
        Constructs a complete multi-part procedural building mesh:
        - Stone Foundation Plinth (`Z = -1.2m .. 0.0m`) so it never floats on slopes
        - Main Building Walls (`Z = 0.0m .. H`)
        - Roof Structure (Gabled pitched roof, Flat parapet + beams, Conical thatch, or Fantasy Spire)
        - Chimney / Side Annex / Doorway Awning
        """
        w = 3.2 + variant * 0.9
        d = 2.8 + (1 - variant) * 0.8
        h = 3.4 + variant * 0.6

        verts: List[Tuple[float, float, float]] = []
        faces: List[Tuple[int, ...]] = []

        def add_box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> None:
            b = len(verts)
            verts.extend([
                (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
            ])
            faces.extend([
                (b + 0, b + 1, b + 5, b + 4),
                (b + 1, b + 2, b + 6, b + 5),
                (b + 2, b + 3, b + 7, b + 6),
                (b + 3, b + 0, b + 4, b + 7),
                (b + 4, b + 5, b + 6, b + 7),
                (b + 3, b + 2, b + 1, b + 0),
            ])

        # 1. Stone Foundation Plinth
        add_box(-w * 1.08, w * 1.08, -d * 1.08, d * 1.08, -1.5, 0.2)
        # 2. Main House Body
        add_box(-w, w, -d, d, 0.2, h)

        if style == HouseStyle.DESERT_ADOBE:
            # Flat roof parapet walls + side annex tower + wooden roof beams
            add_box(-w * 1.04, w * 1.04, -d * 1.04, d * 1.04, h, h + 0.55)
            add_box(w * 0.3, w * 1.35, -d * 0.7, d * 0.7, 0.2, h * 1.38)
            # Wooden beams protruding from adobe façade
            for bx in (-w * 0.6, 0.0, w * 0.6):
                add_box(bx - 0.12, bx + 0.12, -d * 1.22, d * 1.22, h - 0.35, h - 0.15)
        elif style == HouseStyle.SAVANNA_VILLAGE:
            # Conical / Pyramidal Thatched Overhang Roof
            rw = w * 1.35
            rd = d * 1.35
            b = len(verts)
            verts.extend([
                (-rw, -rd, h - 0.1), (rw, -rd, h - 0.1),
                (rw, rd, h - 0.1), (-rw, rd, h - 0.1),
                (0.0, 0.0, h + 2.8),
            ])
            faces.extend([
                (b + 0, b + 1, b + 4),
                (b + 1, b + 2, b + 4),
                (b + 2, b + 3, b + 4),
                (b + 3, b + 0, b + 4),
            ])
        elif style == HouseStyle.FANTASY_TOWER:
            # Multi-tiered fantasy tower + steep spire roof
            add_box(-w * 0.75, w * 0.75, -d * 0.75, d * 0.75, h, h * 1.75)
            rw = w * 0.95
            rd = d * 0.95
            b = len(verts)
            verts.extend([
                (-rw, -rd, h * 1.72), (rw, -rd, h * 1.72),
                (rw, rd, h * 1.72), (-rw, rd, h * 1.72),
                (0.0, 0.0, h * 2.65),
            ])
            faces.extend([
                (b + 0, b + 1, b + 4),
                (b + 1, b + 2, b + 4),
                (b + 2, b + 3, b + 4),
                (b + 3, b + 0, b + 4),
            ])
        else:
            # MEDIEVAL_MOUNTAIN: Pitched Gabled Roof (Telhado de duas águas) + Chimney + Porch
            rw = w * 1.18
            rd = d * 1.18
            ridge_z = h + 2.4
            b = len(verts)
            verts.extend([
                (-rw, -rd, h - 0.1), (rw, -rd, h - 0.1),
                (rw, rd, h - 0.1), (-rw, rd, h - 0.1),
                (-rw, 0.0, ridge_z), (rw, 0.0, ridge_z),
            ])
            faces.extend([
                (b + 0, b + 1, b + 5, b + 4),
                (b + 2, b + 3, b + 4, b + 5),
                (b + 0, b + 4, b + 3),
                (b + 1, b + 2, b + 5),
            ])
            # Stone Chimney
            add_box(w * 0.45, w * 0.80, d * 0.25, d * 0.65, h * 0.5, ridge_z + 0.9)
            # Entrance Porch Awning
            add_box(-w * 0.35, w * 0.35, -d * 1.45, -d, 1.8, 2.15)

        return self._build_mesh_datablock(meshes_data, name, verts, faces, mats.get("WALL"))

    def _create_procedural_prop_mesh(
        self,
        meshes_data: Any,
        name: str,
        mats: Dict[str, Any],
        variant: int,
    ) -> Any:
        """Creates roadside Lantern Posts, Signposts, or Obelisk Pillars."""
        verts: List[Tuple[float, float, float]] = []
        faces: List[Tuple[int, ...]] = []

        def add_box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> None:
            b = len(verts)
            verts.extend([
                (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
            ])
            faces.extend([
                (b + 0, b + 1, b + 5, b + 4),
                (b + 1, b + 2, b + 6, b + 5),
                (b + 2, b + 3, b + 7, b + 6),
                (b + 3, b + 0, b + 4, b + 7),
                (b + 4, b + 5, b + 6, b + 7),
                (b + 3, b + 2, b + 1, b + 0),
            ])

        if variant == 0:
            # Roadside Lantern Post + Crossbar + Hanging Lantern
            add_box(-0.35, 0.35, -0.35, 0.35, -0.4, 0.6)
            add_box(-0.15, 0.15, -0.15, 0.15, 0.6, 3.8)
            add_box(-0.15, 1.25, -0.12, 0.12, 3.5, 3.75)
            add_box(0.85, 1.25, -0.22, 0.22, 2.85, 3.5)
            return self._build_mesh_datablock(meshes_data, name, verts, faces, mats.get("WOOD"))
        else:
            # Waypoint Stone Pillar / Ruin Marker + Crate
            add_box(-0.6, 0.6, -0.6, 0.6, -0.4, 0.5)
            add_box(-0.42, 0.42, -0.42, 0.42, 0.5, 3.2)
            add_box(0.75, 1.65, -0.45, 0.45, 0.0, 0.9)
            return self._build_mesh_datablock(meshes_data, name, verts, faces, mats.get("ROCK"))

    def _create_procedural_rock_mesh(
        self,
        meshes_data: Any,
        name: str,
        mats: Dict[str, Any],
        rng: random.Random,
        variant: int,
    ) -> Any:
        """Creates a faceted low-poly / stylized boulder mesh."""
        verts: List[Tuple[float, float, float]] = [(0.0, 0.0, 1.8), (0.0, 0.0, -0.6)]
        ring1 = 6
        for i in range(ring1):
            ang = (i / ring1) * math.tau
            r = 1.6 * rng.uniform(0.78, 1.25)
            verts.append((math.cos(ang) * r, math.sin(ang) * r, rng.uniform(0.1, 0.7)))

        faces: List[Tuple[int, ...]] = []
        for i in range(ring1):
            nxt = 2 + ((i + 1) % ring1)
            cur = 2 + i
            faces.append((0, cur, nxt))
            faces.append((1, nxt, cur))

        return self._build_mesh_datablock(meshes_data, name, verts, faces, mats.get("ROCK"))

    def _create_procedural_vegetation_mesh(
        self,
        meshes_data: Any,
        name: str,
        biome: str,
        mats: Dict[str, Any],
        rng: random.Random,
        variant: int,
    ) -> Any:
        """Creates biome-adapted procedural trees/flora (Pine, Flat-Top Savanna Acacia, Desert Palm/Cactus)."""
        verts: List[Tuple[float, float, float]] = []
        faces: List[Tuple[int, ...]] = []

        def add_box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> None:
            b = len(verts)
            verts.extend([
                (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
            ])
            faces.extend([
                (b + 0, b + 1, b + 5, b + 4),
                (b + 1, b + 2, b + 6, b + 5),
                (b + 2, b + 3, b + 7, b + 6),
                (b + 3, b + 0, b + 4, b + 7),
                (b + 4, b + 5, b + 6, b + 7),
                (b + 3, b + 2, b + 1, b + 0),
            ])

        # Trunk
        add_box(-0.28, 0.28, -0.28, 0.28, -0.3, 3.2)

        if biome == EnvironmentBiome.SAVANNA_PLAINS:
            # Flat-topped Savanna Acacia Canopy
            add_box(-2.8, 2.8, -2.6, 2.6, 3.0, 3.85)
            add_box(-1.8, 2.2, -2.0, 1.8, 3.7, 4.35)
        elif biome == EnvironmentBiome.DESERT:
            # Desert Saguaro / Palm Cluster
            add_box(0.28, 1.15, -0.22, 0.22, 1.4, 1.85)
            add_box(0.75, 1.15, -0.22, 0.22, 1.85, 3.0)
            add_box(-1.15, -0.28, -0.22, 0.22, 1.8, 2.2)
            add_box(-1.15, -0.75, -0.22, 0.22, 2.2, 3.3)
        else:
            # Layered Pine / Lush Canopy
            add_box(-1.9, 1.9, -1.9, 1.9, 1.8, 3.4)
            add_box(-1.4, 1.4, -1.4, 1.4, 3.1, 4.7)
            add_box(-0.8, 0.8, -0.8, 0.8, 4.4, 5.8)

        return self._build_mesh_datablock(meshes_data, name, verts, faces, mats.get("FOLIAGE"))

    def _create_procedural_decal_mesh(
        self,
        meshes_data: Any,
        name: str,
        mats: Dict[str, Any],
        rng: random.Random,
        variant: int,
    ) -> Any:
        """Creates a flat polygonal stone paver / moss / sand drift decal patch."""
        verts: List[Tuple[float, float, float]] = [(0.0, 0.0, 0.04)]
        sides = 6
        for i in range(sides):
            ang = (i / sides) * math.tau
            r = (1.4 + variant * 0.5) * rng.uniform(0.8, 1.2)
            verts.append((math.cos(ang) * r, math.sin(ang) * r, 0.0))

        faces: List[Tuple[int, ...]] = []
        for i in range(sides):
            cur = 1 + i
            nxt = 1 + ((i + 1) % sides)
            faces.append((0, cur, nxt))

        return self._build_mesh_datablock(meshes_data, name, verts, faces, mats.get("DECAL"))

    def _build_mesh_datablock(
        self,
        meshes_data: Any,
        name: str,
        verts: List[Tuple[float, float, float]],
        faces: List[Tuple[int, ...]],
        mat: Any,
    ) -> Any:
        existing = meshes_data.get(name)
        if existing is not None and hasattr(meshes_data, "remove"):
            try:
                meshes_data.remove(existing)
            except Exception:
                pass
        mesh = meshes_data.new(name)
        if hasattr(mesh, "from_pydata"):
            mesh.from_pydata(verts, [], faces)
            if hasattr(mesh, "update"):
                mesh.update()
        if mat is not None and hasattr(mesh, "materials") and hasattr(mesh.materials, "append"):
            mesh.materials.append(mat)
        return mesh

    def _spawn_instance(
        self,
        name: str,
        mesh_data: Any,
        location: Tuple[float, float, float],
        rotation_euler: Tuple[float, float, float],
        scale: Tuple[float, float, float],
        collection: Any,
    ) -> Any:
        obj = self.bpy.data.objects.new(name, mesh_data)
        obj.location = location
        obj.rotation_euler = rotation_euler
        obj.scale = scale
        if collection is not None and hasattr(collection, "objects"):
            collection.objects.link(obj)
        return obj

    def _get_evaluated_terrain(self, terrain_obj: Any) -> Optional[Any]:
        try:
            ctx = self.bpy.context
            if hasattr(ctx, "evaluated_depsgraph_get") and hasattr(terrain_obj, "evaluated_get"):
                deps = ctx.evaluated_depsgraph_get()
                return terrain_obj.evaluated_get(deps)
        except Exception:
            pass
        return None

    def _sample_surface(
        self,
        eval_terrain: Optional[Any],
        x: float,
        y: float,
        params: TerrainEngineParams,
    ) -> Tuple[float, Tuple[float, float, float]]:
        """
        Uses exact raycasting on the displaced terrain mesh when running in Blender,
        with an analytical elevation fallback for headless/mock environments.
        """
        if eval_terrain is not None and hasattr(eval_terrain, "ray_cast"):
            try:
                res, loc, norm, _ = eval_terrain.ray_cast((x, y, 2500.0), (0.0, 0.0, -1.0))
                if res:
                    return float(loc[2]), (float(norm[0]), float(norm[1]), float(norm[2]))
            except Exception:
                pass
        # Analytical fallback
        d_road = self._estimate_road_distance(x, y, params)
        half_w = float(params.road_width_m) * 0.5
        if params.enable_road and d_road <= half_w:
            return float(params.macro_basin_height) * 0.35 + float(params.road_carve_depth_m), (0.0, 0.0, 1.0)
        z_est = (
            float(params.macro_basin_height) * 0.4
            + float(params.dune_height) * 0.35 * (0.5 + 0.5 * math.sin(x * 0.02 + y * 0.015))
        )
        return z_est, (0.0, 0.0, 0.92)

    def _estimate_road_center_y(self, road_x: float, params: TerrainEngineParams) -> float:
        scale_norm = max(float(params.road_meander_scale) / 10.0, 0.02)
        freq = 0.0032 / scale_norm
        meander = math.sin(road_x * freq * math.tau) * float(params.road_meander_amplitude) * 0.55
        return float(params.road_offset_m) + meander

    def _unrotate_road_xy(self, rx: float, ry: float, params: TerrainEngineParams) -> Tuple[float, float]:
        ang = -math.radians(float(params.road_direction_deg))
        ca, sa = math.cos(ang), math.sin(ang)
        return (rx * ca - ry * sa, rx * sa + ry * ca)

    def _estimate_road_distance(self, x: float, y: float, params: TerrainEngineParams) -> float:
        ang = math.radians(float(params.road_direction_deg))
        ca, sa = math.cos(ang), math.sin(ang)
        rx = x * ca - y * sa
        ry = x * sa + y * ca
        cy = self._estimate_road_center_y(rx, params)
        d_main = abs(ry - cy)
        if params.road_secondary_branch and rx > 0.0:
            d_branch = abs(ry - (cy + rx * 0.62))
            return min(d_main, d_branch)
        return d_main

    def _normal_to_tilt(self, normal: Tuple[float, float, float]) -> Tuple[float, float]:
        nx, ny, nz = normal
        nz_safe = max(abs(nz), 0.1)
        return (-ny / nz_safe * 0.5, nx / nz_safe * 0.5)
