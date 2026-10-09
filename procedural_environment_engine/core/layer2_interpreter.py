"""
LAYER 2 — CONTEXT INTERPRETER
Transforms raw measurements from Layer 1 into epistemic findings (FACT / INFERRED / UNKNOWN),
component diagnoses (EXISTS / INCOMPLETE / MISSING / UNKNOWN), and an actionable plan.
"""

from typing import List, Dict
from ..config import ConflictStrategy, TERRAIN_MODIFIER_NAME
from .data_models import (
    SceneRawAnalysis,
    ContextInterpretationReport,
    EpistemicFinding,
    ComponentDiagnosis,
    EpistemicTag,
    ExistenceStatus,
    ActionDecision,
)


class ContextInterpreter:
    """
    Layer 2: Interprets SceneRawAnalysis without confusing existence with correct configuration.
    """

    def interpret(self, raw: SceneRawAnalysis) -> ContextInterpretationReport:
        report = ContextInterpretationReport()
        t = raw.primary_terrain

        # 1. Terrain Existence & Scale Analysis
        if t is None:
            report.findings.append(
                EpistemicFinding(
                    tag=EpistemicTag.FACT,
                    component="TERRAIN",
                    summary="Nenhum objeto mesh de terreno foi encontrado na cena.",
                )
            )
            report.component_diagnoses["TERRAIN"] = ComponentDiagnosis(
                component="TERRAIN",
                existence_status=ExistenceStatus.MISSING,
                config_status=ExistenceStatus.MISSING,
                recommended_action=ActionDecision.GENERATE,
                reason="Cena sem terreno principal. O motor irá gerar um novo terreno.",
            )
            report.what_is_missing.append("Objeto de Terreno base")
            report.what_i_should_generate.append("Novo terreno procedural na coleção PROC_ENV/TERRAIN")
            report.recommended_conflict_strategy = ConflictStrategy.CREATE_NEW
        else:
            dx, dy, dz = t.dimensions_m
            report.findings.append(
                EpistemicFinding(
                    tag=EpistemicTag.FACT,
                    component="TERRAIN",
                    summary=(
                        f"Terreno principal '{t.name}' medido com {dx:.3f} × {dy:.3f} × {dz:.3f} m "
                        f"(~{t.area_km2:.2f} km²) e {t.base_vertices:,} vértices base."
                    ),
                    details={
                        "dimensions_m": t.dimensions_m,
                        "area_km2": t.area_km2,
                        "base_vertices": t.base_vertices,
                        "base_polygons": t.base_polygons,
                    },
                )
            )
            report.what_i_have.append(
                f"Terreno '{t.name}' ({dx:.1f} × {dy:.1f} m, {t.base_vertices:,} vértices, UV: {t.uv_maps})"
            )
            report.what_i_can_keep.append(
                f"Malha e escala real do terreno '{t.name}' (~{t.area_km2:.2f} km²)"
            )

            # 2. Geometry Density & Modifier Load Analysis
            subsurf_mods = [m for m in t.modifiers if m.mod_type == "SUBSURF" and (m.show_viewport or m.show_render)]
            proc_env_mods = [m for m in t.modifiers if m.name == TERRAIN_MODIFIER_NAME]

            if t.base_vertices >= 500_000 and subsurf_mods:
                report.geometry_load_level = "CRITICAL_SUBDIV_RISK"
                report.findings.append(
                    EpistemicFinding(
                        tag=EpistemicTag.INFERRED,
                        component="GEOMETRY_PERFORMANCE",
                        summary=(
                            f"A malha base já possui alta densidade ({t.base_vertices:,} vértices). "
                            f"Com o modifier Subdivision ativo, a contagem estimada sobe para "
                            f"~{t.estimated_render_polygons:,} polígonos no Render — risco severo de memória."
                        ),
                        details={
                            "base_vertices": t.base_vertices,
                            "estimated_viewport_polygons": t.estimated_viewport_polygons,
                            "estimated_render_polygons": t.estimated_render_polygons,
                        },
                    )
                )
                report.what_i_should_modify.append(
                    "Desativar/otimizar de forma reversível o Subdivision extra para não multiplicar os 1,33M de vértices"
                )
            elif t.base_vertices >= 500_000:
                report.geometry_load_level = "HIGH"
                report.findings.append(
                    EpistemicFinding(
                        tag=EpistemicTag.INFERRED,
                        component="GEOMETRY_PERFORMANCE",
                        summary=(
                            f"Alta densidade geométrica existente ({t.base_vertices:,} vértices). "
                            "Não devemos subdividir mais; usar geometria para macro/média forma e shader para micro-detalhe."
                        ),
                    )
                )
            else:
                report.geometry_load_level = "NORMAL"

            # 3. Dune / Macroform Modifiers Diagnosis
            if proc_env_mods:
                report.component_diagnoses["TERRAIN_DUNES"] = ComponentDiagnosis(
                    component="TERRAIN_DUNES",
                    existence_status=ExistenceStatus.EXISTS,
                    config_status=ExistenceStatus.CORRECTLY_CONFIGURED,
                    recommended_action=ActionDecision.MODIFY,
                    reason=f"Modifier '{TERRAIN_MODIFIER_NAME}' já está ativo no terreno.",
                )
            else:
                has_any_gn = any(m.mod_type == "NODES" for m in t.modifiers)
                has_displace = any(m.mod_type == "DISPLACE" for m in t.modifiers)
                report.component_diagnoses["TERRAIN_DUNES"] = ComponentDiagnosis(
                    component="TERRAIN_DUNES",
                    existence_status=ExistenceStatus.INCOMPLETE if (has_any_gn or has_displace) else ExistenceStatus.MISSING,
                    config_status=ExistenceStatus.NOT_TESTED,
                    recommended_action=ActionDecision.GENERATE,
                    reason=(
                        "Modifiers existentes encontrados (Geometry Nodes / Displace), mas falta o sistema "
                        "parametrizado multi-escala de dunas (Macro Bacias + Dunas Direcionais + Ondulação Média)."
                    ),
                )
                report.what_is_missing.append(
                    "Sistema procedural de dunas multi-escala parametrizado (Macro / Medium / Wind Warp)"
                )
                report.what_i_should_generate.append(
                    f"Modifier Geometry Nodes '{TERRAIN_MODIFIER_NAME}' respeitando a escala {dx:.0f}×{dy:.0f}m"
                )

            # 4. Material & PBR 4K Analysis
            mat = t.active_material
            pbr_count = len(raw.available_pbr_maps)
            pbr_names = [info.image_name for info in raw.available_pbr_maps.values()]

            if pbr_count > 0:
                report.findings.append(
                    EpistemicFinding(
                        tag=EpistemicTag.FACT,
                        component="PBR_MAPS",
                        summary=(
                            f"Encontrados {pbr_count} mapas PBR no arquivo .blend: {', '.join(pbr_names)}."
                        ),
                        details={"pbr_maps": pbr_names},
                    )
                )
                report.what_i_have.append(f"{pbr_count} mapas PBR 4K no .blend ({', '.join(pbr_names)})")
                report.what_i_can_keep.append(f"Mapas PBR 4K existentes ({', '.join(pbr_names)})")

            if mat is None:
                report.component_diagnoses["SURFACE_MATERIAL"] = ComponentDiagnosis(
                    component="SURFACE_MATERIAL",
                    existence_status=ExistenceStatus.MISSING,
                    config_status=ExistenceStatus.MISSING,
                    recommended_action=ActionDecision.GENERATE,
                    reason="O terreno não possui material ativo.",
                )
                report.what_is_missing.append("Material de areia procedural + PBR")
            else:
                report.findings.append(
                    EpistemicFinding(
                        tag=EpistemicTag.FACT,
                        component="MATERIAL",
                        summary=(
                            f"Material ativo '{mat.name}' possui {mat.node_count} nodes "
                            f"({', '.join(mat.node_names)}). Usa PBR atualmente: {mat.uses_pbr_maps}."
                        ),
                        details={
                            "material_name": mat.name,
                            "node_count": mat.node_count,
                            "uses_pbr_maps": mat.uses_pbr_maps,
                            "connected_images": mat.connected_image_names,
                        },
                    )
                )
                report.what_i_have.append(f"Material ativo '{mat.name}' ({mat.node_count} nodes)")
                report.what_i_can_keep.append(f"Backup preservado do material '{mat.name}'")

                if pbr_count > 0 and not mat.uses_pbr_maps:
                    report.component_diagnoses["PBR_INTEGRATION"] = ComponentDiagnosis(
                        component="PBR_INTEGRATION",
                        existence_status=ExistenceStatus.EXISTS,
                        config_status=ExistenceStatus.INCOMPLETE,
                        recommended_action=ActionDecision.MODIFY,
                        reason=(
                            "Os mapas PBR 4K existem no .blend, mas NÃO estão conectados ao material atual. "
                            "Existência da imagem != uso ativo no shader."
                        ),
                    )
                    report.what_is_missing.append(
                        "Conexão controlada dos 3 mapas PBR 4K + variação procedural Macro/Média/Micro no shader"
                    )
                    report.what_i_should_modify.append(
                        f"Evoluir material '{mat.name}' (com backup) para Híbrido Procedural Multi-Escala + PBR 4K"
                    )
                elif mat.uses_pbr_maps and mat.has_explicit_mapping_node:
                    report.component_diagnoses["PBR_INTEGRATION"] = ComponentDiagnosis(
                        component="PBR_INTEGRATION",
                        existence_status=ExistenceStatus.EXISTS,
                        config_status=ExistenceStatus.CORRECTLY_CONFIGURED,
                        recommended_action=ActionDecision.KEEP,
                        reason="Mapas PBR estão conectados com nó explícito de Mapping.",
                    )
                else:
                    report.component_diagnoses["PBR_INTEGRATION"] = ComponentDiagnosis(
                        component="PBR_INTEGRATION",
                        existence_status=ExistenceStatus.INCOMPLETE,
                        config_status=ExistenceStatus.INCOMPLETE,
                        recommended_action=ActionDecision.GENERATE,
                        reason="Shader precisa de variação multi-escala e controle explícito de Mapping.",
                    )

            # 5. Stretching Risk Analysis (Why UV 0-1 stretches on 590 x 834 m)
            if max(dx, dy) > 20.0 or t.aspect_ratio_xy > 1.05:
                report.has_pbr_stretch_risk = True
                report.pbr_stretch_explanation = (
                    f"Terreno mede {dx:.1f}m × {dy:.1f}m (proporção 1 : {t.aspect_ratio_xy:.3f}). "
                    f"Mapear texturas em UV 0..1 sem escala métrica estica 1 único tile por {max(dx, dy):.1f}m "
                    f"e deforma o eixo maior em {(t.aspect_ratio_xy - 1.0) * 100:.1f}%. "
                    f"Solução: Mapeamento Métrico Real (ex: 1 tile 4K a cada 3.0m × 3.0m) + Anti-Tiling."
                )
                report.findings.append(
                    EpistemicFinding(
                        tag=EpistemicTag.INFERRED,
                        component="TEXTURE_MAPPING",
                        summary=report.pbr_stretch_explanation,
                        details={
                            "aspect_ratio_xy": t.aspect_ratio_xy,
                            "max_dimension_m": max(dx, dy),
                        },
                    )
                )
                report.what_i_should_generate.append(
                    "Sistema de Coordenadas Métricas Reais + Anti-Tiling no shader para impedir textura esticada"
                )

        # 6. Other Objects & Lighting/Camera Analysis (Preserve & Do Not Assume Unknowns)
        for other in raw.other_objects:
            if other.obj_type == "MESH" and other.semantic_role == EpistemicTag.UNKNOWN:
                report.findings.append(
                    EpistemicFinding(
                        tag=EpistemicTag.UNKNOWN,
                        component=f"OBJECT:{other.name}",
                        summary=(
                            f"Objeto mesh '{other.name}' ({other.dimensions_m[0]:.1f}×{other.dimensions_m[1]:.1f}×"
                            f"{other.dimensions_m[2]:.1f} m, {other.vertices} vértices, materiais={other.material_names}) "
                            "não possui função final classificada. Será preservado intacto (UNKNOWN != FALSE)."
                        ),
                    )
                )
                report.component_diagnoses[f"OBJECT:{other.name}"] = ComponentDiagnosis(
                    component=f"OBJECT:{other.name}",
                    existence_status=ExistenceStatus.EXISTS,
                    config_status=ExistenceStatus.UNKNOWN,
                    recommended_action=ActionDecision.PRESERVE_UNTOUCHED,
                    reason="Função exata ainda não classificada; não assumir que é duna ou montanha.",
                )
                report.what_i_can_keep.append(f"Objeto '{other.name}' preservado sem alterações")

        if raw.light_objects_count > 0 or raw.world_has_sky_texture:
            report.findings.append(
                EpistemicFinding(
                    tag=EpistemicTag.FACT,
                    component="LIGHTING",
                    summary=(
                        f"Iluminação base existente ({raw.light_objects_count} luz(es), "
                        f"World='{raw.world_name}', Sky Texture={raw.world_has_sky_texture})."
                    ),
                )
            )
            report.component_diagnoses["LIGHTING"] = ComponentDiagnosis(
                component="LIGHTING",
                existence_status=ExistenceStatus.EXISTS,
                config_status=ExistenceStatus.CORRECTLY_CONFIGURED,
                recommended_action=ActionDecision.KEEP,
                reason="A iluminação solar e Sky Texture já possuem base funcional.",
            )
            report.what_i_can_keep.append(f"Iluminação Sun + World '{raw.world_name}' (Sky Texture)")

        if raw.camera_objects_count > 0:
            report.component_diagnoses["CAMERA"] = ComponentDiagnosis(
                component="CAMERA",
                existence_status=ExistenceStatus.EXISTS,
                config_status=ExistenceStatus.EXISTS,
                recommended_action=ActionDecision.KEEP,
                reason="Câmera existente preservada (foco atual: fundação do terreno e superfície).",
            )
            report.what_i_can_keep.append("Camera existente preservada")

        return report
