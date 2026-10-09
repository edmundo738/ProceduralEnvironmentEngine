"""
SCRIPT RUNNER PARA BLENDER 5.2.1 LTS — PROCEDURAL ENVIRONMENT ENGINE V0
Como usar no Blender:
  1. Aba 'Scripting' -> Open -> selecione `scripts/run_v0_desert.py` (ou instale o .zip como Add-on).
  2. Clique em 'Run Script' (▶).
  3. O script irá:
     - Registar o painel lateral `ProcEnv` no 3D Viewport (atalho tecla `N` -> aba `ProcEnv`).
     - Analisar a cena atual (`Plane` 590x834m, 1.33M vértices, mapas PBR 4K).
     - Construir as Dunas Procedurais (Layer 3) + Areia Multi-Escala com PBR 4K sem estiramento (Layer 4).
     - Guardar backup reversível (`Desert_Sand.001_PROC_BACKUP` + Snapshot da cena).
     - Gravar o relatório completo no bloco de texto `PROC_ENV_Report.txt` dentro do Blender.
"""

import os
import sys
from pathlib import Path


def _ensure_repo_in_syspath() -> Path:
    try:
        # When run from disk or CLI
        here = Path(__file__).resolve()
        repo_root = here.parent.parent if here.parent.name == "scripts" else here.parent
    except NameError:
        # Fallback if pasted directly into an unsaved Blender text datablock
        repo_root = Path(os.getcwd())

    repo_str = str(repo_root)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)
    return repo_root


_ensure_repo_in_syspath()

import bpy  # noqa: E402
import procedural_environment_engine as proc_env  # noqa: E402
from procedural_environment_engine.config import (  # noqa: E402
    TerrainEngineParams,
    OperationMode,
    ConflictStrategy,
    PerformanceProfile,
    MappingMethod,
)
from procedural_environment_engine.presets.desert_presets import apply_preset_to_params  # noqa: E402


# ==============================================================================
# CONFIGURAÇÃO RÁPIDA DE EXECUÇÃO
# ==============================================================================
# Opções de ACTION:
#   "BUILD_V0"         -> Analisa + Cria Snapshot + Constrói Dunas + Areia/PBR 4K + Valida
#   "ANALYZE_ONLY"     -> Apenas inspeciona a cena e gera o relatório sem modificar nada
#   "ROLLBACK"         -> Reverte a cena para o estado original anterior ao script
#   "REGISTER_UI_ONLY" -> Apenas ativa o painel N-Panel 'ProcEnv' na 3D Viewport
ACTION = "BUILD_V0"

PRESET = "cinematic_branching_erg"  # "cinematic_branching_erg" | "dendritic_river_dunes" | "flowing_sahara_waves" | "namib_mega_corridors"
CONFLICT_STRATEGY = ConflictStrategy.ENHANCE_OPTIMIZE
PERFORMANCE_PROFILE = PerformanceProfile.BALANCED
SEED = 847293


def main() -> None:
    # 1. Registar o Add-on / Painel N-Panel ('ProcEnv')
    try:
        proc_env.unregister()
    except Exception:
        pass
    proc_env.register()
    print("[ProcEnv V0] Painel 'ProcEnv' registado na 3D Viewport (Pressione 'N' -> aba 'ProcEnv').")

    if ACTION == "REGISTER_UI_ONLY":
        return

    engine = proc_env.ProceduralEnvironmentEngine(bpy)

    if ACTION == "ROLLBACK":
        res = engine.rollback_to_snapshot(scene=bpy.context.scene)
        print("[ProcEnv V0] Resultado do Rollback:", res)
        return

    params = TerrainEngineParams(
        operation_mode=OperationMode.ANALYZE_ONLY if ACTION == "ANALYZE_ONLY" else OperationMode.AUTO,
        conflict_strategy=CONFLICT_STRATEGY,
        performance_profile=PERFORMANCE_PROFILE,
        mapping_method=MappingMethod.METRIC_OBJECT,
        seed=SEED,
    )
    apply_preset_to_params(params, PRESET)

    result = engine.run_v0(params=params, scene=bpy.context.scene)
    report_str = result["formatted_report"]

    # Guardar relatório dentro do Blender Text Editor ('PROC_ENV_Report.txt')
    txt = bpy.data.texts.get("PROC_ENV_Report.txt")
    if txt is None:
        txt = bpy.data.texts.new("PROC_ENV_Report.txt")
    txt.clear()
    txt.write(report_str)

    print(report_str)


if __name__ == "__main__":
    main()
