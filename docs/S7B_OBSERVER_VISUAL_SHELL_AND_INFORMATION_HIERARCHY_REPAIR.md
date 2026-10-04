# S7B_OBSERVER_VISUAL_SHELL_AND_INFORMATION_HIERARCHY_REPAIR

## Intent
Material visual/shell repair after S7 functional collapse: match reference **region placement** and optional **Aquatic Glass** chrome theme without inventing runtime ecology or decorating scientific views.

## Locks
```
AQUATIC_GLASS_THEME = YES
PHOTOREALISTIC_WORLD_BACKGROUND = NO
SCIENTIFIC_VIEW_DECORATION = NO
INVENTED_RUNTIME_VALUES = NO
REFERENCE_REGION_PLACEMENT_MUST_MATCH = YES
PIXEL_EXACT_COPY_REQUIRED = NO
RESPONSIVE_ADAPTATION_ALLOWED = YES
```

## Region placement (authoritative)
- TOP: single full-width `app-toolbar`
- LEFT: full-height `left-sidebar` observation nav
- CENTER: dominant scientific viewport
- RIGHT: contextual inspector (`observer-right-inspector`)
- BOTTOM: status/evidence drawer
- VIEWPORT OVERLAYS: compact mode/status only (WorldPane mode bar)

## Removed legacy placements
- second permanent toolbar row (`observation-nav-strip`)
- detached ControlDevice icon rail
- horizontal World/Organism/FPV/Hearing strip
- raw “Show left / Hide right / Hide bottom” cluster above viewport

## Theme
- `ThemePref` includes `aquatic`
- CSS tokens under `html[data-theme="aquatic"]` style **application chrome only**
- Scientific map stage uses light high-contrast canvas chrome via `resolvedWorldTheme` treating aquatic as light (no water/photo textures)

## Closure
See `results/s7b_observer_visual_shell_and_information_hierarchy_repair/FINAL_REPORT.md`.

## Non-goals
- No Beta 4.1
- No physics / cognition / S6 claim changes
