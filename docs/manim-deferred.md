# Deferred Manim animation ideas (Layer 5)

Ideas catalogued from the 3blue1brown `videos/` archive that were **deliberately
not migrated** into `app/services/manim/`. They either need 3D rendering, an
OpenGL-only feature of `manimgl`, external assets/models, or per-video manual
work that cannot be parameterized behind a JSON scene spec.

Revisit an item only when its blocker below is resolved.

| Idea | 3b1b source | Why deferred |
|------|-------------|--------------|
| Pi creatures (expressive mascot reacting to the math) | `custom/characters/pi_creature.py` | Hand-drawn SVG rig with per-video choreography; no ManimCE port and no way for the LLM spec to drive expressions meaningfully |
| Mug-to-torus morph (topology intro) | `_2018/uncertainty.py` and shorts | Requires 3D `Surface` rendering plus camera orbits; our pipeline renders 2D Cairo scenes in a portrait frame |
| OpenGL shader effects (glow, refraction, vector-field flow textures) | `custom/shaders/`, `_2020/shadows.py` | `manimgl`-only shader pipeline; ManimCE's Cairo renderer has no shader support |
| Live GPT-2 attention/logit demo | `_2024/transformers/ml_basics.py` | Depends on a running language model and tensor dumps; not reproducible inside a render subprocess |
| Patron name scroll animations | end-cards across most videos | Marketing artifact tied to 3b1b's patron list; irrelevant to generated explainers |
| Image pixel-loop effects (photo dissolves into moving pixels) | `_2017/waves.py` end cards | Needs raster image assets per topic; our specs are text/geometry only |
| 4D butterfly / quaternion rotations | `_2018/quaternions.py` | Interactive 3D (originally WebGL); flattening to 2D loses the entire point |
| Raster region painting (Mandelbrot/Newton pixel escapes) | `_2021/newton_fractal.py` | Per-pixel shader iteration; a Cairo `VMobject` version is orders of magnitude too slow at render time. The 1-D caricature shipped as the `newton_basins` niche segment instead |

## Related but shipped

Several deferred-looking ideas did make it in, in reduced 2D form — see
`app/services/manim/segments/niche/` (`newton_basins`, `fractal_zoom`,
`collision_pi`, `galton_board`) and `catalog.yaml` for their topic-gating
keywords.
