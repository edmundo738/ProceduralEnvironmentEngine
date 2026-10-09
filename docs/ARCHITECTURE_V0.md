# Procedural Environment Engine — Arquitetura e Especificação Técnica (V0)

## 1. Visão do Produto

O **Procedural Environment Engine (`ProcEnv`)** é um sistema autónomo de análise, construção e transformação de cenários procedurais para **Blender 5.2+ LTS**.

O sistema opera sob quatro pilares fundamentais:
1. **ENTENDER (`Layer 1: Scene Analyzer`)**: Medir e inventariar o que já existe na cena real sem suposições.
2. **INTERPRETAR (`Layer 2: Context Interpreter`)**: Separar `FACT`, `INFERRED` e `UNKNOWN`, distinguindo `EXISTS`, `INCOMPLETE`, `MISSING` e `CONFLICTING`.
3. **CONSTRUIR & APROVEITAR (`Layers 3–4: Terrain & Surface Generators`)**: Reutilizar recursos existentes (malhas, mapas PBR 4K, iluminação) e construir o que falta de forma parametrizada e controlada.
4. **REVERTER (`State & Snapshot Manager`)**: Garantir que nenhuma operação destrói trabalho existente irreversivelmente.

---

## 2. Metodologia Epistemológica do Motor

Todas as análises e diagnósticos produzidos pelo motor classificam as afirmações em três categorias estritas:

- **`FACT`**: Medido diretamente através da API `bpy` (ex: dimensões `590.212 × 833.532 m`, `1,329,352` vértices base, `3` imagens PBR 4K presentes em `bpy.data.images`, `0` nós de imagem conectados ao material `Desert_Sand.001`).
- **`INFERRED`**: Dedução técnica baseada em métricas (ex: aplicar `Subdivision Render = 3` sobre `1,327,057` polígonos multiplicará a malha por $4^3 = 64\times \approx 84.9\text{M}$ polígonos; mapear UV `0–1` sem escala métrica num plano de `590 × 834 m` estica cada textura ao longo de centenas de metros e com distorção de proporção `1 : 1.412`).
- **`UNKNOWN`**: O que ainda não foi validado visualmente ou cujo papel semântico não está classificado (ex: função final do objeto `Cone` com 24 vértices e escala `~66×60×59`). **Regra de ouro**: `UNKNOWN ≠ FALSE` e `NOT TESTED ≠ PASS`.

---

## 3. Arquitetura em 7 Camadas

```text
USER INTENT (Auto / Guided / Manual + Seed + Preset)
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ LAYER 1 — SCENE ANALYZER                                 │
│  • Mede objetos, bounds, vértices base vs avaliados, UVs │
│  • Inventaria Modifiers, Geometry Nodes, Materiais e PBR │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ LAYER 2 — CONTEXT INTERPRETER                            │
│  • Classifica: EXISTS / INCOMPLETE / MISSING / UNKNOWN   │
│  • Deteta riscos de performance e stretching de textura  │
│  • Propõe estratégia (Enhance/Optimize, Keep, Replace)   │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ STATE MANAGER (REVERSIBILIDADE)                          │
│  • Guarda Snapshot JSON na cena + Backup de Materiais    │
│  • Permite Rollback de 1-clique para o estado original   │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ LAYER 3 — TERRAIN GENERATOR (V0: DUNAS PROCEDURAIS)      │
│  • Geometry Nodes multi-escala (Macro Bacias + Dunas     │
│    Direcionais com Domain Warping + Ondulação Média)     │
│  • Opera em coordenadas métricas reais sem explodir malha│
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ LAYER 4 — SURFACE GENERATOR (V0: AREIA + PBR 4K)         │
│  • Variação Procedural Macro, Média e Micro (Ripples)    │
│  • Reintegração das PBR 4K (Diffuse, Normal, Roughness)  │
│  • Mapeamento Métrico Real + Anti-Tiling (Zero Stretch)  │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ LAYERS 5, 6, 7 — ENVIRONMENT, LIGHTING & CAMERA (Fases)  │
│  • Distribuição espacial de rochas/vegetação, Sol/Sky,   │
│    Câmera cinematográfica                                │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ VALIDATOR                                                │
│  • Compara métricas Antes vs Depois e gera Relatório     │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Políticas de Reutilização e Conflito (`ConflictStrategy`)

Quando o utilizador entrega uma cena já iniciada (Modo B — *Analyze and Build*), o sistema oferece 4 modos de atuação:

1. **`ENHANCE_OPTIMIZE` (Aprimorar & Otimizar — Padrão Inteligente)**:
   - Reutiliza o terreno principal (`Plane`) e os mapas PBR 4K encontrados no ficheiro `.blend`.
   - Desativa de forma reversível modificadores redundantes ou perigosos (ex: `Subdivision` com `Render = 3` numa malha que já possui `1,33M` vértices, evitando crash de memória).
   - Preserva uma fração configurável do relevo existente (`Existing Relief Keep`) e adiciona o sistema `PROC_ENV_Terrain` (Geometry Nodes) para as dunas procedurais.
   - Faz backup do material anterior (`Desert_Sand.001_PROC_BACKUP`) e constrói o shader híbrido Procedural + PBR 4K.
2. **`KEEP_AND_STACK` (Manter Tudo & Empilhar)**:
   - Não altera a visibilidade de nenhum modifier existente; apenas anexa o modifier de dunas e atualiza o material.
3. **`CLEAN_REPLACE` (Substituição Limpa Reversível)**:
   - Silencia (`show_viewport = False`, `show_render = False`) todos os modifiers anteriores no terreno (guardando o estado no snapshot) para que apenas o motor `PROC_ENV` governe a forma.
4. **`CREATE_NEW` (Gerar Novo Terreno do Zero — Modo A)**:
   - Cria uma nova malha otimizada na coleção `PROC_ENV/TERRAIN` sem tocar nos objetos existentes.
