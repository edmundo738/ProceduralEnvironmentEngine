# Caso de Validação V0 — Cena Desértica em Blender 5.2.1 LTS

## 1. Separação Epistemológica do Estado Inicial

### FACT (Medido Diretamente na Cena)
- **Versão**: Blender `5.2.1 LTS`, Render Engine `Cycles` (`1920 × 1080`, `100%`), Unidades `Metric` (`Scale = 1.0`).
- **Terreno (`Plane`)**:
  - Dimensões: `X = 590.212 m`, `Y = 833.532 m`, `Z = 38.429 m` (Área $\approx 0.492\text{ km}^2$).
  - Bounds locais: `X: -298.197 → 293.278`, `Y: -413.111 → 422.327`, `Z: -1.810 → 37.186`.
  - Geometria base: `1,329,352` vértices, `2,656,408` arestas, `1,327,057` polígonos.
  - UV Map: `UVMap`.
  - Modifiers ativos:
    1. `Geometry Nodes`
    2. `Subdivision` (`Viewport = 1`, `Render = 3`)
    3. `Displace` (`Strength = 0.1`, `Midlevel = 0.5`, `Texture = Texture`)
- **Material Atual (`Desert_Sand.001`)**:
  - Contém apenas 4 nodes: `Material Output`, `Principled BSDF`, `Noise Texture`, `Color Ramp`.
  - **Não utiliza** atualmente os mapas PBR 4K.
- **Mapas PBR 4K Armazenados no `.blend` (`bpy.data.images`)**:
  1. Diffuse: `red_sand_diff_4k.jpg.001` (`4096 × 4096`)
  2. Normal: `red_sand_nor_gl_4k.exr` (`4096 × 4096`)
  3. Roughness: `red_sand_rough_4k.exr` (`4096 × 4096`)
- **Outros Elementos**:
  - `Cone`: Dimensões `461.705 × 482.852 × 232.795 m`, `24` vértices, sem material.
  - `Light` (Sun): Posição `(20.594, 11.792, 120.144)`, Energy `504.95`, `World.001` com `Sky Texture`.
  - `Camera`: Posição `(0, 0, 0)`, Lens `50 mm`, Sensor `36 mm`.

### INFERRED (Deduções de Engenharia)
1. **Causa Matemática da Textura PBR Esticada (Situação A Histórica)**:
   - O `Plane` mede `590.212 m` em X por `833.532 m` em Y (rácio de aspeto `1 : 1.412`).
   - Quando um mapa 4K é ligado ao `UVMap` (`0..1`) sem compensação de escala métrica:
     - **Erro de Escala Absoluta**: Um único tile de areia é esticado por `833.5 metros` (1 pixel da textura 4K passa a cobrir $\approx 20.3\text{ cm}$ de terreno!).
     - **Erro de Proporção (Anisotropia)**: O eixo Y é esticado `41.2%` mais do que o eixo X (`833.532 / 590.212 = 1.4122`).
   - **Solução Definitiva no Layer 4 (`Surface Generator`)**:
     - Usar **Mapeamento Métrico Real** (`Tile Size = 2.5m a 4.0m`), onde cada repetição do mapa PBR 4K cobre exatamente `N × N metros` quadrados no mundo real, independentemente do tamanho ou rácio do `Plane`.
     - Ou, quando usado `UVMap`, multiplicar automaticamente `UV.x` por `Dim_X / Tile_Size` (`590.212 / 3.0 = 196.74`) e `UV.y` por `Dim_Y / Tile_Size` (`833.532 / 3.0 = 277.84`).
     - Adicionar **Anti-Tiling Procedural (Stochastic Dual-Scale Blending + Noise Offset)** para que a repetição de tiles de `3 m` num deserto de `834 m` não crie padrão de grelha visível à distância.
2. **Risco Crítico no Modifier `Subdivision (Render: 3)`**:
   - Como a malha já tem `1,327,057` polígonos, manter `Subdivision` com `Render = 3` multiplica os polígonos por $4^3 = 64$, resultando em $\approx 84.9\text{ milhões}$ de polígonos no momento do render Cycles.
   - A política padrão `ENHANCE_OPTIMIZE` desativa de forma reversível o `Subdivision` (guardando o estado original no snapshot) e utiliza os `1.33M` vértices existentes exclusivamente para a macro/média forma das dunas, delegando as micro-ondulações e grãos para o shader (Normal + Bump).

### UNKNOWN (Não Assumido)
- Função final do objeto `Cone` (`24` vértices): preservado intacto sem alterações até decisão do utilizador.
- Composição interna exata do modifier `Geometry Nodes` já presente no `Plane`: inspecionada dinamicamente pelo `SceneAnalyzer` durante a execução em tempo real no Blender.
