# Procedural Environment Engine (`ProcEnv V0.4 — CP-04`)

Motor autónomo de **Geração de Cenários Pré-Prontos Multi-Bioma, Criador Universal de Estradas & Caminhos, Casas Procedurais 3D, Props, Rochas, Vegetação, Decals e Superfície Híbrida PBR 4K** para **Blender 5.2+ LTS**.

> **Princípio Central**: *"Construir ambientes e cenários completos através de regras, contexto e composição, minimizando a intervenção humana sem desperdiçar o trabalho que já existe."*

---

## 1. Arquitetura em Camadas (`CP-04`)

```text
ProceduralEnvironmentEngine/
├── CHECKPOINT.md                          # Estado vivo do projeto (FACT / INFERRED / UNKNOWN & Checkpoints)
├── releases/
│   └── procedural_environment_engine_v0.zip  # Add-on V0.4.0 PRONTO A BAIXAR E INSTALAR no Blender 5.2+
├── docs/
│   ├── ARCHITECTURE_V0.md                 # Especificação das 7 Camadas e Metodologia Epistemológica
│   └── DESERT_CASE_STUDY.md               # Diagnóstico Técnico do Caso Real (590×834m, 1.33M verts, PBR 4K)
├── procedural_environment_engine/         # Add-on instalável no Blender 5.2+ LTS
│   ├── __init__.py                        # Registo do Add-on e painel N-Panel ('ProcEnv')
│   ├── blender_manifest.toml              # Manifesto de Extensão Blender 4.2+ / 5.2+ (V0.4.0)
│   ├── config.py                          # Parâmetros Multi-Bioma, Estradas, Casas, Props, Rochas e Decals
│   ├── core/
│   │   ├── data_models.py                 # Separação estrita: FACT / INFERRED / UNKNOWN e EXISTS / INCOMPLETE / MISSING
│   │   ├── layer1_analyzer.py             # LAYER 1: Scene Analyzer (observação pura sem modificar a cena)
│   │   ├── layer2_interpreter.py          # LAYER 2: Context Interpreter (diagnóstico + 5 perguntas do motor)
│   │   ├── state_manager.py               # Reversibilidade: Snapshots JSON, Backups de Material e Rollback 1-Clique
│   │   ├── layer3_terrain.py              # LAYER 3: Terrain & Road Generator (Multi-Bioma + Escavação/Alisamento de Estrada)
│   │   ├── layer4_surface.py              # LAYER 4: Surface Generator (Biomas + Rocha por Inclinação + Pintura de Estrada + PBR 4K)
│   │   ├── layer5_environment.py          # LAYER 5: Complete Scenario Generator (Casas Procedurais, Props, Rochas, Árvores e Decals)
│   │   ├── validator.py                   # Validador pós-geração (compara métricas Antes vs Depois)
│   │   └── engine.py                      # Orquestrador central (Layers 1 a 5)
│   ├── presets/
│   │   └── desert_presets.py              # 8 Presets Multi-Bioma (Desertos, Montanhas Verdes, Vales, Savanas, Fantasia)
│   └── ui/
│       ├── properties.py                  # Sliders em tempo real para Terreno, Estradas, Casas, Props, Rochas e Decals
│       ├── operators.py                   # Operadores: Gerar Cenário, Popular Casas/Props, Limpar Objetos, Curva 3D, Rollback
│       └── panels.py                      # Painéis N-Panel ('View3D > Sidebar (N) > ProcEnv')
├── scripts/
│   ├── run_v0_desert.py                   # Script standalone pronto para correr no Text Editor do Blender
│   └── build_addon_zip.py                 # Gera o ficheiro .zip instalável do Add-on
└── tests/
    └── test_engine_logic.py               # Suite de testes (CP-01 a CP-04)
```

---

## 2. O Que o Motor Faz (`CP-04`)

1. **Multi-Bioma & Relevo Variado (`Layer 3 + Layer 4`)**:
   - **🏜️ Desertos em Teia / Rio (`DESERT`)**: Dunas ramificadas (`Voronoi SMOOTH_F1` em 2 octaves), perfil suave (`SIN`, zero paredes verticais) e suavização topológica (`Blur Attribute`).
   - **🏔️ Montanhas Verdes (`MOUNTAIN_ALPINE`) & 🌿 Vales (`LUSH_VALLEY`)**: Picos rochosos com **Rocha Automática nas Encostas Íngremes (`PROC_SlopeRockMask`)**, relva verde e musgo húmido nos vales.
   - **🦁 Savanas & Explanadas (`SAVANNA_PLAINS`)**: Grandes explanadas com planaltos de topo achatado (`Plateau Strength`), capim dourado e terra vermelha.
   - **✨ Paisagens Fantasiosas (`FANTASY_LANDSCAPE`)**: Terraços esculpidos (`Terraces`), musgo esmeralda e rocha basáltica.
2. **Criador Universal de Estradas & Caminhos (`2. Criador de Estradas & Caminhos`)**:
   - Contorna, achata e alisa automaticamente o relevo ao longo de um caminho sinuoso procedural (com opção de **Bifurcação em Y**) ou seguindo uma **Curva 3D (`PROC_ENV_Road_Curve`)**, e pinta automaticamente o leito da estrada no shader via atributo `proc_road_mask`.
3. **Cenários Pré-Prontos: Casas Procedurais, Props, Rochas, Vegetação & Decals (`3. Casas Procedurais, Props, Rochas & Decals — Layer 5`)**:
   - **🏠 Casas & Edifícios Procedurais (`PROC_ENV_BUILDINGS`)**: 4 estilos arquitetónicos (`Vila de Adobe`, `Chalé Alpino / Medieval`, `Cabanas de Savana`, `Torres Fantasia`) com fundação de pedra anti-flutuação, agrupadas em aldeias ao longo das margens da estrada sem bloquear o caminho.
   - **🏮 Props de Estrada & Vila (`PROC_ENV_PROPS`)**: Postes de lanterna com luz emissiva, pilares de pedra e caixas distribuídos nas bermas da estrada.
   - **🪨 Rochas (`PROC_ENV_ROCKS`), 🌲 Vegetação do Bioma (`PROC_ENV_VEGETATION`) e 💠 Decals (`PROC_ENV_DECALS`)**: Pinheiros, acácias de savana, cactos/palmeiras, rochedos e lajes/musgo/areia alinhados à normal exata do terreno.
