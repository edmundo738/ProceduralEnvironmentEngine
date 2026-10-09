# CHECKPOINT DE ENGENHARIA — PROCEDURAL ENVIRONMENT ENGINE

## 1. IDENTIFICAÇÃO DO CHECKPOINT

* **CHECKPOINT_ID**: `CP-04_COMPLETE_SCENARIO_HOUSES_PROPS_DECALS_ENGINE`
* **BRANCH**: `arena/01a10351-proceduralenvironmentengine`
* **VERSÃO DO ADD-ON**: `0.4.0` (`releases/procedural_environment_engine_v0.zip`)
* **TARGET_BLENDER**: `Blender 5.2.1 LTS` (Cycles, Metric, Scale `1.0`)

---

## 2. ESTADO DO PROJETO

### `PROJECT_STATE`
* Evolução do motor para um **Gerador Completo de Cenários Pré-Prontos (`Complete Scenario Generator — Layers 1 a 5`)**: além de esculpir terrenos multi-bioma e criar estradas/caminhos que alisam e contornam o relevo, o motor agora gera e distribui automaticamente **Casas Procedurais 3D (`PROC_ENV_BUILDINGS`)**, **Props de Estrada e Vila (`PROC_ENV_PROPS`)**, **Rochas e Penhascos 3D (`PROC_ENV_ROCKS`)**, **Vegetação do Bioma (`PROC_ENV_VEGETATION`)** e **Decals de Superfície e Estrada (`PROC_ENV_DECALS`)**, respeitando o corredor da estrada e assentando exatamente na superfície real do terreno.

### `HISTÓRICO DE CHECKPOINTS`
* **CP-00**: Inspeção completa da cena real em Blender 5.2.1 LTS (`Plane` 590×834m, 1.33M vértices, 3 mapas PBR 4K).
* **CP-01**: Implementação do Terrain Engine V0 (Scene Analyzer + Context Interpreter + Dunas V0 + PBR 4K Anti-Stretching).
* **CP-02**: Validação do teste real do utilizador $\rightarrow$ eliminação das paredes verticais (`SAW` $\rightarrow$ `SIN`), projeção 2D horizontal `(X,Y,0)`, rede de ramificações tipo árvore/rio/teia (`Voronoi SMOOTH_F1` em 2 octaves), suavização topológica (`Blur Attribute` + `Shade Smooth`) e desbloqueio total dos intervalos dos sliders (Escala até `500.0`).
* **CP-03**: Construção do **Criador Universal de Estradas & Caminhos** + **Sistema Multi-Bioma e Deformações Variadas (Montanhas Verdes, Musgo/Pedras/Relva, Savanas/Explanadas e Paisagens Fantasiosas para Jogos)**.
* **CP-04 (Atual)**: Construção do **Layer 5 — Gerador de Cenários Pré-Prontos com Casas Procedurais, Props, Rochas, Vegetação e Decals (`EnvironmentGenerator`)** + novo painel N-Panel **`3. Casas Procedurais, Props, Rochas & Decals (Layer 5)`**.

---

## 3. O QUE FOI IMPLEMENTADO NO `CP-04` (`V0.4`)

### A. Casas & Edifícios Procedurais 3D (`PROC_ENV_BUILDINGS`)
1. **4 Estilos Arquitetónicos + Modo Automático por Bioma (`AUTO_BIOME`)**:
   * **Vila de Adobe / Deserto (`DESERT_ADOBE`)**: Casas de adobe com terraço plano, parapeitos, porta recuada, vigas de madeira aparentes e fundação de pedra.
   * **Chalé Alpino / Medieval (`MEDIEVAL_MOUNTAIN`)**: Casas com paredes de madeira/pedra, telhado inclinado de duas águas com beirais e chaminé de pedra lateral.
   * **Cabanas de Savana (`SAVANNA_VILLAGE`)**: Cabanas cilíndricas sobre plinto de pedra com telhado cónico de colmo em camadas.
   * **Torres & Templos Fantasia (`FANTASY_TOWER`)**: Torres octogonais esguias com secção superior alargada e pináculo aguçado.
2. **Assentamento Inteligente & Aldeias junto à Estrada**:
   * Todas as casas incluem uma **base/fundação de pedra (`plinth`)** que penetra no subsolo para que nenhuma casa fique a flutuar em terrenos inclinados.
   * As casas agrupam-se em **pequenas vilas/aldeias (`Agrupamento em Vila`)** ao longo das margens da estrada, orientadas para o caminho, **sem nunca bloquear o leito da estrada**.

### B. Props de Estrada & Vila (`PROC_ENV_PROPS`)
* **Postes de Lanterna com Luz Emissiva (`Lantern Post`)**: Postes de madeira com braço suspenso e lanterna brilhante (`Emission Strength`) distribuídos regularmente ao longo das bermas da estrada.
* **Pilares / Marcos de Caminho (`Ruined Pillar`)** e **Caixas / Suprimentos (`Crate Cluster`)** posicionados junto às estradas e casas.

### C. Rochas 3D (`PROC_ENV_ROCKS`), Vegetação (`PROC_ENV_VEGETATION`) & Decals (`PROC_ENV_DECALS`)
* **Rochas e Penhascos 3D**: Malhas poliédricas irregulares distribuídas nas encostas e afloramentos rochosos.
* **Vegetação adaptada ao Bioma**:
  * **Montanha / Vale**: Pinheiros alpinos em camadas (`Alpine Pine`) + arbustos.
  * **Savana**: Acácias de copa achatada (`Savanna Flat-Top Acacia`) + tufos de vegetação.
  * **Deserto**: Cactos Saguaro com braços (`Desert Cactus`) + vegetação de oásis.
* **Decals de Chão & Estrada (`PROC_ENV_DECALS`)**: Lajes de pedra partidas, manchas de musgo e acumulações de areia alinhadas automaticamente à normal da superfície (`_euler_from_normal`).

---

## 4. SEPARAÇÃO EPISTEMOLÓGICA (`CP-04`)

* **`FACT`**:
  * `6/6` testes automatizados em `tests/test_engine_logic.py` passaram (`OK`), incluindo o novo teste `test_cp04_complete_scenario_houses_props_rocks_decals` que valida a geração de casas, props, rochas, vegetação e decals em todos os biomas e a limpeza reversível das coleções `PROC_ENV_BUILDINGS`, `PROC_ENV_PROPS` e `PROC_ENV_DECALS`.
  * O pacote `releases/procedural_environment_engine_v0.zip` (`70.5 KB`, versão `0.4.0`) foi compilado e enviado para o GitHub.
* **`UNKNOWN` (`NOT TESTED IN LIVE VIEWPORT YET`)**:
  * Validação visual direta no teu Blender 5.2.1 LTS da distribuição 3D das casas procedurais, postes de lanterna, rochas, árvores e decals sobre o terreno avaliado.

---

## 5. PRÓXIMA AÇÃO (`NEXT ACTION`)

1. Baixar o novo `releases/procedural_environment_engine_v0.zip` (`V0.4 - CP-04`) do GitHub e instalar no Blender.
2. Clicar em **`1-CLICK: GERAR CENÁRIO / APLICAR PRESET`** (que agora cria Terreno + Estrada + Casas + Props + Rochas + Vegetação + Decals) ou usar o novo painel **`3. Casas Procedurais, Props, Rochas & Decals (Layer 5)`** para regenerar/ajustar a quantidade e escala das casas, postes, árvores, pedras e decals!
