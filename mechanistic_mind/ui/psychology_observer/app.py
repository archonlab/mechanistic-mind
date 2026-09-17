from __future__ import annotations

import json
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import numpy as np

from .controller import (
    OBSTACLE_CONDITIONS,
    MEMORY_ARCHITECTURES,
    PERSISTENT_CONDITIONS,
    RESOURCE_LAYOUTS,
    WORLD_MODES,
    PsychologyLaunchSpec,
    PsychologyObserverController,
)
from .model import (
    PsychologyTickView,
)
from .map_view import CanvasWorldRenderer, selection_snapshot
from .planet_model import FIELD_LAYERS, assert_read_only_surface
from .planet_session import PlanetInspectionSession
from .legacy_mode import (
    LEGACY_MODE_OFF_STATUS,
    LEGACY_MODE_ON_STATUS,
    can_disable_legacy_mode,
    logical_active_legacy_experiment,
    snapshot as legacy_mode_snapshot,
)
from .planet_setup import (
    FIXTURE_IDS,
    FIXTURE_LABELS,
    CurrentPhysicalWorldSetup,
    apply_current_setup,
    fixture_label,
    list_fixture_ids,
)
from .planet_view import PlanetFieldRenderer, format_cell_inspector_text, world_and_boundary_text
from .theme import (
    ThemeMode,
    detect_system_scheme,
    palette_for,
    resolve_scheme,
)


class PsychologyObserverApp:
    """Standalone Mechanistic Mind Psychology Observer application."""

    LEFT_PANEL_INITIAL_WIDTH = 360
    LEFT_PANEL_MIN_WIDTH = 240
    MAIN_PANEL_MIN_WIDTH = 760
    MAP_PANEL_MIN_HEIGHT = 260
    TIMELINE_PANEL_MIN_HEIGHT = 90
    PROSPECTIVE_PRESETS = (
        "Integrated Psyche v1",
        "4.11 Prospective Self-State",
        "4.12 Transition Composition",
        "4.12.1 Missing-Link Acquisition",
        "4.12.2 Same Present / Different History",
        "4.13 Expectation × Prediction Violation",
        "4.13.1 Expectation Adaptation / Alternating",
        "4.14 Multiple Acquired Consequences",
        "4.15 Prospective Continuity",
        "4.16 Persistent Prospective Trace",
        "4.17 Persistent Expectation × Fresh Prediction Conflict",
        "4.18 Composed Future Value",
        "4.18.1 Prospective Space Development",
        "4.18.2 Dynamic Sustaining Ecology",
        "4.19 Context Formation",
        "4.20 Hierarchical Body Prediction",
        "4.21 Predictive Compression",
        "4.22 Multi-Scale Predictive Organization",
        "4.23 Prospective Trajectory Composition",
        "4.24 Endogenous Temporal Reference",
        "4.25 Instrumental Observation",
        "4.26 Prospective Consequence Influence",
        "4.27 Predictive Generalization",
        "4.28 Predictive Scenario Competition",
        "4.29 Predictive Reliability",
        "4.30 Unavoidable State Transition",
        "4.31 Evidence-Producing Physical Action",
        "4.32 Learning-Mediated Futures",
        "4.33 Conditional Prospection",
        "4.34 Multimodal Consequence Learning",
        "4.35 Predictive Structure Selection",
        "4.36 Predictive Representation Sufficiency",
        "4.37 Contingent Physical Futures",
        "4.38 Psyche Incubation",
        "4.39 Sensorimotor Dynamics",
        "4.40 Endogenous Predictive Signaling",
        "4.41 Acquired Internal Dynamics",
        "4.42 Body-Coupled Development",
        "4.43 Distal Consequence",
        "4.44 Body × Acquired Dynamics",
        "4.45 World–Body Biography",
        "4.46 Acquired Sensorimotor Coupling",
        "4.47 Endogenous Motor Access",
        "4.48 Endogenous Dynamic Range",
        "4.49 Ordinary Physical Excitation",
        "4.50 World → Body → Motor Access",
        "4.51 Default Runtime Body Access",
        "4.52 Early Physical Ecology",
        "4.53 Matched Motor History",
        "4.54 Ordinary Physical Ecology Diagnostic",
        "4.55 Existing Physiology Compatibility",
        "4.56 Generic Physical Transduction",
        "4.57 Motor Pathway Archaeology",
        "4.58 Action Space Compatibility",
        "4.59 Generic Physical Effector",
        "4.60 Arbitrary Physical Coupling",
        "4.61 Live Operating Range",
        "4.62 Amplitude Budget",
        "4.63 Existing Physical Ecology",
        "4.64 WORLD→BODY Audit",
        "4.65 Minimal Passive Physical Exchange",
        "4.66 Frozen Physical Composition",
        "4.67 Physical DOF Access Audit",
        "4.68 Persistent Process Provenance",
        "4.69 Frozen Physical Composition",
        "4.70 Generic Action Body Internal Return",
        "4.71 Post-Consequence Relaxation and Latent Return",
        "4.72 State-Dependent Physical Consequence",
        "4.73 Physical Intervention vs Non-Intervention",
        "4.74 Body-Response-Consequence Acquisition Archaeology",
        "4.75 Response-Contingent Internal Transition Acquisition",
        "4.76 Acquired Transition Reinstatement",
    )

    def __init__(
        self,
        root: tk.Tk,
        controller: PsychologyObserverController,
        *,
        initial_theme: ThemeMode = ThemeMode.SYSTEM,
    ) -> None:
        self.root = root
        self.controller = controller
        self.theme_mode = initial_theme
        self.scheme = resolve_scheme(
            initial_theme,
            system_scheme=detect_system_scheme(),
        )
        self.palette = palette_for(self.scheme)
        self._semantic: list[tuple[tk.Misc, dict[str, str]]] = []

        self.last_tick_count = 0
        self._last_event_keys: set[str] = set()

        self.ticks_var = tk.IntVar(value=120)
        self.seed_var = tk.IntVar(value=17)
        self.world_var = tk.StringVar(value="contextual-objects")
        self.obstacle_condition_var = tk.StringVar(value="HAZARD")
        self.persistent_condition_var = tk.StringVar(value="BROKEN")
        self.layout_var = tk.StringVar(value="distributed")
        self.random_rate_var = tk.DoubleVar(value=0.0)
        self.world_dynamics_var = tk.StringVar(value="STATIC_WORLD")
        self.perception_mode_var = tk.StringVar(value="CONTACT_ONLY")
        self.cue_mode_var = tk.StringVar(value="LEGACY_CUE_ONLY")
        self.ecology_condition_var = tk.StringVar(value="DYNAMIC_SIGNAL")
        self.resistance_mode_var = tk.StringVar(value="OVERCOMEABLE")
        self.prospective_preset_var = tk.StringVar(
            value="4.12.2 Same Present / Different History"
        )
        # UI memory only — not logically active unless legacy_mode_enabled.
        self.legacy_mode_enabled = tk.BooleanVar(value=False)
        self.legacy_mode_status_var = tk.StringVar(value=LEGACY_MODE_OFF_STATUS)
        self.memory_architecture_var = tk.StringVar(
            value="BOUNDED_COMPRESSED"
        )
        self.world_badge_var = tk.StringVar(value="CURRENT MM")
        self.theme_var = tk.StringVar(value=initial_theme.value)
        self.agent_var = tk.StringVar(value="A001")
        self.status_var = tk.StringVar(value="IDLE")
        self.run_var = tk.StringVar(value="No run")
        self.path_var = tk.StringVar(value="results/psychology_observer")
        self.model_status_var = tk.StringVar(value="PhysicalSystemRuntime • WORLD + BODY + INTERNAL")
        self.truth_overlay_var = tk.BooleanVar(value=True)
        self.memory_overlay_var = tk.BooleanVar(value=True)
        self.follow_agent_var = tk.BooleanVar(value=False)
        self.map_renderer = CanvasWorldRenderer()
        self.view_mode_var = tk.StringVar(value="physical_world")
        self.mode_selector_var = tk.StringVar(value="Current MM")
        self.planet_layer_var = tk.StringVar(value="M0")
        self.planet_boundary_overlay_var = tk.BooleanVar(value=True)
        self.planet_session = PlanetInspectionSession(seed=17)
        self.planet_seed_var = tk.IntVar(value=17)
        self.planet_boundary_fixture_var = tk.StringVar(value="off")
        self.planet_renderer = PlanetFieldRenderer()
        self._planet_running = False
        self._planet_after_id = None
        self._planet_last_render = 0.0
        self._planet_render_interval_s = 0.05  # ~20 Hz display cadence (UX)\n        self.planet_sim_speed_var = tk.DoubleVar(value=1.0)  # sim steps multiplier vs display
        self._planet_batch_wall_ms = 12.0  # bound work per after() callback
        self._planet_batch_max_ticks = 48
        self._planet_run_error = None
        self._planet_last_saved_key: tuple[int, int] | None = None
        self._planet_last_saved_dir = None
        self._current_agent_trail: list[tuple[float, float]] = []
        self.planet_run_status_var = tk.StringVar(value="Current MM: paused")
        self.planet_lifecycle_var = tk.StringVar(value="UNCONFIGURED")
        self._map_drag_origin: tuple[int, int] | None = None
        self._map_dragged = False
        self.timeline_visible = True
        self._timeline_height = 300
        self._development_poll_counter = 0

        root.title("Mechanistic Mind Psychology Observer 0.4.0")
        root.geometry("1740x980")
        root.minsize(1320, 800)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.style = ttk.Style(root)
        self.style.theme_use("clam")

        self._build_topbar()
        self._build_body()
        self._build_footer()
        self._apply_theme()
        self._timeline_hidden_by_view = False
        self._organism_right_sections = []
        self._organism_right_headers = []
        self._planet_right_sections = []
        self._planet_right_headers = []
        self._planet_map_controls = []
        self._organism_map_controls = []
        self.root.after(80, self._poll)
        self.root.after(120, self._register_view_chrome)
        self.root.after(180, self._bootstrap_current_physical_world)

    # ---------- common widgets ----------

    def _reg(self, widget: tk.Misc, **tokens: str):
        self._semantic.append((widget, tokens))
        return widget

    def _frame(self, parent, surface="surface.app"):
        return self._reg(
            tk.Frame(parent, borderwidth=0),
            background=surface,
        )

    def _label(
        self,
        parent,
        text="",
        *,
        surface="surface.app",
        foreground="text.primary",
        font=("TkDefaultFont", 9),
        textvariable=None,
        anchor="w",
        justify="left",
    ):
        return self._reg(
            tk.Label(
                parent,
                text=text,
                textvariable=textvariable,
                borderwidth=0,
                font=font,
                anchor=anchor,
                justify=justify,
            ),
            background=surface,
            foreground=foreground,
        )

    def _button(self, parent, text, command, kind="neutral"):
        mapping = {
            "neutral": (
                "surface.control",
                "text.primary",
                "surface.elevated",
                "text.primary",
            ),
            "primary": (
                "action.primary",
                "text.inverse",
                "action.primary_hover",
                "text.inverse",
            ),
            "danger": (
                "action.danger",
                "text.inverse",
                "action.danger_hover",
                "text.inverse",
            ),
        }
        bg, fg, abg, afg = mapping[kind]
        return self._reg(
            tk.Button(
                parent,
                text=text,
                command=command,
                borderwidth=0,
                relief="flat",
                padx=12,
                pady=8,
                font=("TkDefaultFont", 10, "bold"),
                cursor="hand2",
            ),
            background=bg,
            foreground=fg,
            activebackground=abg,
            activeforeground=afg,
            disabledforeground="text.muted",
            highlightbackground=bg,
            highlightcolor="focus.ring",
        )

    def _section(self, parent, text):
        label = self._label(
            parent,
            text,
            surface="surface.navigation",
            foreground="text.muted",
            font=("TkDefaultFont", 8, "bold"),
        )
        label.pack(anchor="w", padx=14, pady=(12, 5))
        return label


    def _safe_text(self, parent, height=12, **kw):
        """Create a wrap-safe Text panel that cannot force horizontal page growth."""
        fr = tk.Frame(parent, borderwidth=0)
        fr.pack(fill="both", expand=True)
        # min-width 0 analogue: let paned children shrink
        try:
            fr.pack_propagate(True)
        except Exception:
            pass
        widget = tk.Text(
            fr,
            height=height,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
            **kw,
        )
        self._reg(
            widget,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        widget.pack(fill="both", expand=True)
        # soft-wrap long tokens
        try:
            widget.configure(wrap="word")
        except Exception:
            pass
        return widget

    def _set_safe(self, widget, text: str) -> None:
        if widget is None:
            return
        # Insert with zero-width spaces after separators to encourage wrap of long IDs
        safe = (
            str(text)
            .replace("||", "||​")
            .replace("→", "→​")
            .replace("/", "/​")
        )
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", safe)
        widget.configure(state="disabled")


    def _kv_card(self, parent, keys):
        card = self._frame(parent, "surface.card")
        card.pack(fill="x", padx=12)
        values = {}
        for key in keys:
            row = self._frame(card, "surface.card")
            row.pack(fill="x", padx=9, pady=1)
            self._label(
                row,
                key.upper(),
                surface="surface.card",
                foreground="text.muted",
                font=("TkDefaultFont", 7, "bold"),
            ).pack(side="left")
            value = self._label(
                row,
                "—",
                surface="surface.card",
                foreground="text.primary",
                font=("TkFixedFont", 8, "bold"),
                anchor="e",
            )
            value.pack(side="right")
            values[key] = value
        return values

    # ---------- layout ----------

    def _build_topbar(self):
        bar = self._frame(self.root, "surface.navigation")
        bar.grid(row=0, column=0, sticky="ew")
        bar.configure(height=58)
        bar.pack_propagate(False)

        self._label(
            bar,
            "⬡  Mechanistic Mind Psychology Observer",
            surface="surface.navigation",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(side="left", padx=(16, 16), fill="y")

        self._label(
            bar,
            textvariable=self.world_badge_var,
            surface="surface.navigation",
            foreground="chart.1",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(side="left", padx=6, fill="y")

        self.model_status_label = self._label(
            bar,
            textvariable=self.model_status_var,
            surface="surface.navigation",
            foreground="status.info",
            font=("TkDefaultFont", 9, "bold"),
        )
        self.model_status_label.pack(side="left", padx=18, fill="y")

        self.view_mode_combo = ttk.Combobox(
            bar,
            textvariable=self.mode_selector_var,
            values=("Current MM", "Legacy Experiments"),
            state="readonly",
            width=18,
        )
        self.view_mode_combo.pack(side="left", padx=(8, 4), pady=12)
        self.view_mode_combo.bind("<<ComboboxSelected>>", self._mode_selector_changed)
        self._label(
            bar,
            "Mode",
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        ).pack(side="left")

        combo = ttk.Combobox(
            bar,
            textvariable=self.theme_var,
            values=tuple(item.value for item in ThemeMode),
            state="readonly",
            width=8,
        )
        combo.pack(side="right", padx=(4, 14), pady=12)
        combo.bind("<<ComboboxSelected>>", self._theme_changed)

        self._label(
            bar,
            "Theme",
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        ).pack(side="right")

        # Update 4.7: thin psyche selector (A/B). Does not invent social UI.
        self.agent_combo = ttk.Combobox(
            bar,
            textvariable=self.agent_var,
            values=("A001",),
            state="readonly",
            width=8,
        )
        self.agent_combo.pack(side="right", padx=(4, 10), pady=12)
        self.agent_combo.bind("<<ComboboxSelected>>", self._agent_changed)
        self._agent_label = self._label(
            bar,
            "Agent",
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        )
        self._agent_label.pack(side="right")

    def _build_body(self):
        body = self._reg(
            tk.PanedWindow(
                self.root,
                orient=tk.HORIZONTAL,
                borderwidth=0,
                sashwidth=9,
                sashpad=1,
                sashrelief="flat",
                showhandle=True,
                handlesize=8,
                handlepad=28,
                opaqueresize=True,
                cursor="sb_h_double_arrow",
            ),
            background="border.default",
        )
        body.grid(row=1, column=0, sticky="nsew")
        self.body_splitter = body

        self.left = self._frame(body, "surface.navigation")
        self.left.configure(width=self.LEFT_PANEL_INITIAL_WIDTH)

        main = self._frame(body, "surface.app")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        center = self._reg(
            tk.PanedWindow(
                main,
                orient=tk.VERTICAL,
                borderwidth=0,
                sashwidth=9,
                sashpad=1,
                sashrelief="flat",
                showhandle=True,
                handlesize=8,
                handlepad=28,
                opaqueresize=True,
                cursor="sb_v_double_arrow",
            ),
            background="border.default",
        )
        center.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.center_splitter = center

        self.right = self._frame(main, "surface.navigation")
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.configure(width=500)
        self.right.grid_propagate(False)

        body.add(
            self.left,
            width=self.LEFT_PANEL_INITIAL_WIDTH,
            minsize=self.LEFT_PANEL_MIN_WIDTH,
            stretch="never",
        )
        body.add(
            main,
            minsize=self.MAIN_PANEL_MIN_WIDTH,
            stretch="always",
        )

        self._build_left()
        self._build_map(center)
        self._build_timeline(center)
        self._build_right()

    def _build_left(self):
        # MM-CONFIG-1: Current Physical World setup (shown in physical_world view)
        self.current_setup_header = self._label(
            self.left,
            "CURRENT MM — ONE PHYSICAL SYSTEM",
            surface="surface.navigation",
            foreground="text.muted",
            font=("TkDefaultFont", 8, "bold"),
        )
        self.current_setup_header.pack(anchor="w", padx=14, pady=(12, 5))
        current = self._frame(self.left, "surface.navigation")
        current.pack(fill="x", padx=12)
        self.current_setup_frame = current
        self.planet_seed_entry = self._compact_entry(
            current, "Planet seed", self.planet_seed_var
        )
        fixture_values = [f"{fid} — {FIXTURE_LABELS[fid]}" for fid in FIXTURE_IDS]
        self.planet_fixture_var_display = tk.StringVar(
            value=f"off — {FIXTURE_LABELS['off']}"
        )
        self.planet_fixture_combo = self._compact_combo(
            current,
            "Boundary fixture",
            self.planet_fixture_var_display,
            fixture_values,
        )
        self.planet_fixture_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._sync_fixture_id_from_display()
        )
        apply_row = self._frame(current, "surface.navigation")
        apply_row.pack(fill="x", pady=(6, 2))
        self.planet_apply_setup_button = self._button(
            apply_row, "Apply setup", self._apply_current_planet_setup, "primary"
        )
        self.planet_apply_setup_button.pack(side="left", fill="x", expand=True)
        run_row = self._frame(current, "surface.navigation")
        run_row.pack(fill="x", pady=(8, 2))
        self._label(
            run_row,
            "RUN",
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 8, "bold"),
        ).pack(anchor="w")
        run_btns = self._frame(current, "surface.navigation")
        run_btns.pack(fill="x", pady=(2, 2))
        self.current_pw_run_button = self._button(
            run_btns, "Run", self._planet_run, "primary"
        )
        self.current_pw_run_button.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.current_pw_pause_button = self._button(run_btns, "Pause", self._planet_pause)
        self.current_pw_pause_button.pack(side="left", fill="x", expand=True, padx=2)
        self.current_pw_stop_button = self._button(
            run_btns, "Stop", self._planet_stop, "danger"
        )
        self.current_pw_stop_button.pack(side="left", fill="x", expand=True, padx=2)
        self.current_pw_step_button = self._button(run_btns, "Step", self._planet_step)
        self.current_pw_step_button.pack(side="left", fill="x", expand=True, padx=2)
        self.current_pw_reset_button = self._button(run_btns, "Reset", self._planet_reset)
        self.current_pw_reset_button.pack(side="left", fill="x", expand=True, padx=(2, 0))
        self.planet_lifecycle_label = self._label(
            current,
            textvariable=self.planet_lifecycle_var,
            surface="surface.navigation",
            foreground="status.info",
            font=("TkDefaultFont", 9, "bold"),
        )
        self.planet_lifecycle_label.pack(anchor="w", pady=(6, 2))
        self.planet_setup_provenance = self._label(
            current,
            "PhysicalSystemRuntime: WORLD + BODY + INTERNAL · one canonical tick.\n"
            "Law open1_signed_v1 when boundary ON · inspection fixtures only.",
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 7),
        )
        self.planet_setup_provenance.pack(anchor="w", pady=(4, 2))
        # Shown when Physical World / legacy OFF via chrome (default view = physical_world).

        # MM-CONFIG-1.1 — explicit legacy mode gate (default OFF)
        self.legacy_mode_header = self._label(
            self.left,
            "LEGACY EXPERIMENT MODE (historical 4.xx only)",
            surface="surface.navigation",
            foreground="text.muted",
            font=("TkDefaultFont", 8, "bold"),
        )
        self.legacy_mode_header.pack(anchor="w", padx=14, pady=(12, 5))
        self.legacy_mode_gate_frame = self._frame(self.left, "surface.card")
        self.legacy_mode_gate_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.legacy_mode_status_label = self._label(
            self.legacy_mode_gate_frame,
            textvariable=self.legacy_mode_status_var,
            surface="surface.card",
            foreground="status.info",
            font=("TkDefaultFont", 9, "bold"),
        )
        self.legacy_mode_status_label.pack(anchor="w", padx=10, pady=(8, 2))
        self.legacy_mode_check = tk.Checkbutton(
            self.legacy_mode_gate_frame,
            text="Enable Legacy Experiments",
            variable=self.legacy_mode_enabled,
            command=self._on_legacy_mode_toggled,
            borderwidth=0,
            highlightthickness=0,
            font=("TkDefaultFont", 8),
        )
        self._reg(
            self.legacy_mode_check,
            background="surface.card",
            foreground="text.secondary",
            activebackground="surface.card",
            activeforeground="text.primary",
            selectcolor="surface.control",
        )
        self.legacy_mode_check.pack(anchor="w", padx=10, pady=(2, 8))

        # Historical workspace explanation, shown only in Legacy mode while disabled.
        self.current_organism_null_header = self._label(
            self.left,
            "LEGACY EXPERIMENTS",
            surface="surface.navigation",
            foreground="text.muted",
            font=("TkDefaultFont", 8, "bold"),
        )
        self.current_organism_null_frame = self._frame(self.left, "surface.card")
        self._label(
            self.current_organism_null_frame,
            "Historical 4.xx reproduction workspace.\n\n"
            "Current MM remains a separate PhysicalSystemRuntime and is preserved\n"
            "when this workspace is opened or closed.\n\n"
            "Enable Legacy Experiments only to run a historical experiment.",
            surface="surface.card",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", padx=10, pady=10)
        # packed by _remount_left_workspace only

        self.legacy_setup_header = self._label(
            self.left,
            "LEGACY EXPERIMENTS",
            surface="surface.navigation",
            foreground="text.muted",
            font=("TkDefaultFont", 8, "bold"),
        )
        # packed only when legacy mode ON
        setup = self._frame(self.left, "surface.navigation")
        self.legacy_setup_frame = setup

        preset_row = self._frame(setup, "surface.navigation")
        preset_row.pack(fill="x", pady=(0, 6))
        self._label(
            preset_row, "EXPERIMENT", surface="surface.navigation",
            foreground="text.secondary", font=("TkDefaultFont", 8, "bold"),
        ).pack(anchor="w")
        preset_controls = self._frame(preset_row, "surface.navigation")
        preset_controls.pack(fill="x", pady=(2, 0))
        self.prospective_preset_combo = ttk.Combobox(
            preset_controls,
            textvariable=self.prospective_preset_var,
            values=self.PROSPECTIVE_PRESETS,
            state="readonly",
            width=1,
        )
        self.prospective_preset_combo.pack(side="left", fill="x", expand=True)
        self.prospective_preset_combo.bind(
            "<<ComboboxSelected>>", lambda _event: self._apply_prospective_preset()
        )
        self.legacy_preset_honesty = self._label(
            setup,
            "Note: some presets (e.g. 4.76) have no dedicated runner and fall through to observer_launcher.",
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 7),
        )
        self.legacy_preset_honesty.pack(anchor="w", pady=(0, 4))

        viewport = self._frame(setup, "surface.navigation")
        viewport.configure(height=250)
        viewport.pack(fill="x")
        viewport.pack_propagate(False)
        self.run_setup_viewport = viewport
        self.left.bind("<Configure>", self._resize_run_setup_viewport, add="+")
        self.run_setup_canvas = tk.Canvas(
            viewport, borderwidth=0, highlightthickness=0, width=1,
        )
        self._reg(self.run_setup_canvas, background="surface.navigation")
        self.run_setup_scrollbar = ttk.Scrollbar(
            viewport, orient="vertical", command=self.run_setup_canvas.yview
        )
        self.run_setup_canvas.configure(yscrollcommand=self.run_setup_scrollbar.set)
        self.run_setup_scrollbar.pack(side="right", fill="y")
        self.run_setup_canvas.pack(side="left", fill="both", expand=True)
        self.run_setup_form = self._frame(self.run_setup_canvas, "surface.navigation")
        self.run_setup_window = self.run_setup_canvas.create_window(
            (0, 0), window=self.run_setup_form, anchor="nw"
        )
        self.run_setup_form.bind("<Configure>", self._run_setup_content_configured)
        self.run_setup_canvas.bind("<Configure>", self._run_setup_canvas_configured)

        self._run_setup_groups = {}
        simulation = self._collapsible_group(
            self.run_setup_form, "SIMULATION", expanded=True
        )
        self.ticks_entry = self._compact_entry(simulation, "Ticks / days", self.ticks_var)
        self.seed_entry = self._compact_entry(simulation, "Seed", self.seed_var)

        world = self._collapsible_group(self.run_setup_form, "WORLD", expanded=True)
        self.world_combo = self._compact_combo(world, "World", self.world_var, WORLD_MODES)
        self.world_combo.bind("<<ComboboxSelected>>", self._world_changed)
        self.obstacle_combo = self._compact_combo(
            world, "Obstacle condition", self.obstacle_condition_var, OBSTACLE_CONDITIONS
        )
        self.persistent_combo = self._compact_combo(
            world, "Persistent target", self.persistent_condition_var,
            PERSISTENT_CONDITIONS, state="disabled"
        )
        self.layout_combo = self._compact_combo(
            world, "Resource layout", self.layout_var, RESOURCE_LAYOUTS
        )
        self.random_rate_entry = self._compact_entry(
            world, "Random event rate", self.random_rate_var
        )

        cognition = self._collapsible_group(
            self.run_setup_form, "COGNITION", expanded=False
        )
        self.memory_architecture_combo = self._compact_combo(
            cognition, "Memory / cognition", self.memory_architecture_var,
            MEMORY_ARCHITECTURES
        )
        self.world_dynamics_combo = self._compact_combo(
            cognition, "World dynamics", self.world_dynamics_var,
            ("STATIC_WORLD", "DYNAMIC_WORLD")
        )
        self.perception_mode_combo = self._compact_combo(
            cognition, "Perception", self.perception_mode_var,
            ("CONTACT_ONLY", "MULTI_CHANNEL")
        )
        self.cue_mode_combo = self._compact_combo(
            cognition, "Cue mode", self.cue_mode_var,
            ("LEGACY_CUE_ONLY", "PERCEPTUAL_CUE_ENABLED")
        )
        self.ecology_condition_combo = self._compact_combo(
            cognition, "Ecology condition", self.ecology_condition_var,
            ("POOR", "DYNAMIC_SUSTAINING", "DYNAMIC_SIGNAL", "DECORRELATED_SIGNAL", "UNSIGNALED", "INERT_SIGNAL")
        )
        self.resistance_mode_combo = self._compact_combo(
            cognition, "Interaction resistance", self.resistance_mode_var,
            ("OFF", "LOW", "OVERCOMEABLE", "IMPOSSIBLE", "DYNAMIC", "STRUCTURED", "RANDOM_CONTROL")
        )
        self._bind_run_setup_wheel(self.run_setup_form)
        self._world_changed()

        row = self._frame(setup, "surface.navigation")
        row.pack(fill="x", pady=(8, 2))
        self.start_button = self._button(
            row, "Start Run", self.start, "primary"
        )
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.stop_button = self._button(row, "Stop", self.stop, "danger")
        self.stop_button.pack(side="left", padx=(4, 0))

        self.run_identity_header = self._section(self.left, "RUN IDENTITY")
        card = self._frame(self.left, "surface.card")
        self.run_identity_frame = card
        card.pack(fill="x", padx=12)
        self.status_label = self._label(
            card,
            textvariable=self.status_var,
            surface="surface.card",
            foreground="status.info",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.status_label.pack(anchor="w", padx=10, pady=(10, 4))
        self._label(
            card,
            textvariable=self.run_var,
            surface="surface.card",
            foreground="text.secondary",
            font=("TkFixedFont", 8),
        ).pack(anchor="w", padx=10, pady=2)
        self._label(
            card,
            textvariable=self.path_var,
            surface="surface.card",
            foreground="text.muted",
            font=("TkFixedFont", 7),
        ).pack(anchor="w", padx=10, pady=(2, 10))

        self.ontology_header = self._section(self.left, "ONTOLOGY")
        card = self._frame(self.left, "surface.card")
        self.ontology_frame = card
        card.pack(fill="x", padx=12)
        self._label(
            card,
            "WORLD TRUTH\n"
            "↓\n"
            "BODY TRUTH\n"
            "↓\n"
            "ACCESSIBLE SIGNALS\n"
            "↓\n"
            "PSYCHE MODEL\n"
            "↓\n"
            "BEHAVIOR",
            surface="surface.card",
            foreground="text.secondary",
            font=("TkFixedFont", 8, "bold"),
        ).pack(anchor="w", padx=10, pady=10)

        self.scientific_boundary_header = self._section(self.left, "SCIENTIFIC BOUNDARY")
        card = self._frame(self.left, "surface.card")
        self.scientific_boundary_frame = card
        card.pack(fill="x", padx=12)
        self._label(
            card,
            "Mass, age, hidden object roles and\n"
            "event receipts are Observer truth.\n\n"
            "The psyche sees local perception,\n"
            "interoception and experienced effects.",
            surface="surface.card",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", padx=10, pady=10)

        # Default: legacy OFF — hide historical workspace immediately.
        self._apply_legacy_mode_chrome()

    def _entry_field(self, parent, title, variable, row):
        self._label(
            parent,
            title.upper(),
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 8, "bold"),
        ).grid(row=row * 2, column=0, sticky="w", pady=(5, 2))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row * 2 + 1, column=0, sticky="ew")
        return entry

    def _compact_row(self, parent, title):
        row = self._frame(parent, "surface.navigation")
        row.pack(fill="x", padx=8, pady=2)
        self._label(
            row, title, surface="surface.navigation", foreground="text.secondary",
            font=("TkDefaultFont", 8),
        ).pack(side="left", fill="x", expand=True)
        return row

    def _compact_entry(self, parent, title, variable):
        row = self._compact_row(parent, title)
        widget = ttk.Entry(row, textvariable=variable, width=14)
        widget.pack(side="right", fill="x", expand=False)
        return widget

    def _compact_combo(self, parent, title, variable, values, *, state="readonly"):
        row = self._compact_row(parent, title)
        widget = ttk.Combobox(
            row, textvariable=variable, values=tuple(values), state=state, width=18
        )
        widget.pack(side="right", fill="x", expand=False)
        return widget

    def _collapsible_group(self, parent, title, *, expanded):
        shell = self._frame(parent, "surface.navigation")
        shell.pack(fill="x")
        body = self._frame(shell, "surface.navigation")
        state = {"expanded": bool(expanded), "body": body, "title": title}
        header = self._button(
            shell, "", lambda: self._toggle_run_setup_group(title), kind="neutral"
        )
        header.configure(anchor="w", padx=8, pady=4, font=("TkDefaultFont", 8, "bold"))
        header.pack(fill="x", pady=(2, 0))
        state["header"] = header
        self._run_setup_groups[title] = state
        if expanded:
            body.pack(fill="x")
        self._update_run_setup_group_header(title)
        return body

    def _update_run_setup_group_header(self, title):
        group = self._run_setup_groups[title]
        group["header"].configure(
            text=("▼ " if group["expanded"] else "▶ ") + title
        )

    def _toggle_run_setup_group(self, title):
        group = self._run_setup_groups[title]
        group["expanded"] = not group["expanded"]
        if group["expanded"]:
            group["body"].pack(fill="x")
        else:
            group["body"].pack_forget()
        self._update_run_setup_group_header(title)
        self.run_setup_form.update_idletasks()
        self._update_run_setup_scrollregion()

    def _run_setup_content_configured(self, _event=None):
        self._update_run_setup_scrollregion()

    def _run_setup_canvas_configured(self, event):
        self.run_setup_canvas.itemconfigure(self.run_setup_window, width=max(1, event.width))
        self._update_run_setup_scrollregion()

    def _resize_run_setup_viewport(self, event):
        # Leave the existing RUN IDENTITY / ontology cards untouched while the
        # parameter viewport absorbs vertical resizing within conservative bounds.
        height = max(170, min(340, int(event.height) - 500))
        if int(self.run_setup_viewport.cget("height")) != height:
            self.run_setup_viewport.configure(height=height)

    def _update_run_setup_scrollregion(self):
        bbox = self.run_setup_canvas.bbox("all")
        self.run_setup_canvas.configure(scrollregion=bbox or (0, 0, 0, 0))

    def _run_setup_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            delta = int(getattr(event, "delta", 0))
            units = -1 if delta > 0 else (1 if delta < 0 else 0)
        if units:
            self.run_setup_canvas.yview_scroll(units, "units")
        return "break"

    def _bind_run_setup_wheel(self, widget):
        widget.bind("<MouseWheel>", self._run_setup_mousewheel)
        widget.bind("<Button-4>", self._run_setup_mousewheel)
        widget.bind("<Button-5>", self._run_setup_mousewheel)
        for child in widget.winfo_children():
            self._bind_run_setup_wheel(child)

    def _build_map(self, parent):
        card = self._frame(parent, "surface.card")
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)
        self.map_card = card
        parent.add(
            card,
            minsize=self.MAP_PANEL_MIN_HEIGHT,
            stretch="always",
            pady=4,
        )

        header = self._frame(card, "surface.card")
        header.grid(row=0, column=0, sticky="ew")
        controls = self._frame(header, "surface.card")
        controls.pack(side="right", padx=(4, 8))

        self.timeline_toggle_button = self._button(
            controls,
            "Timeline ▲",
            self._toggle_timeline,
        )
        self.timeline_toggle_button.pack(side="right", padx=(4, 0), pady=4)

        self.truth_check = tk.Checkbutton(
            controls,
            text="Truth",
            variable=self.truth_overlay_var,
            command=self._draw_map,
            borderwidth=0,
            highlightthickness=0,
        )
        self._reg(
            self.truth_check,
            background="surface.card",
            foreground="text.secondary",
            activebackground="surface.card",
            activeforeground="text.primary",
            selectcolor="surface.control",
        )
        self.truth_check.pack(side="right", padx=(4, 0))

        self.planet_layer_combo = ttk.Combobox(
            controls,
            textvariable=self.planet_layer_var,
            values=FIELD_LAYERS,
            state="readonly",
            width=12,
        )
        self.planet_layer_combo.pack(side="right", padx=(6, 0))
        self.planet_layer_combo.bind("<<ComboboxSelected>>", lambda _e: self._planet_layer_changed())
        self._label(
            controls,
            "Planet layer",
            surface="surface.card",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        ).pack(side="right", padx=(8, 0))
        self.planet_boundary_check = tk.Checkbutton(
            controls,
            text="Boundary contact",
            variable=self.planet_boundary_overlay_var,
            command=self._draw_map,
            borderwidth=0,
            highlightthickness=0,
            font=("TkDefaultFont", 8),
        )
        self._reg(
            self.planet_boundary_check,
            background="surface.card",
            foreground="text.secondary",
            activebackground="surface.card",
            activeforeground="text.primary",
            selectcolor="surface.control",
        )
        self.planet_boundary_check.pack(side="right", padx=(4, 0))
        self.planet_reset_button = self._button(controls, "Reset", self._planet_reset)
        self.planet_reset_button.pack(side="right", padx=3, pady=4)
        self.planet_step_button = self._button(controls, "Step", self._planet_step)
        self.planet_step_button.pack(side="right", padx=3, pady=4)
        self.planet_pause_button = self._button(controls, "Pause", self._planet_pause)
        self.planet_pause_button.pack(side="right", padx=3, pady=4)
        self.planet_stop_button = self._button(controls, "Stop", self._planet_stop, "danger")
        self.planet_stop_button.pack(side="right", padx=3, pady=4)
        self.planet_run_button = self._button(controls, "Run", self._planet_run)
        self.planet_run_button.pack(side="right", padx=3, pady=4)
        self._label(
            controls,
            textvariable=self.planet_run_status_var,
            surface="surface.card",
            foreground="status.info",
            font=("TkDefaultFont", 8, "bold"),
        ).pack(side="right", padx=(8, 4))

        memory_check = tk.Checkbutton(
            controls,
            text="Memory",
            variable=self.memory_overlay_var,
            command=self._draw_map,
            borderwidth=0,
            highlightthickness=0,
        )
        self._reg(
            memory_check,
            background="surface.card",
            foreground="text.secondary",
            activebackground="surface.card",
            activeforeground="text.primary",
            selectcolor="surface.control",
        )
        memory_check.pack(side="right", padx=4)

        follow_check = tk.Checkbutton(
            controls,
            text="Follow",
            variable=self.follow_agent_var,
            command=self._draw_map,
            borderwidth=0,
            highlightthickness=0,
        )
        self._reg(
            follow_check,
            background="surface.card",
            foreground="text.secondary",
            activebackground="surface.card",
            activeforeground="text.primary",
            selectcolor="surface.control",
        )
        follow_check.pack(side="right", padx=4)

        self.map_fit_button = self._button(controls, "Fit", self._map_fit)
        self.map_fit_button.pack(side="right", padx=3, pady=4)
        self.map_zoom_in_button = self._button(
            controls, "+", lambda: self._map_zoom(1.25)
        )
        self.map_zoom_in_button.pack(side="right", padx=2, pady=4)
        self.map_zoom_out_button = self._button(
            controls, "−", lambda: self._map_zoom(0.8)
        )
        self.map_zoom_out_button.pack(side="right", padx=2, pady=4)

        # Pack the controls first so they remain visible when the window or
        # center pane becomes narrow; the informational hint yields space.
        self._label(
            header,
            "WORLD VIEW",
            surface="surface.card",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left", padx=12, pady=9)
        self.map_hint = self._label(
            header,
            "Waiting for organism telemetry",
            surface="surface.card",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        )
        self.map_hint.pack(side="left", padx=14)

        self.canvas = tk.Canvas(
            card,
            borderwidth=0,
            highlightthickness=1,
        )
        self._reg(
            self.canvas,
            background="surface.canvas",
            highlightbackground="border.default",
            highlightcolor="focus.ring",
        )
        self.canvas.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(0, 10),
        )
        self.canvas.bind("<Configure>", lambda _e: self._draw_map())
        self.canvas.bind("<ButtonPress-1>", self._map_press)
        self.canvas.bind("<B1-Motion>", self._map_drag)
        self.canvas.bind("<ButtonRelease-1>", self._map_release)
        self.canvas.bind("<MouseWheel>", self._map_wheel)
        self.canvas.bind("<Button-4>", lambda event: self._map_zoom(1.12, event))
        self.canvas.bind("<Button-5>", lambda event: self._map_zoom(0.89, event))

    def _build_timeline(self, parent):
        card = self._frame(parent, "surface.card")
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)
        self.timeline_card = card
        parent.add(
            card,
            height=self._timeline_height,
            minsize=self.TIMELINE_PANEL_MIN_HEIGHT,
            stretch="never",
            pady=4,
        )

        self._label(
            card,
            "CAUSAL TIMELINE  •  BODY AFTER ACTION vs SIGNALS AT DECISION",
            surface="surface.card",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=8)

        columns = (
            "tick",
            "pos",
            "mass",
            "action",
            "body",
            "signals",
            "pe",
            "u",
            "v",
            "reason",
        )
        self.timeline = ttk.Treeview(
            card,
            columns=columns,
            show="headings",
            height=10,
        )
        headings = {
            "tick": "DAY",
            "pos": "POS",
            "mass": "MASS",
            "action": "ACTION",
            "body": "BODY E/H/F",
            "signals": "SIGNALS E/H/F",
            "pe": "PE",
            "u": "U",
            "v": "VALUE",
            "reason": "SELECTION REASON",
        }
        widths = {
            "tick": 58,
            "pos": 68,
            "mass": 68,
            "action": 135,
            "body": 140,
            "signals": 140,
            "pe": 62,
            "u": 62,
            "v": 70,
            "reason": 250,
        }
        for column in columns:
            self.timeline.heading(column, text=headings[column])
            self.timeline.column(
                column,
                width=widths[column],
                anchor="w",
                stretch=(column == "reason"),
            )

        self.timeline.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(10, 0),
            pady=(0, 10),
        )
        scroll = ttk.Scrollbar(
            card,
            orient="vertical",
            command=self.timeline.yview,
        )
        scroll.grid(
            row=1,
            column=1,
            sticky="ns",
            padx=(0, 10),
            pady=(0, 10),
        )
        self.timeline.configure(yscrollcommand=scroll.set)

    def _toggle_timeline(self):
        if self.timeline_visible:
            self._timeline_height = max(
                self.TIMELINE_PANEL_MIN_HEIGHT,
                self.timeline_card.winfo_height(),
            )
            self.center_splitter.forget(self.timeline_card)
            self.timeline_visible = False
            self.timeline_toggle_button.configure(text="Timeline ▼")
            return

        self.center_splitter.add(
            self.timeline_card,
            height=self._timeline_height,
            minsize=self.TIMELINE_PANEL_MIN_HEIGHT,
            stretch="never",
            pady=4,
        )
        self.timeline_visible = True
        self.timeline_toggle_button.configure(text="Timeline ▲")
        self.root.after_idle(self._restore_timeline_height)

    def _restore_timeline_height(self):
        if not self.timeline_visible:
            return
        total_height = self.center_splitter.winfo_height()
        sash_y = max(
            self.MAP_PANEL_MIN_HEIGHT,
            total_height - self._timeline_height,
        )
        try:
            self.center_splitter.sash_place(0, 1, sash_y)
        except tk.TclError:
            pass


    def _build_right(self):
        # The Observer truth/model panel grows as new scientific layers are
        # exposed. Keep it vertically scrollable instead of silently
        # collapsing the event list on smaller displays.
        shell = self._frame(self.right, "surface.navigation")
        shell.pack(fill="both", expand=True)
    
        scroll = tk.Canvas(
            shell,
            borderwidth=0,
            highlightthickness=0,
        )
        self._reg(
            scroll,
            background="surface.navigation",
            highlightbackground="surface.navigation",
        )
        scrollbar = ttk.Scrollbar(
            shell,
            orient="vertical",
            command=scroll.yview,
        )
        scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
    
        content = self._frame(scroll, "surface.navigation")
        window_id = scroll.create_window(
            (0, 0),
            window=content,
            anchor="nw",
        )
    
        def sync_scroll(_event=None):
            scroll.configure(scrollregion=scroll.bbox("all"))
    
        def sync_width(event):
            scroll.itemconfigure(window_id, width=event.width)
    
        content.bind("<Configure>", sync_scroll)
        scroll.bind("<Configure>", sync_width)
    
        def wheel(event):
            if event.delta:
                scroll.yview_scroll(
                    int(-1 * (event.delta / 120)),
                    "units",
                )
    
        scroll.bind("<MouseWheel>", wheel)
        content.bind("<MouseWheel>", wheel)
        self.right_scroll_canvas = scroll
        self.right_content = content

        self._section(content, "CURRENT MM — SYSTEM + AGENT")
        planet_card = self._frame(content, "surface.card")
        planet_card.pack(fill="x", padx=12, pady=(0, 8))
        self.planet_status_panel = tk.Text(
            planet_card,
            height=10,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.planet_status_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.planet_status_panel.pack(fill="both", expand=True)
        self.planet_status_panel.insert("1.0", "Current MM is ready. Apply setup, Run, or Step.\nWORLD + BODY + INTERNAL share one tick.")
        self.planet_status_panel.configure(state="disabled")

        self._section(content, "CURRENT MM — COGNITION")
        cog_card = self._frame(content, "surface.card")
        cog_card.pack(fill="x", padx=12, pady=(0, 8))
        self.planet_cognition_panel = tk.Text(
            cog_card,
            height=16,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.planet_cognition_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.planet_cognition_panel.pack(fill="both", expand=True)
        self.planet_cognition_panel.insert(
            "1.0",
            "Agent observation / memory / prediction / prospection / action / causal trace\n"
            "(populated from PhysicalSystemRuntime cognition; no fake thoughts)",
        )
        self.planet_cognition_panel.configure(state="disabled")

        self._section(content, "EXTERNAL MATERIAL BOUNDARY")
        boundary_card = self._frame(content, "surface.card")
        boundary_card.pack(fill="x", padx=12, pady=(0, 8))
        self.planet_boundary_panel = tk.Text(
            boundary_card,
            height=14,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.planet_boundary_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.planet_boundary_panel.pack(fill="both", expand=True)
        self.planet_boundary_panel.insert("1.0", "External Material Boundary\nOFF\n(default)")
        self.planet_boundary_panel.configure(state="disabled")

        self.planet_analyzer_header = self._section(content, "PHYSICAL WORLD ANALYZER")
        analyzer_card = self._frame(content, "surface.card")
        analyzer_card.pack(fill="x", padx=12, pady=(0, 8))
        self.planet_analyzer_panel = tk.Text(
            analyzer_card,
            height=18,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.planet_analyzer_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.planet_analyzer_panel.pack(fill="both", expand=True)
        self.planet_analyzer_panel.insert(
            "1.0",
            "MM-ANALYZER-1\nStratified summaries appear after Planet reset/step.\n"
            "RAW / DERIVED / INTERPRETATION / NULL / UNSUPPORTED.",
        )
        self.planet_analyzer_panel.configure(state="disabled")

        self._section(content, "SELECTION INSPECTOR")
        inspector_card = self._frame(content, "surface.card")
        inspector_card.pack(fill="x", padx=12, pady=(0, 8))
        self.inspector = tk.Text(
            # wrap-safe: long IDs must not expand page
            inspector_card,
            height=20,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        inspector_scroll = ttk.Scrollbar(
            inspector_card,
            orient="vertical",
            command=self.inspector.yview,
        )
        self.inspector.configure(yscrollcommand=inspector_scroll.set)
        self._reg(
            self.inspector,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        inspector_scroll.pack(side="right", fill="y")
        self.inspector.pack(side="left", fill="both", expand=True)
        self._set_inspector_text(
            "Physical World: click a cell on the planet map.\n\n"
            "Legacy organism views still use OBJECTIVE / PERCEIVED / LEARNED when active."
        )
    
        self._section(content, "PHYSICAL INTAKE & INTERNAL PROCESSING")
        intake_card = self._frame(content, "surface.card")
        intake_card.pack(fill="x", padx=12, pady=(0, 8))
        self.physical_intake_panel = tk.Text(
            intake_card,
            height=12,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.physical_intake_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.physical_intake_panel.pack(fill="both", expand=True)
        self.physical_intake_panel.insert(
            "1.0",
            "EXTERNAL OBJECT → TRANSFER → INTERNAL MATERIAL → PROCESSING → BODY\n"
            "No FOOD/EAT/HUNGER labels. Update 4.8 physical mechanism.",
        )
        self.physical_intake_panel.configure(state="disabled")

        self._section(content, "TEMPORAL CONTINGENCY ACQUISITION")
        tc_card = self._frame(content, "surface.card")
        tc_card.pack(fill="x", padx=12, pady=(0, 8))
        self.temporal_contingency_panel = tk.Text(
            tc_card, height=12, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(self.temporal_contingency_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.temporal_contingency_panel.pack(fill="both", expand=True)
        self.temporal_contingency_panel.insert(
            "1.0",
            "Update 4.10 temporal acquisition · measurement is causally inert; mechanism availability depends on run configuration",
        )
        self.temporal_contingency_panel.configure(state="disabled")

        self._section(content, "ECOLOGICAL CONTINGENCY STABILIZATION")
        ecs_card = self._frame(content, "surface.card")
        ecs_card.pack(fill="x", padx=12, pady=(0, 8))
        self.ecological_stabilization_panel = tk.Text(
            ecs_card, height=10, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(
            self.ecological_stabilization_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.ecological_stabilization_panel.pack(fill="both", expand=True)
        self.ecological_stabilization_panel.insert(
            "1.0",
            "Update 4.10.1 ecological stabilization (Observer only; inert)",
        )
        self.ecological_stabilization_panel.configure(state="disabled")

        self._section(content, "ACTION EXECUTION ATTRIBUTION")
        aea_card = self._frame(content, "surface.card")
        aea_card.pack(fill="x", padx=12, pady=(0, 8))
        self.action_execution_attribution_panel = tk.Text(
            aea_card, height=12, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(
            self.action_execution_attribution_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.action_execution_attribution_panel.pack(fill="both", expand=True)
        self.action_execution_attribution_panel.insert(
            "1.0",
            "Update 4.10.2 action execution attribution (Observer only; inert)",
        )
        self.action_execution_attribution_panel.configure(state="disabled")

        self._section(content, "PREDICTIVE UTILIZATION DIAGNOSTIC")
        pud_card = self._frame(content, "surface.card")
        pud_card.pack(fill="x", padx=12, pady=(0, 8))
        self.predictive_utilization_panel = tk.Text(
            pud_card, height=12, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(
            self.predictive_utilization_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.predictive_utilization_panel.pack(fill="both", expand=True)
        self.predictive_utilization_panel.insert(
            "1.0",
            "Update 4.10.3 predictive utilization (Observer only; inert)",
        )
        self.predictive_utilization_panel.configure(state="disabled")

        self._section(content, "ACTION ECONOMICS")
        ae_card = self._frame(content, "surface.card")
        ae_card.pack(fill="x", padx=12, pady=(0, 8))
        self.action_economics_panel = tk.Text(
            ae_card, height=12, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(self.action_economics_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.action_economics_panel.pack(fill="both", expand=True)
        self.action_economics_panel.insert("1.0", "Update 4.10.5 action economics (Observer only; inert)")
        self.action_economics_panel.configure(state="disabled")

        self._section(content, "NATURAL PHYSIOLOGICAL WINDOW")
        npw_card = self._frame(content, "surface.card")
        npw_card.pack(fill="x", padx=12, pady=(0, 8))
        self.natural_physiological_window_panel = tk.Text(
            npw_card, height=14, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(self.natural_physiological_window_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.natural_physiological_window_panel.pack(fill="both", expand=True)
        self.natural_physiological_window_panel.insert("1.0", "Update 4.10.6 natural physiological window (Observer only; inert)")
        self.natural_physiological_window_panel.configure(state="disabled")

        self._section(content, "DEVELOPMENTAL PHYSIOLOGY")
        dp_card = self._frame(content, "surface.card")
        dp_card.pack(fill="x", padx=12, pady=(0, 8))
        self.developmental_physiology_panel = tk.Text(
            dp_card, height=14, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(self.developmental_physiology_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.developmental_physiology_panel.pack(fill="both", expand=True)
        self.developmental_physiology_panel.insert("1.0", "Update 4.10.7 developmental physiology (Observer only; inert)")
        self.developmental_physiology_panel.configure(state="disabled")

        self._section(content, "ORDINARY ACTION ECONOMY")
        oae_card = self._frame(content, "surface.card")
        oae_card.pack(fill="x", padx=12, pady=(0, 8))
        self.ordinary_action_economy_panel = tk.Text(
            oae_card, height=14, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(self.ordinary_action_economy_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.ordinary_action_economy_panel.pack(fill="both", expand=True)
        self.ordinary_action_economy_panel.insert("1.0", "Update 4.10.8 ordinary action economy (Observer only; inert)")
        self.ordinary_action_economy_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE TEMPORAL ECONOMY")
        pte_card = self._frame(content, "surface.card")
        pte_card.pack(fill="x", padx=12, pady=(0, 8))
        self.prospective_temporal_economy_panel = tk.Text(
            pte_card, height=14, wrap="none", borderwidth=0, highlightthickness=0,
            font=("TkFixedFont", 7), padx=8, pady=8,
        )
        self._reg(self.prospective_temporal_economy_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.prospective_temporal_economy_panel.pack(fill="both", expand=True)
        self.prospective_temporal_economy_panel.insert("1.0", "Update 4.10.9 prospective temporal economy (Observer only; inert)")
        self.prospective_temporal_economy_panel.configure(state="disabled")

        self._section(content, "BOUNDED PROSPECTIVE TRAJECTORY")
        self.bounded_prospective_trajectory_panel = tk.Text(
            content, height=14, wrap="word", relief="flat", borderwidth=0, highlightthickness=0
        )
        self.bounded_prospective_trajectory_panel.configure(font=("TkFixedFont", 7), padx=8, pady=8)
        self._reg(self.bounded_prospective_trajectory_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.bounded_prospective_trajectory_panel.pack(fill="both", expand=True)
        self.bounded_prospective_trajectory_panel.insert("1.0", "Update 4.10.10 bounded prospective trajectory (Observer only; inert)")
        self.bounded_prospective_trajectory_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE TRAJECTORY CALIBRATION")
        self.prospective_trajectory_calibration_panel = tk.Text(
            content, height=14, wrap="word", relief="flat", borderwidth=0, highlightthickness=0
        )
        self.prospective_trajectory_calibration_panel.configure(font=("TkFixedFont", 7), padx=8, pady=8)
        self._reg(self.prospective_trajectory_calibration_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.prospective_trajectory_calibration_panel.pack(fill="both", expand=True)
        self.prospective_trajectory_calibration_panel.insert("1.0", "Update 4.10.11 prospective trajectory calibration (Observer only; inert)")
        self.prospective_trajectory_calibration_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE SELF-STATE")
        self.prospective_self_state_panel = tk.Text(
            content, height=16, wrap="word", relief="flat", borderwidth=0, highlightthickness=0
        )
        self.prospective_self_state_panel.configure(font=("TkFixedFont", 7), padx=8, pady=8)
        self._reg(self.prospective_self_state_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.prospective_self_state_panel.pack(fill="both", expand=True)
        self.prospective_self_state_panel.insert("1.0", "Update 4.11 prospective self-state (Observer only; inert)")
        self.prospective_self_state_panel.configure(state="disabled")

        self._section(content, "COMPOSED PROSPECTIVE TRAJECTORIES")
        self.composed_prospective_trajectories_panel = tk.Text(
            content, height=14, wrap="word", relief="flat", borderwidth=0, highlightthickness=0
        )
        self.composed_prospective_trajectories_panel.configure(font=("TkFixedFont", 7), padx=8, pady=8)
        self._reg(self.composed_prospective_trajectories_panel, background="surface.card", foreground="text.secondary",
                  insertbackground="text.primary", selectbackground="surface.selected", selectforeground="text.primary")
        self.composed_prospective_trajectories_panel.pack(fill="both", expand=True)
        self.composed_prospective_trajectories_panel.insert("1.0", "Update 4.12 composed prospective trajectories (Observer only; inert)")
        self.composed_prospective_trajectories_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · CURRENT STATE")
        self.prospective_current_state_panel = self._safe_text(content, height=8)
        self.prospective_current_state_panel.insert("1.0", "CURRENT STATE (psyche-visible)")
        self.prospective_current_state_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · ACTION FUTURES")
        self.prospective_action_futures_panel = self._safe_text(content, height=12)
        self.prospective_action_futures_panel.insert("1.0", "ACTION FUTURES H1/H2/H3")
        self.prospective_action_futures_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · COMPOSED FUTURES")
        self.prospective_composed_futures_panel = self._safe_text(content, height=14)
        self.prospective_composed_futures_panel.insert("1.0", "COMPOSED FUTURES (no ranking)")
        self.prospective_composed_futures_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · HISTORY COMPARISON")
        self.prospective_history_comparison_panel = self._safe_text(content, height=12)
        self.prospective_history_comparison_panel.insert("1.0", "HISTORY COMPARISON A|B")
        self.prospective_history_comparison_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · PREDICTION CHECK")
        self.prospective_prediction_check_panel = self._safe_text(content, height=10)
        self.prospective_prediction_check_panel.insert("1.0", "PREDICTED vs REALIZED")
        self.prospective_prediction_check_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · EXPECTATION CHECK")
        self.prospective_expectation_check_panel = self._safe_text(content, height=14)
        self.prospective_expectation_check_panel.insert(
            "1.0",
            "EXPECTATION CHECK — NO_PREDICTIVE_BASELINE vs MISMATCH (no surprise variable)",
        )
        self.prospective_expectation_check_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · ACQUIRED CONSEQUENCES")
        self.prospective_acquired_consequences_panel = self._safe_text(content, height=12)
        self.prospective_acquired_consequences_panel.insert(
            "1.0",
            "ACQUIRED CONSEQUENCES — legacy EMA vs bounded multi-modes (no ranking)",
        )
        self.prospective_acquired_consequences_panel.configure(state="disabled")

        self._section(content, "PROSPECTIVE · CONTINUITY TRACE")
        self.prospective_continuity_trace_panel = self._safe_text(content, height=14)
        self.prospective_continuity_trace_panel.insert(
            "1.0",
            "CONTINUITY TRACE — mechanism-persistent old tail vs fresh reconstruction",
        )
        self.prospective_continuity_trace_panel.configure(state="disabled")

        self._section(content, "EXPERIMENT PRESET STATUS (4.11–4.16)")
        self.prospective_settings_panel = self._safe_text(content, height=8)
        _ps_msg = (
            'Select the experiment in RUN SETUP.\n'
            'Preset only populates existing legitimate controls — no fake intelligence/curiosity sliders.'
        )
        self.prospective_settings_panel.insert('1.0', _ps_msg)
        self.prospective_settings_panel.configure(state='disabled')

        self._section(content, "ENVIRONMENTAL REGULATION PROBE")
        erp_card = self._frame(content, "surface.card")
        erp_card.pack(fill="x", padx=12, pady=(0, 8))
        self.env_regulation_probe_panel = tk.Text(
            erp_card,
            height=14,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.env_regulation_probe_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.env_regulation_probe_panel.pack(fill="both", expand=True)
        self.env_regulation_probe_panel.insert(
            "1.0",
            "Update 4.9.1 diagnostic (Observer only). PHYSICAL → EXPERIENCE → RETRIEVAL → ...\n"
            "Does not feed cognition.",
        )
        self.env_regulation_probe_panel.configure(state="disabled")

        self._section(content, "ENVIRONMENTAL CAUSAL FRONTIER")
        ecf_card = self._frame(content, "surface.card")
        ecf_card.pack(fill="x", padx=12, pady=(0, 8))
        self.env_causal_frontier_panel = tk.Text(
            ecf_card,
            height=12,
            wrap="none",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.env_causal_frontier_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.env_causal_frontier_panel.pack(fill="both", expand=True)
        self.env_causal_frontier_panel.insert(
            "1.0",
            "Stage | Evidence | Status | Ref\n(Update 4.9.1 causal frontier — diagnosis only)",
        )
        self.env_causal_frontier_panel.configure(state="disabled")

        self._section(content, "WORLD–ORGANISM EXCHANGE")
        exch_card = self._frame(content, "surface.card")
        exch_card.pack(fill="x", padx=12, pady=(0, 8))
        self.world_organism_exchange_panel = tk.Text(
            exch_card,
            height=10,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.world_organism_exchange_panel,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.world_organism_exchange_panel.pack(fill="both", expand=True)
        self.world_organism_exchange_panel.insert(
            "1.0",
            (
                "LOCAL ENV AVAILABILITY → EXCHANGE → INTERNAL MATERIALS → PROCESSING → BODY\n"
                "Update 4.9. Same storage as 4.8. No survival-label cognition."
            ),
        )
        self.world_organism_exchange_panel.configure(state="disabled")

        self._section(content, "CROSS-AGENT PHYSICAL TRACE")
        trace_card = self._frame(content, "surface.card")
        trace_card.pack(fill="x", padx=12, pady=(0, 8))
        self.cross_agent_trace = tk.Text(
            trace_card,
            height=14,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            padx=8,
            pady=8,
        )
        self._reg(
            self.cross_agent_trace,
            background="surface.card",
            foreground="text.secondary",
            insertbackground="text.primary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.cross_agent_trace.pack(fill="both", expand=True)
        self.cross_agent_trace.insert(
            "1.0",
            "OBSERVER GROUND TRUTH vs AGENT-AVAILABLE EVIDENCE\n"
            "Load a 4.7.1 probe run or observer_receipts.cross_agent_trace_v471.\n"
            "No social labels. Stages: PHYSICAL→OBSERVABLE→EXPERIENCE→RETRIEVAL→…",
        )
        self.cross_agent_trace.configure(state="disabled")

        self._section(content, "1 • WORLD TRUTH  [OBSERVER ONLY]")
        self.world_values = self._kv_card(
            content,
            (
                "position",
                "progress",
                "objective objects",
                "objective obstacles",
                "obstacle contacts",
                "random events",
                "current world event",
            ),
        )
    
        self._section(content, "2 • BODY TRUTH / BIOLOGICAL TIME  [OBSERVER ONLY]")
        self.body_values = self._kv_card(
            content,
            (
                "life day",
                "age years",
                "mass kg",
                "mass status",
                "mass risk",
                "mass delta/day",
                "metabolic balance",
                "energy reserve",
                "hydration",
                "fatigue",
                "damage",
                "effort cost",
            ),
        )
    
        self._section(content, "3 • ACCESSIBLE SIGNALS  [AGENT CAN SEE]")
        self.signal_values = self._kv_card(
            content,
            (
                "energy signal",
                "hydration signal",
                "fatigue signal",
                "discomfort signal",
                "effort signal",
                "last experienced",
                "new effect → next tick",
            ),
        )
    
        self._section(content, "4 • PSYCHE MODEL  [LEARNED STATE]")
        self.model_values = self._kv_card(
            content,
            (
                "memory mode",
                "memory episodes",
                "memory patterns",
                "novel fragments",
                "retrieval stage",
                "candidates P/X/E/T",
                "retrieval confidence",
                "active modalities",
                "expectation",
                "perceptual mismatch",
                "perceptual activation",
                "retention",
                "known positions",
                "known objects",
                "known obstacles",
                "action models",
                "object cue models",
                "obstacle cue models",
                "physiology context",
                "prediction source",
                "context samples",
                "prediction error",
                "selected prediction",
                "selected uncertainty",
                "selected value",
                "selected habit",
            ),
        )
    
        self._section(content, "5 • BEHAVIOR")
        self.behavior_values = self._kv_card(
            content,
            (
                "action",
                "selection reason",
                "selection score",
                "action source",
            ),
        )
    
        self._section(content, "OBSERVER EVENTS / MODEL DIVERGENCE")
        event_card = self._frame(content, "surface.card")
        event_card.pack(fill="x", padx=12, pady=(0, 12))
        self.events = tk.Listbox(
            event_card,
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 7),
            height=8,
        )
        self._reg(
            self.events,
            background="surface.card",
            foreground="text.secondary",
            selectbackground="surface.selected",
            selectforeground="text.primary",
        )
        self.events.pack(fill="both", expand=True, padx=8, pady=8)

    def _update_cross_agent_trace_panel(self, tick) -> None:
        """Update 4.7.1: Observer ground truth vs agent-available evidence."""
        widget = getattr(self, "cross_agent_trace", None)
        if widget is None:
            return
        from pathlib import Path
        import json
        lines = [
            "=== OBSERVER GROUND TRUTH ===",
            "(actor / probe id never enter cognition)",
        ]
        # Prefer live receipts on tick if present
        receipt = None
        raw = getattr(tick, "raw", None) or getattr(tick, "world_variables", None)
        # Fall back to latest probe summary artifact
        summary = Path("results/update471_cross_agent_trace/TRACE_PRESENT_SUMMARY.json")
        chain = Path("results/update471_cross_agent_trace/CROSS_AGENT_TRACE_CHAIN.json")
        data = None
        if summary.exists():
            try:
                data = json.loads(summary.read_text())
            except Exception:
                data = None
        if data:
            inter = data.get("intervention") or {}
            bob = data.get("b_observation") or {}
            bexp = data.get("b_experience") or {}
            bret = data.get("b_retrieval") or {}
            stages = data.get("stages") or {}
            lines.append(
                f"A intervention: agent={inter.get('acting_agent')} "
                f"tick={inter.get('tick')} action={inter.get('action')}"
            )
            lines.append(
                f"property quantity {inter.get('before')} → {inter.get('after')} "
                f"changed={inter.get('changed')}"
            )
            lines.append("=== AGENT-AVAILABLE EVIDENCE ===")
            lines.append(
                f"visible quantity={bob.get('quantity')} "
                f"in_visible_objects={bob.get('in_visible_objects')} "
                f"offset={bob.get('relative_offset')}"
            )
            lines.append(
                f"experience stored={bexp.get('stored')} "
                f"spatial_qty={(bexp.get('spatial') or {}).get('quantity')}"
            )
            lines.append(
                f"retrieval={bret.get('status')} retrieved={bret.get('retrieved')}"
            )
            lines.append("=== STAGE CHAIN ===")
            order = [
                "PHYSICAL_EVENT",
                "OBSERVABLE",
                "EXPERIENCE",
                "RETRIEVAL",
                "PREDICTION",
                "PROSPECTIVE_VALUE",
                "DECISION",
            ]
            for key in order:
                lines.append(f"{key}: {stages.get(key, 'N/A')}")
                if key != "DECISION":
                    lines.append("    ↓")
        else:
            lines.append("No 4.7.1 TRACE_PRESENT_SUMMARY.json yet.")
            lines.append("Run experiments/run_update471_cross_agent_trace.py")
        # Selected agent note
        aid = getattr(self.controller.projector, "preferred_agent_id", None) or getattr(tick, "agent_id", None)
        lines.append(f"selected_agent={aid}")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")





    def _update_temporal_contingency_panel(self, tick) -> None:
        """Update 4.10 Observer: temporal contingency table (causally inert)."""
        widget = getattr(self, "temporal_contingency_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = [
            "TEMPORAL CONTINGENCY (Observer)  confidence≠value",
            "action|lag|status|support|conf|mean_energy_delta",
            "",
        ]
        # Live from agent mechanism state if present on tick
        ms = getattr(tick, "mechanism_states", None) or getattr(tick, "agent_mechanism_states", None)
        tc = None
        if isinstance(ms, dict):
            for block in ms.values():
                if isinstance(block, dict):
                    psy = block.get("psyche") or block
                    if isinstance(psy, dict):
                        sm = (psy.get("memory") or {}).get("sensorimotor") or {}
                        if isinstance(sm.get("temporal_contingency"), dict):
                            tc = sm["temporal_contingency"]
                            break
        if tc:
            lines.append(f"pending={len(tc.get('pending') or [])} n={len(tc.get('contingencies') or {})}")
            for key, rec in list((tc.get("contingencies") or {}).items())[:12]:
                md = (rec.get("mean_body_delta") or {})
                lines.append(
                    f"{rec.get('action')}|L{rec.get('lag')}|{rec.get('status')}|"
                    f"{rec.get('support')}|{float(rec.get('confidence') or 0):.2f}|"
                    f"{float(md.get('energy_signal') or 0):+.3f}"
                )
            bridge = None
            # try working diag from same psyche
        snap = Path("results/update410_temporal_contingency/UPDATE410_CAUSAL_CHAIN.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                fu = data.get("first_unsupported") or {}
                lines.append("")
                lines.append(f"FIRST_UNSUPPORTED: {fu.get('arrow')} = {fu.get('status')}")
                lines.append(f"POST MOVE={data.get('post_410_move')} USE={data.get('post_410_use')}")
            except Exception:
                pass
        lines.append("")
        lines.append("Does not feed cognition.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_prospective_temporal_economy_panel(self, tick) -> None:
        """Update 4.10.9 Observer: prospective temporal economy (inert)."""
        widget = getattr(self, "prospective_temporal_economy_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = ["PROSPECTIVE TEMPORAL ECONOMY (4.10.9 Observer)", ""]
        snap = Path("results/update4109_temporal_habit_alignment/OBSERVER_UPDATE4109_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                for row in (data.get("table") or [])[:4]:
                    lines.append(
                        f"{row.get('state')} t={row.get('tick')} habitW={row.get('HABIT_VALUE_WAIT')} "
                        f"USE={row.get('CURRENT_USE_ord')} WAIT={row.get('CURRENT_WAIT_ord')} "
                        f"ablated={row.get('habit_ablated_order')} shadow={row.get('shadow_order_vs_WAIT')}"
                    )
            except Exception as exc:
                lines.append(f"(error: {exc})")
        else:
            lines.append("(no snapshot yet)")
        lines += ["", "Shadow only; does not feed cognition."]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_bounded_prospective_trajectory_panel(self, tick) -> None:
        """Update 4.10.10 Observer: bounded trajectory + repetition-value channels (inert)."""
        widget = getattr(self, "bounded_prospective_trajectory_panel", None)
        if widget is None:
            return
        from pathlib import Path
        lines = ["BOUNDED PROSPECTIVE TRAJECTORY (4.10.10 Observer)", ""]
        snap = Path("results/update41010_bounded_prospective_trajectory/FOUR_WAY_COMPARISON.json")
        sem = Path("results/update41010_bounded_prospective_trajectory/TEMPORAL_RECORD_SEMANTICS_AUDIT.md")
        lines.append("Semantics: cumulative T0→TL per lag; DO NOT sum lags.")
        if snap.exists():
            import json
            rows = json.loads(snap.read_text())
            for r in rows[:4]:
                c = r.get("CANONICAL") or {}
                tr = r.get("TEMPORAL_REPETITION_SEPARATED_SHADOW") or {}
                lines.append(
                    f"{r.get('state')}: CANON {c.get('order')}  TEMPORAL+RVS {tr.get('order')}  "
                    f"bestH={tr.get('best_horizon')} USE={tr.get('USE')}"
                )
        else:
            lines.append("(no FOUR_WAY_COMPARISON.json yet)")
        lines.append("")
        lines.append("Channels: CANONICAL | HABIT_ABLATED | REPETITION_VALUE_SEPARATED | TEMPORAL_REPETITION_SEPARATED_SHADOW")
        lines.append("H10/H25 UNKNOWN without lags>3. Shadow only — not policy.")
        text = "\n".join(lines)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")





    def _apply_prospective_preset(self) -> None:
        name = str(self.prospective_preset_var.get() if hasattr(self, "prospective_preset_var") else "")
        # Populate existing controls only
        notes = [f"PRESET: {name}", ""]
        if "4.41" in name:
            self.world_dynamics_var.set("dynamic");self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual");self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed();self.status_var.set("4.41 Acquired Internal Dynamics");return
        if "4.40" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed(); self.status_var.set("4.40 Endogenous Predictive Signaling"); return
        if "4.39" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.39 Sensorimotor Dynamics")
            return
        if "4.38" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.38 Psyche Incubation")
            return
        if "4.37" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.37 Contingent Physical Futures")
            return
        if "4.36" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.36 Predictive Representation Sufficiency")
            return
        if "4.35" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.35 Predictive Structure Selection")
            return
        if "4.34" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.34 Multimodal Consequence Learning")
            return
        if "4.33" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.33 Conditional Prospection")
            return
        if "4.32" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.32 Learning-Mediated Futures")
            return
        if "4.31" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.31 Evidence-Producing Physical Action")
            return
        if "4.30" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.30 Unavoidable State Transition")
            return
        if "4.29" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.29 Predictive Reliability")
            return
        if "4.28" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.28 Predictive Scenario Competition")
            return
        if "4.27" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.27 Predictive Generalization")
            return
        if "4.26" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.26 Prospective Consequence Influence")
            return
        if "4.25" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.25 Instrumental Observation")
            return
        if "4.24" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.24 Endogenous Temporal Reference")
            return
        if "4.23" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.23 Prospective Trajectory Composition")
            return
        if "4.22" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.22 Multi-Scale Predictive Organization")
            return
        if "4.21" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.21 Predictive Compression")
            return
        if "4.20" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.20 Hierarchical Body Prediction")
            return
        if "4.19" in name:
            self.world_dynamics_var.set("dynamic"); self.perception_mode_var.set("multi-channel")
            self.cue_mode_var.set("perceptual"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self._world_changed()
            self.status_var.set("4.19 Context Formation")
            return
        if "4.18.2" in name:
            self.ticks_var.set(1000); self.seed_var.set(17)
            self.world_var.set("contextual-objects"); self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self.world_dynamics_var.set("DYNAMIC_WORLD"); self.perception_mode_var.set("MULTI_CHANNEL")
            self.cue_mode_var.set("PERCEPTUAL_CUE_ENABLED"); self.ecology_condition_var.set("DYNAMIC_SIGNAL")
            self.resistance_mode_var.set("OVERCOMEABLE"); self._world_changed()
            notes += ["free-policy dynamic physical ecology", "state-dependent local scalar emission",
                      "generic resistance + partial transformation", "no cognition/policy/value changes"]
        elif "4.11" in name:
            self.ticks_var.set(200)
            self.seed_var.set(17)
            notes += ["ticks=200", "seed=17", "focus=prospective self-state H1/H2/H3 + WAIT trajectory"]
        elif "4.12.1" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += ["ticks=120", "seed=17", "focus=missing-link MOVE@S:eMhMfL then compose USE→MOVE"]
        elif "4.12.2" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += ["ticks=120", "seed=17", "focus=same present / different history A vs B"]
        elif "4.18.1" in name:
            self.ticks_var.set(1000)
            self.seed_var.set(17)
            self.world_var.set("contextual-objects")
            self.memory_architecture_var.set("EXPERIENCE_GATED_V05")
            self.world_dynamics_var.set("DYNAMIC_WORLD")
            self.perception_mode_var.set("MULTI_CHANNEL")
            self.cue_mode_var.set("PERCEPTUAL_CUE_ENABLED")
            self._world_changed()
            notes += [
                "ticks=1000 default; arbitrary positive integer accepted (1000/5000/10000/25000/50000/100000 useful)",
                "seed=user configurable",
                "runner=free-policy Update 4.18.1 long-run",
                "focus=prospective-space development at checkpoints",
                "no pretraining · no forced actions · no policy/value coupling",
            ]
        elif "4.18" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += [
                "ticks=120",
                "seed=17",
                "runner=real Update 4.18 measurement matrix",
                "focus=locally non-positive prefixes → positive composed terminal state",
                "researcher measurement only · no policy/value propagation",
            ]
        elif "4.17" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += [
                "ticks=120",
                "seed=17",
                "runner=real Update 4.17 measurement matrix",
                "focus=old persistent expectation vs fresh comparable prediction",
                "researcher classification only · no conflict resolution/policy coupling",
            ]
        elif "4.16" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += [
                "ticks=120",
                "seed=17",
                "focus=persistent episode trace / partial realization / hard ablations",
                "bounds=1 active trace × 4 branches × 3 edges",
            ]
        elif "4.15" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += [
                "ticks=120",
                "seed=17",
                "focus=prospective continuity vs reconstruction",
            ]
        elif "4.14" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += [
                "ticks=120",
                "seed=17",
                "focus=multiple acquired consequences / legacy vs multi",
            ]
        elif "4.13.1" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += [
                "ticks=120",
                "seed=17",
                "focus=expectation history / X→Y adaptation / alternating XY",
            ]
        elif "4.13" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += [
                "ticks=120",
                "seed=17",
                "focus=expectation check / same event different histories",
                "statuses: NO_PREDICTIVE_BASELINE | PREDICTION_CONFIRMED | PREDICTION_MISMATCH",
            ]
        elif "4.12" in name:
            self.ticks_var.set(120)
            self.seed_var.set(17)
            notes += ["ticks=120", "seed=17", "focus=transition composition depth=2"]
        notes += ["", "COGNITION (existing): temporal contingency / state-conditioned / composition shadow-only"]
        notes += ["No ranking, no planning strength, no curiosity slider."]
        self._set_safe(getattr(self, "prospective_settings_panel", None), chr(10).join(notes))
        if hasattr(self, "run_setup_canvas"):
            self.run_setup_form.update_idletasks()
            self._update_run_setup_scrollregion()
            self.run_setup_canvas.yview_moveto(0.0)
        self.status_var.set(f"PRESET APPLIED: {name}")

    def _update_prospective_hub_panels(self, tick) -> None:
        """Update 4.12.2 Prospective Observer hub (inert; loads artifacts + live working)."""
        from pathlib import Path
        import json

        # CURRENT STATE from live prospective_self_state
        lines_cur = ["CURRENT STATE (psyche-visible)", ""]
        lines_act = ["ACTION FUTURES", "DIRECT = acquired from current real state", ""]
        lines_comp = ["COMPOSED FUTURES (no ranking)", ""]
        lines_hist = ["HISTORY COMPARISON", ""]
        lines_pred = ["PREDICTION CHECK", ""]
        pss = None
        composed = None
        try:
            psy = self._psyche_for_tick(tick) if hasattr(self, "_psyche_for_tick") else None
            if isinstance(psy, dict):
                pss = (psy.get("working") or {}).get("prospective_self_state")
                composed = (psy.get("working") or {}).get("composed_prospective_trajectories")
        except Exception:
            pass
        if isinstance(pss, dict):
            cur = pss.get("current_signals") or {}
            lines_cur.append(f"state_key={pss.get('state_key')}")
            lines_cur.append(
                "e={:.3f} h={:.3f} f={:.3f}".format(
                    float(cur.get("energy_signal") or 0),
                    float(cur.get("hydration_signal") or 0),
                    float(cur.get("fatigue_signal") or 0),
                )
            )
            lines_cur.append("WAIT is an evolving trajectory, not identity.")
            trajs = pss.get("trajectories") or {}
            for act in list(trajs)[:8]:
                lines_act.append(act)
                hz = (trajs.get(act) or {}).get("horizons") or {}
                for L in (1, 2, 3):
                    pack = hz.get(L) or hz.get(str(L)) or {}
                    st = pack.get("predicted_state") or {}
                    lines_act.append(
                        f"  H{L} {pack.get('status')} support={pack.get('support')} "
                        f"pred_e={st.get('energy_signal') if isinstance(st, dict) else None} "
                        f"match={pack.get('state_match')}"
                    )
        else:
            lines_cur.append("(no live prospective_self_state)")
            lines_act.append("(no live trajectories)")

        # Composed from live or artifact
        art412 = Path("results/update412_transition_composition/FOLLOWUP_AFTER.json")
        if art412.exists():
            try:
                j = json.loads(art412.read_text())
                lines_comp.append(f"4.12.1 follow-up status={j.get('status')} composition={j.get('composition')}")
                lines_comp.append(f"novelty={j.get('COMPLETE_SEQUENCE_PREVIOUSLY_SEEN')}")
                ea, eb = j.get("edge_a") or {}, j.get("edge_b") or {}
                lines_comp.append(f"A [{ea.get('provenance')}] {ea.get('action')} -> {ea.get('predicted_state_key')}")
                lines_comp.append(f"B [{eb.get('provenance')}] {eb.get('action')} -> {eb.get('predicted_state_key')}")
            except Exception as exc:
                lines_comp.append(str(exc))
        if isinstance(composed, dict):
            lines_comp.append(f"live keys={list(composed)[:6]}")
            counts = ((composed.get("depth2_tree") or {}).get("counts")) or {}
            if counts:
                lines_comp.append(f"depth2 DIRECT/COMPOSABLE/UNKNOWN={counts}")

        snap = Path("results/update4122_history_dependent_prospective_space/OBSERVER_PROSPECTIVE_SNAPSHOT.json")
        if snap.exists():
            try:
                j = json.loads(snap.read_text())
                sp = j.get("same_present") or {}
                lines_hist.append(f"SAME_PRESENT={sp.get('SAME_PRESENT')} PHYS={sp.get('PHYSICAL_AVAILABILITY_MATCHED')}")
                cmp_ = j.get("comparison") or {}
                lines_hist.append(f"A USE→MOVE={cmp_.get('A_USE_MOVE')}  B USE→MOVE={cmp_.get('B_USE_MOVE')}")
                lines_hist.append(f"A-only={cmp_.get('A_only')}")
                lines_hist.append(f"B-only={cmp_.get('B_only')}")
                lines_hist.append(f"shared={cmp_.get('A_and_B')}")
                lines_hist.append("Labels: REPRESENTABLE ONLY BY A/B — not intelligence scores.")
                pc = j.get("prediction_check_4121") or {}
                if pc:
                    lines_pred.append("From 4.12.1 first physical USE→MOVE:")
                    lines_pred.append(f"S1 error_e={(pc.get('error_s1') or {}).get('energy_signal')}")
                    lines_pred.append(f"S2 error_e={(pc.get('error_s2') or {}).get('energy_signal')}")
                    lines_pred.append("Errors kept per transition — no single success score.")
            except Exception as exc:
                lines_hist.append(str(exc))
        else:
            lines_hist.append("(run update4122 experiment to populate snapshot)")

        lines_exp = ["EXPECTATION CHECK", "measurement-only · no surprise/policy", ""]
        snap413 = Path("results/update413_prediction_violation/OBSERVER_EXPECTATION_SNAPSHOT.json")
        if snap413.exists():
            try:
                j413 = json.loads(snap413.read_text())
                cmp413 = j413.get("same_event_comparison") or {}
                lines_hist.append("")
                lines_hist.append("SAME PHYSICAL EVENT (4.13)")
                lines_hist.append(
                    "audit P/A/R={}/{}/{} H={}".format(
                        cmp413.get("SAME_PRESENT"),
                        cmp413.get("SAME_ACTION"),
                        cmp413.get("SAME_REALIZED_CONSEQUENCE"),
                        cmp413.get("horizon"),
                    )
                )
                for row in (cmp413.get("rows") or [])[:6]:
                    lines_hist.append(
                        "{}: pred_e={} sup={} contrad={} absL1={} status={}".format(
                            row.get("psyche"),
                            row.get("prediction_energy"),
                            row.get("support"),
                            row.get("contradiction"),
                            row.get("abs_error_L1"),
                            row.get("violation_status"),
                        )
                    )
                lines_hist.append("Same abs error can differ in epistemic status by history.")

                def _brief(label, pack):
                    if not isinstance(pack, dict):
                        return
                    exp = pack.get("expected") or {}
                    epi = exp.get("epistemic") or {}
                    viol = pack.get("violation") or {}
                    pred = exp.get("predicted_state") or {}
                    real = (pack.get("realized") or {}).get("realized_state") or {}
                    lines_exp.append(str(label))
                    lines_exp.append(
                        "  EXPECTED H{} [{}] sk={} rec={} sup={} contrad={} conf={}".format(
                            pack.get("horizon"),
                            pack.get("provenance"),
                            pack.get("state_key"),
                            epi.get("status"),
                            epi.get("support"),
                            epi.get("contradiction"),
                            epi.get("confidence"),
                        )
                    )
                    if isinstance(pred, dict) and pred:
                        lines_exp.append(
                            "  pred e/h/f={:.4f}/{:.4f}/{:.4f}".format(
                                float(pred.get("energy_signal") or 0),
                                float(pred.get("hydration_signal") or 0),
                                float(pred.get("fatigue_signal") or 0),
                            )
                        )
                    if isinstance(real, dict) and real:
                        lines_exp.append(
                            "  REALIZED e/h/f={:.4f}/{:.4f}/{:.4f}".format(
                                float(real.get("energy_signal") or 0),
                                float(real.get("hydration_signal") or 0),
                                float(real.get("fatigue_signal") or 0),
                            )
                        )
                    ae = viol.get("absolute_error") or {}
                    se = viol.get("signed_error") or {}
                    lines_exp.append(
                        "  VIOLATION status={} src={} absL1={}".format(
                            viol.get("status"),
                            viol.get("violation_source"),
                            viol.get("absolute_error_L1"),
                        )
                    )
                    if ae:
                        lines_exp.append(
                            "  abs e/h/f={}/{}/{}".format(
                                ae.get("energy_signal"),
                                ae.get("hydration_signal"),
                                ae.get("fatigue_signal"),
                            )
                        )
                    if se:
                        lines_exp.append(
                            "  signed e/h/f={}/{}/{}".format(
                                se.get("energy_signal"),
                                se.get("hydration_signal"),
                                se.get("fatigue_signal"),
                            )
                        )
                    lines_exp.append("  standardized_error=omitted (no component σ in TC)")
                    lines_exp.append("")

                _brief("MATCH (strong, qty matched)", j413.get("match_H3"))
                _brief("VIOLATION (strong, empty object)", j413.get("strong_violation_H3"))
                _brief("UNKNOWN same event", j413.get("unknown_H3"))
                composed413 = j413.get("composed") or {}
                loc = composed413.get("localization") or {}
                lines_exp.append("COMPOSED localization={}".format(loc.get("attribution")))
                lines_exp.append(
                    "  edge1={} edge2={}".format(
                        ((composed413.get("edge_1") or {}).get("violation") or {}).get("status"),
                        ((composed413.get("edge_2") or {}).get("violation") or {}).get("status"),
                    )
                )
                lines_exp.append("semantics: contradiction = directional EMA, not σ")
            except Exception as exc:
                lines_exp.append(str(exc))
        else:
            lines_exp.append("(run update413 experiment to populate snapshot)")

        self._set_safe(getattr(self, "prospective_current_state_panel", None), chr(10).join(lines_cur))
        self._set_safe(getattr(self, "prospective_action_futures_panel", None), chr(10).join(lines_act))
        self._set_safe(getattr(self, "prospective_composed_futures_panel", None), chr(10).join(lines_comp))
        self._set_safe(getattr(self, "prospective_history_comparison_panel", None), chr(10).join(lines_hist))
        self._set_safe(getattr(self, "prospective_prediction_check_panel", None), chr(10).join(lines_pred))
        # Update 4.13.1 expectation history timeline
        snap4131 = Path("results/update4131_expectation_adaptation/OBSERVER_EXPECTATION_HISTORY.json")
        if snap4131.exists():
            try:
                jh = json.loads(snap4131.read_text())
                lines_exp.append("")
                lines_exp.append("EXPECTATION HISTORY")
                lines_exp.append("#  regime  expected_e  realized_e  absL1  status  support  contrad")
                for row in (jh.get("adaptation_timeline") or [])[-18:]:
                    lines_exp.append(
                        "{i:>2} {regime}  {ee}  {re}  {a}  {st}  {sup}  {c}".format(
                            i=row.get("i"),
                            regime=row.get("regime"),
                            ee=row.get("expected_e"),
                            re=row.get("realized_e"),
                            a=row.get("abs_L1"),
                            st=row.get("status"),
                            sup=row.get("support"),
                            c=row.get("contradiction"),
                        )
                    )
                lines_exp.append("")
                lines_exp.append("ALTERNATING OBSERVED vs CURRENT PREDICTION")
                lines_exp.append("observed: " + " ".join(jh.get("alternating_observed_regimes") or []))
                pred = jh.get("alternating_current_prediction") or {}
                if isinstance(pred, dict) and pred:
                    lines_exp.append(
                        "current prediction e/h/f={}/{}/{}".format(
                            pred.get("energy_signal"),
                            pred.get("hydration_signal"),
                            pred.get("fatigue_signal"),
                        )
                    )
                lines_exp.append("UNOBSERVED_MEAN_PREDICTION=" + str(jh.get("UNOBSERVED_MEAN_PREDICTION")))
                lines_exp.append("Z previously observed: NO" if jh.get("UNOBSERVED_MEAN_PREDICTION") == "YES" else "Z previously observed: n/a")
            except Exception as exc:
                lines_exp.append("4131 history: " + str(exc))

        lines_acq = ["ACQUIRED CONSEQUENCES", "legacy EMA vs multi-modes · no ranking/value", ""]
        snap414 = Path("results/update414_multiple_acquired_consequences/OBSERVER_ACQUIRED_CONSEQUENCES.json")
        if snap414.exists():
            try:
                j414 = json.loads(snap414.read_text())
                leg = j414.get("legacy") or {}
                multi = j414.get("multi") or {}
                pack = multi.get("pack") or {}
                lines_acq.append("LEGACY_SINGLE_EMA")
                lines_acq.append(
                    "  status={} support={} contrad={}".format(
                        leg.get("status"), leg.get("support"), leg.get("contradiction")
                    )
                )
                ps = leg.get("predicted_state") or {}
                if ps:
                    lines_acq.append(
                        "  pred e/h/f={:.4f}/{:.4f}/{:.4f}".format(
                            float(ps.get("energy_signal") or 0),
                            float(ps.get("hydration_signal") or 0),
                            float(ps.get("fatigue_signal") or 0),
                        )
                    )
                lines_acq.append("")
                lines_acq.append("MULTI_CONSEQUENCE  n_supported={}".format(pack.get("n_supported")))
                for i, c in enumerate((pack.get("consequences") or [])[:6], 1):
                    st = c.get("predicted_state") or {}
                    lines_acq.append(
                        "CONSEQUENCE {} id={} support={} spread_mad={}".format(
                            i, c.get("id"), c.get("support"), c.get("spread_mad")
                        )
                    )
                    lines_acq.append(
                        "  pred e/h/f={:.4f}/{:.4f}/{:.4f}  provenance={}".format(
                            float(st.get("energy_signal") or 0),
                            float(st.get("hydration_signal") or 0),
                            float(st.get("fatigue_signal") or 0),
                            c.get("provenance"),
                        )
                    )
                zc = j414.get("zcheck") or {}
                lines_acq.append("")
                lines_acq.append(
                    "legacy_near_Z={} multi_recovers_XY={}".format(
                        zc.get("legacy_near_unobserved_Z"), zc.get("multi_recovers_XY")
                    )
                )
                comp = j414.get("composition") or {}
                lines_acq.append(
                    "COMPOSITION_FROM_UNOBSERVED_MEAN={} branches={}".format(
                        comp.get("COMPOSITION_FROM_UNOBSERVED_MEAN"), comp.get("n_branches")
                    )
                )
                # also annotate action futures / history
                lines_act.append("")
                lines_act.append("CONSEQUENCE BRANCHES (one action → multiple outcomes)")
                for i, c in enumerate((pack.get("consequences") or [])[:4], 1):
                    lines_act.append(
                        "  USE consequence {} support={}".format(c.get("id"), c.get("support"))
                    )
                lines_hist.append("")
                lines_hist.append("4.14 alternating observed (research labels only):")
                lines_hist.append(" ".join(j414.get("alternating_observed_researcher_labels") or [])[:120])
                lines_hist.append("retained multi n_supported={}".format(pack.get("n_supported")))
                lines_comp.append("")
                lines_comp.append("4.14 consequence branching → compose independently")
                lines_comp.append(
                    "COMPOSITION_FROM_UNOBSERVED_MEAN={}".format(comp.get("COMPOSITION_FROM_UNOBSERVED_MEAN"))
                )
                lines_exp.append("")
                lines_exp.append("4.14 violation vs multi modes:")
                viol = j414.get("violation") or {}
                lines_exp.append("  realize Y → {}".format((viol.get("Y") or {}).get("status")))
                lines_exp.append("  realize X → {}".format((viol.get("X") or {}).get("status")))
            except Exception as exc:
                lines_acq.append(str(exc))
        else:
            lines_acq.append("(run update414 experiment to populate snapshot)")

        self._set_safe(getattr(self, "prospective_expectation_check_panel", None), chr(10).join(lines_exp))

        lines_cont = ["CURRENT EPISODE TRACE", "mechanism state · no value/policy coupling", ""]
        live416 = None
        try:
            psy416 = self._psyche_for_tick(tick) if hasattr(self, "_psyche_for_tick") else None
            if isinstance(psy416, dict):
                live416 = (psy416.get("working") or {}).get("prospective_trace_continuity")
        except Exception:
            live416 = None
        if isinstance(live416, dict):
            current = live416.get("current_episode_trace") or {}
            fresh = live416.get("fresh_reconstruction") or {}
            lines_cont.append("Trace ID: {}".format(current.get("trace_id")))
            lines_cont.append("Created: tick {}".format(current.get("created_tick")))
            lines_cont.append("Status: {}".format(current.get("status")))
            for branch in (current.get("branches") or [])[:4]:
                lines_cont.append("branch {} consequence={} status={}".format(
                    branch.get("branch_id"), branch.get("consequence_group_id"), branch.get("status")
                ))
                position = int(branch.get("current_position") or 0)
                for index, node in enumerate((branch.get("nodes") or [])[:3]):
                    marker = "✓" if index < position else ("×" if node.get("compatibility") not in (None, "PENDING") else "→")
                    lines_cont.append("  {} {} · predicted t{} · {}".format(
                        marker, node.get("predicted_state_key"), node.get("prediction_created_tick"), node.get("provenance")
                    ))
            lines_cont += ["", "FRESH RECONSTRUCTION"]
            if fresh:
                lines_cont.append("Trace ID: {} · Created: tick {}".format(fresh.get("trace_id"), fresh.get("created_tick")))
            else:
                lines_cont.append("unavailable (ablated or no compatible acquired path)")
            lines_cont.append("ACQUIRED CONSEQUENCES: separate memory structure")

        snap416 = Path("results/update416_persistent_prospective_trace/OBSERVER_CONTINUITY_SNAPSHOT.json")
        if not isinstance(live416, dict) and snap416.exists():
            try:
                j416 = json.loads(snap416.read_text())
                mx416 = j416.get("matrix") or {}
                base416 = j416.get("current_episode_trace") or {}
                lines_cont.append("PROSPECTIVE_CONTINUITY=" + str(mx416.get("PROSPECTIVE_CONTINUITY")))
                lines_cont.append("PROSPECTIVE_RECONSTRUCTION=" + str(mx416.get("PROSPECTIVE_RECONSTRUCTION")))
                lines_cont.append("Trace ID: {} · Created: tick {}".format(base416.get("trace_id"), base416.get("created_tick")))
                lines_cont.append("Status: {}".format(base416.get("status")))
                lines_cont.append("retained tail nodes={}".format(len(j416.get("retained_tail") or [])))
                lines_cont.append("")
                lines_cont.append("FRESH RECONSTRUCTION: " + str(j416.get("fresh_reconstruction_status")))
            except Exception as exc:
                lines_cont.append(str(exc))
        snap415 = Path("results/update415_prospective_continuity/OBSERVER_CONTINUITY_SNAPSHOT.json")
        if not isinstance(live416, dict) and not snap416.exists() and snap415.exists():
            try:
                j415 = json.loads(snap415.read_text())
                mx = j415.get("matrix") or {}
                lines_cont.append("PROSPECTIVE_CONTINUITY=" + str(mx.get("PROSPECTIVE_CONTINUITY")))
                lines_cont.append("PROSPECTIVE_RECONSTRUCTION=" + str(mx.get("PROSPECTIVE_RECONSTRUCTION")))
                base = j415.get("baseline") or {}
                lines_cont.append("CREATED t={} trace={}".format(base.get("created_tick"), base.get("trace_id")))
                lines_cont.append("nodes={}".format(base.get("n_nodes")))
                part = j415.get("partial") or {}
                lines_cont.append("")
                lines_cont.append("REALITY first_edge=" + str(part.get("FIRST_EDGE")))
                lines_cont.append("OLD TAIL (log)=" + str(part.get("OLD_TAIL_IN_RESEARCHER_LOG")))
                lines_cont.append("OLD TAIL (mechanism)=" + str(part.get("OLD_TAIL_AVAILABLE_TO_PROSPECTIVE_MECHANISM")))
                lines_cont.append("FRESH RECONSTRUCTION=" + str(part.get("FRESH_RECONSTRUCTION_AVAILABLE")))
                lines_cont.append("TRACE same/new=" + ("same" if part.get("same_trace_ids") else "new"))
                lines_cont.append("old_id={} fresh_id={}".format(part.get("old_trace_id"), part.get("fresh_trace_id")))
                ab = j415.get("ablation_recon") or {}
                lines_cont.append("")
                lines_cont.append("ABLATION recon_available=" + str(ab.get("RECONSTRUCTION_AVAILABLE_AFTER_ABLATION")))
                multi = j415.get("multi_x") or {}
                lines_cont.append("")
                lines_cont.append("CURRENT EPISODE branch class=" + str((multi.get("episode_resolution_class_hypothesis"))))
                for row in (multi.get("after_compat") or [])[:4]:
                    lines_cont.append(
                        "  {} compat={} support={}".format(
                            row.get("consequence_id"),
                            (row.get("compatibility") or {}).get("status"),
                            row.get("support"),
                        )
                    )
                lines_cont.append("ACQUIRED CONSEQUENCES: separate from episode (see 4.14 panel)")
                lines_exp.append("")
                lines_exp.append("4.15 continuity=" + str(mx.get("PROSPECTIVE_CONTINUITY")))
                lines_exp.append("4.15 reconstruction=" + str(mx.get("PROSPECTIVE_RECONSTRUCTION")))
            except Exception as exc:
                lines_cont.append(str(exc))
        if not isinstance(live416, dict) and not snap416.exists() and not snap415.exists():
            lines_cont.append("(run update416 experiment to populate snapshot)")

        # Update 4.17: compact researcher-only comparison inside the existing
        # continuity panel.  The relation is never written into psyche state.
        relation417 = None
        if isinstance(live416, dict):
            try:
                from mechanistic_mind.research.prospective_conflict import compare_trace_sets
                relation417 = compare_trace_sets(
                    live416.get("current_episode_trace"),
                    live416.get("fresh_reconstruction"),
                )
            except Exception:
                relation417 = None
        snap417 = Path("results/update417_prospective_conflict/OBSERVER_CONFLICT_SNAPSHOT.json")
        if relation417 is None and snap417.exists():
            try:
                relation417 = (json.loads(snap417.read_text()).get("conflict") or None)
            except Exception:
                relation417 = None
        lines_cont += ["", "OLD vs FRESH · researcher only"]
        if isinstance(relation417, dict):
            lines_cont.append("OLD {} · t{}".format(
                relation417.get("old_trace_id"), relation417.get("old_created_tick")
            ))
            lines_cont.append("FRESH {} · t{}".format(
                relation417.get("fresh_trace_id"), relation417.get("fresh_created_tick")
            ))
            lines_cont.append("Comparable relation: {}".format(relation417.get("relation")))
            pairs = relation417.get("incompatible_pairs") or relation417.get("compatible_pairs") or []
            if pairs:
                lines_cont.append("action={} H{} · L1={}".format(
                    pairs[0].get("comparison_action"), pairs[0].get("comparison_horizon"),
                    pairs[0].get("absolute_L1"),
                ))
            lines_cont.append("Policy coupling: {}".format(relation417.get("policy_coupling")))
        else:
            lines_cont.append("(no concurrent comparable representations)")

        # Update 4.18: artifact-backed researcher view.  It is intentionally
        # displayed here rather than placed in psyche state.
        snap418 = Path("results/update418_composed_future_value/OBSERVER_COMPOSED_VALUE_SNAPSHOT.json")
        lines_cont += ["", "PROSPECTIVE · COMPOSED VALUE HORIZON"]
        if snap418.exists():
            try:
                value418 = json.loads(snap418.read_text())
                lines_cont.append("START STATE " + str(value418.get("start_state")))
                for depth in value418.get("depths") or []:
                    for branch in (depth.get("branches") or [])[:4]:
                        ordinary = (branch.get("ordinary_valuation") or {}).get("ordinary_value")
                        edges = branch.get("edges") or []
                        lines_cont.append("depth {} · {}".format(
                            depth.get("depth"), " → ".join(str(e.get("action")) for e in edges)
                        ))
                        lines_cont.append("  state={} · ordinary value={:+.6f} · provenance={}".format(
                            branch.get("state"), float(ordinary or 0.0),
                            (edges[-1].get("provenance") if edges else "UNKNOWN"),
                        ))
                        lines_cont.append("  supports={}".format([e.get("support") for e in edges]))
                lines_cont.append("VALUE HORIZON: {}".format(value418.get("value_horizon")))
                lines_cont.append("COMPLETE SEQUENCE PREVIOUSLY SEEN: {}".format(
                    value418.get("complete_sequence_previously_seen")))
                lines_cont.append("POLICY COUPLING: {}".format(value418.get("policy_coupling")))
            except Exception as exc:
                lines_cont.append("snapshot error: " + str(exc))
        else:
            lines_cont.append("(run 4.18 preset to populate snapshot)")

        snap4181 = Path("results/update4181_prospective_space_development/OBSERVER_DEVELOPMENT_SNAPSHOT.json")
        lines_cont += ["", "PROSPECTIVE · DEVELOPMENT"]
        if snap4181.exists():
            try:
                dev = json.loads(snap4181.read_text()); cur = dev.get("current") or {}; first = dev.get("first_emergence") or {}
                lines_cont += [
                    "TICK {} · EXPERIENCE {} · TRANSITIONS {}".format(cur.get("tick"), cur.get("experience_count"), cur.get("supported_transition_count")),
                    "D1 {} · D2 {} · D3 {} · UNKNOWN {}".format(cur.get("known_depth1"), cur.get("known_depth2"), cur.get("known_depth3"), cur.get("unknown_count")),
                    "BRANCHES {} · DEEPEST {}".format(cur.get("multi_consequence_count"), cur.get("deepest_supported_future")),
                    "POSITIVE HORIZONS D1/D2/D3: {}/{}/{}".format(cur.get("positive_depth1_count"), cur.get("positive_depth2_count"), cur.get("positive_depth3_count")),
                    "LOCAL− / DEEP+ {}".format(cur.get("locally_nonpositive_deeper_positive_count")),
                    "FIRST D2 {} · D3 {} · LOCAL−/DEEP+ {}".format(first.get("FIRST_DEPTH2_COMPOSITION"), first.get("FIRST_DEPTH3_COMPOSITION"), first.get("FIRST_LOCALLY_NONPOSITIVE_DEEPER_POSITIVE")),
                    "RECENT CURVE tick | D1 | D2 | D3",
                ]
                for row in dev.get("curve") or []:
                    lines_cont.append("{} | {} | {} | {}".format(row.get("tick"), row.get("known_depth1"), row.get("known_depth2"), row.get("known_depth3")))
            except Exception as exc:
                lines_cont.append("snapshot error: " + str(exc))
        else:
            lines_cont.append("(run 4.18.1 preset; checkpoint snapshots update live)")

        # Experiment-aware adapters (4.23–4.27): richer Observer-only panels
        try:
            from mechanistic_mind.ui.psychology_observer.experiment_viz import lines_for_preset
            _preset = str(self.prospective_preset_var.get() if hasattr(self, "prospective_preset_var") else "")
            if any(k in _preset for k in ("4.23", "4.24", "4.25", "4.26", "4.27", "4.28", "4.29", "4.30", "4.31", "4.32", "4.33", "4.34", "4.35", "4.36", "4.37", "4.38", "4.39", "4.40", "4.41", "4.42", "4.43", "4.44", "4.45", "4.46", "4.47", "4.48", "4.49", "4.50", "4.51", "4.52", "4.53", "4.54", "4.55", "4.56", "4.57", "4.58", "4.59", "4.60", "4.61", "4.62", "4.63", "4.64", "4.65", "4.66", "4.67", "4.68", "4.69", "4.70", "4.71", "4.72", "4.73", "4.74", "4.75", "4.76")):
                lines_cont += [""] + lines_for_preset(_preset)
        except Exception as _viz_exc:
            lines_cont.append("experiment_viz error: " + str(_viz_exc))

        pci426 = Path("results/update426_prospective_consequence_influence/OBSERVER_PCI_SNAPSHOT.json")
        if pci426.exists() and self.prospective_preset_var.get() == "4.26 Prospective Consequence Influence":
            try:
                snap=json.loads(pci426.read_text()); agent=snap.get("CURRENT_AGENT_AVAILABLE") or {}; res=snap.get("RESEARCHER_ONLY") or {}
                d=res.get("deltas") or {}; pr=res.get("prospective") or {}
                lines_cont += ["", "4.26 PROSPECTIVE CONSEQUENCE INFLUENCE",
                    "AGENT probs={} (softmax; no GOAL/argmax)".format(agent.get("probs")),
                    "RESEARCHER shift_B={} A_comp={} B_comp={}".format(d.get("shift_toward_B"), pr.get("A_composition_success"), pr.get("B_composition_success"))]
            except Exception as exc:
                lines_cont.append("4.26 snapshot error: "+str(exc))

        io425 = Path("results/update425_instrumental_observation/OBSERVER_INSTRUMENTAL_SNAPSHOT.json")
        if io425.exists() and self.prospective_preset_var.get() == "4.25 Instrumental Observation":
            try:
                snap=json.loads(io425.read_text()); agent=snap.get("CURRENT_AGENT_AVAILABLE") or {}; res=snap.get("RESEARCHER_ONLY") or {}
                c1=res.get("C1") or {}; obs=res.get("obs_useful") or {}
                lines_cont += ["", "4.25 INSTRUMENTAL OBSERVATION",
                    "AGENT-AVAILABLE pred_count={} (no W identity / no TOOL)".format(agent.get("pred_count")),
                    "RESEARCHER C1={} class={} direct={} mediated={}".format(c1.get("assert_candidate"), c1.get("classification"), obs.get("direct_distinguishability"), obs.get("mediated_distinguishability"))]
            except Exception as exc:
                lines_cont.append("4.25 snapshot error: "+str(exc))

        et424 = Path("results/update424_endogenous_temporal/OBSERVER_TEMPORAL_SNAPSHOT.json")
        if et424.exists() and self.prospective_preset_var.get() == "4.24 Endogenous Temporal Reference":
            try:
                snap=json.loads(et424.read_text()); agent=snap.get("CURRENT_AGENT_AVAILABLE") or {}; res=snap.get("RESEARCHER_ONLY") or {}
                lines_cont += ["", "4.24 ENDOGENOUS TEMPORAL REFERENCE",
                    "AGENT-AVAILABLE state_pred={} traj_pred={} (no CLOCK)".format(agent.get("state_pred_count"), agent.get("traj_pred_count")),
                    "RESEARCHER wall/ticks are metrics only - see SAME_STATE_DIFF_HISTORY.json"]
            except Exception as exc:
                lines_cont.append("4.24 snapshot error: "+str(exc))

        pr423 = Path("results/update423_prospective_composition/OBSERVER_PROSPECTIVE_SNAPSHOT.json")
        if pr423.exists() and self.prospective_preset_var.get() == "4.23 Prospective Trajectory Composition":
            try:
                snap=json.loads(pr423.read_text()); agent=snap.get("CURRENT_AGENT_AVAILABLE") or {}; res=snap.get("RESEARCHER_ONLY") or {}
                nov=(res.get("novel") or {}); comp=nov.get("compose") or {}
                lines_cont += ["", "4.23 PROSPECTIVE TRAJECTORY COMPOSITION",
                    "AGENT-AVAILABLE transitions={}".format(agent.get("transitions")),
                    "RESEARCHER novel_success={} depth={} expansions={} (no GOAL/PLAN)".format(nov.get("novel_composition_success"), comp.get("max_depth_reached"), comp.get("expansion_count")),
                    "Exposure audit + provenance in results/update423_* — world future not agent-visible."]
            except Exception as exc:
                lines_cont.append("4.23 snapshot error: "+str(exc))

        ms422 = Path("results/update422_multiscale_prediction/OBSERVER_MULTISCALE_SNAPSHOT.json")
        if ms422.exists() and self.prospective_preset_var.get() == "4.22 Multi-Scale Predictive Organization":
            try:
                snap=json.loads(ms422.read_text()); agent=snap.get("CURRENT_AGENT_AVAILABLE") or {}; res=snap.get("RESEARCHER_ONLY") or {}
                rs=res.get("snap") or {}
                lines_cont += ["", "4.22 MULTI-SCALE PREDICTIVE ORGANIZATION",
                    "AGENT-AVAILABLE local={} relations={}".format(agent.get("local_structure_count"), agent.get("relation_count")),
                    "RESEARCHER broader={} depth_dist={} (not cognition labels)".format(rs.get("retained_broader_count"), rs.get("candidate_depth_distribution")),
                    "Expand via BROADER_STRUCTURES.json / PROVENANCE_AUDIT — GT G never agent-visible."]
            except Exception as exc:
                lines_cont.append("4.22 snapshot error: "+str(exc))

        mem421 = Path("results/update421_predictive_compression/OBSERVER_MEMORY_SNAPSHOT.json")
        if mem421.exists() and self.prospective_preset_var.get() == "4.21 Predictive Compression":
            try:
                snap=json.loads(mem421.read_text()); res=snap.get("RESEARCHER_ONLY") or {}; cost=res.get("cost") or {}
                lines_cont += ["", "4.21 PREDICTIVE COMPRESSION · MEMORY BROWSER",
                    "AGENT-AVAILABLE: {}".format(snap.get("CURRENT_AGENT_AVAILABLE")),
                    "RESEARCHER bytes={} structures_tick_proxy raw_removed in artifacts".format(cost.get("bytes_persistent")),
                    "ticks_lived={} raw_retained={} raw_removed={}".format(cost.get("ticks_lived"), cost.get("raw_retained"), cost.get("raw_removed")),
                    "Expand structures via results/.../PROVENANCE_AUDIT.json — not cognition."]
            except Exception as exc:
                lines_cont.append("4.21 snapshot error: "+str(exc))

        body420 = Path("results/update420_hierarchical_body_prediction/OBSERVER_BODY_SNAPSHOT.json")
        if body420.exists() and self.prospective_preset_var.get() == "4.20 Hierarchical Body Prediction":
            try:
                snap=json.loads(body420.read_text()); body=snap.get("BODY_GROUND_TRUTH") or {}; learned=snap.get("LEARNED_PREDICTIVE_EVIDENCE") or {}
                lines_cont += ["", "4.20 BODY PROCESSES · FIVE-LAYER SEPARATION",
                    "BODY GT process={}".format((body.get("process_state") or {})),
                    "AGENT-AVAILABLE: {}".format(snap.get("AGENT_AVAILABLE")),
                    "LEARNED local={} relations={}".format(learned.get("local_count"), learned.get("relation_count")),
                    "Never conflate WORLD/BODY GT, agent fragments, and learned evidence."]
            except Exception as exc:
                lines_cont.append("4.20 snapshot error: "+str(exc))

        ctx419 = Path("results/update419_context_formation/OBSERVER_CONTEXT_SNAPSHOT.json")
        if ctx419.exists() and self.prospective_preset_var.get() == "4.19 Context Formation":
            try:
                snap = json.loads(ctx419.read_text()); gt = snap.get("world_ground_truth") or {}; learned = snap.get("learned_internal") or {}; viol = snap.get("last_violation") or {}
                lines_cont += ["", "4.19 CONTEXT · WORLD GT / AGENT-AVAILABLE / LEARNED",
                    "GT phase={} tick={} keys={}".format(gt.get("phase"), gt.get("tick"), list((gt.get("field_summary") or {}).keys())[:6]),
                    "AGENT-AVAILABLE: {}".format(snap.get("agent_available")),
                    "LEARNED patterns={} obs={} mismatches={}".format(learned.get("pattern_count"), learned.get("total_observations"), learned.get("mismatch_events")),
                    "VIOLATION mismatch_delta={} (no agent notify)".format(viol.get("mismatch_delta")),
                    "Do not conflate GT, agent-available, and learned evidence."]
            except Exception as exc:
                lines_cont.append("4.19 snapshot error: "+str(exc))

        eco4182 = Path("results/update4182_dynamic_ecology/OBSERVER_ECOLOGY_SNAPSHOT.json")
        if eco4182.exists() and self.prospective_preset_var.get() == "4.18.2 Dynamic Sustaining Ecology":
            try:
                eco=json.loads(eco4182.read_text()); opp=eco.get("opportunities") or {}; d=eco.get("development") or {}
                lines_cont += ["", "DYNAMIC PHYSICAL ECOLOGY · RESEARCHER GROUND TRUTH",
                    "condition={} tick={}".format(eco.get("condition"),eco.get("tick")),
                    "SOURCE opportunities={} encounters={} interactions={}".format(opp.get("source_opportunities"),opp.get("source_encounters"),opp.get("actual_interactions")),
                    "SIGNAL exposures={} before-source={}".format(opp.get("signal_exposures"),opp.get("signal_before_source")),
                    "TRANSFORM partial={} complete={} ineffective={}".format(opp.get("partial_transformations"),opp.get("complete_transformations"),opp.get("ineffective_interactions")),
                    "RESISTANCE exposures={} impossible={} repeated-seq={}".format(opp.get("resistance_state_exposures"),opp.get("impossible_object_interactions"),opp.get("repeated_interaction_sequences")),
                    "ACTIVE={} WAIT={} · DEPTH={}".format(opp.get("active_ticks"),opp.get("wait_ticks"),d.get("deepest_supported_future")),
                    "GT vs agent: resistance/integrity/depletion/phase/trajectory are Observer-only;",
                    "agent receives local physical fragments only (no resistance label)."]
                phys_path = Path("results/update4182_dynamic_ecology/PHYSICAL_RESISTANCE_CONTROLS.json")
                if phys_path.exists():
                    phys = json.loads(phys_path.read_text()).get("summary") or {}
                    lines_cont += ["", "FORCED PHYSICAL CONTROLS (Category A; not free policy)",
                        "OVERCOMEABLE expose@{} · LOW@{} · IMPOSSIBLE never/n={} def={}".format(
                            phys.get("OVERCOMEABLE_contacts_to_expose"), phys.get("LOW_contacts_to_expose"),
                            phys.get("IMPOSSIBLE_never_exposes_over_n"), phys.get("IMPOSSIBLE_final_deformation")),
                        "PUSH reduces resistance={} fewer contacts={} · partial={} qty-deplete={}".format(
                            phys.get("PUSH_reduces_resistance"), phys.get("PUSH_fewer_contacts_to_expose"),
                            phys.get("partial_transformation_observed"), phys.get("quantity_depletes_after_expose"))]
            except Exception as exc:
                lines_cont.append("4.18.2 snapshot error: "+str(exc))

        self._set_safe(getattr(self, "prospective_acquired_consequences_panel", None), chr(10).join(lines_acq))
        self._set_safe(getattr(self, "prospective_continuity_trace_panel", None), chr(10).join(lines_cont))

    def _update_composed_prospective_trajectories_panel(self, tick) -> None:
        """Update 4.12 Observer: composed trajectories (inert, no ranking)."""
        widget = getattr(self, "composed_prospective_trajectories_panel", None)
        if widget is None:
            return
        lines = ["COMPOSED PROSPECTIVE TRAJECTORIES (4.12 Observer)", "shadow-only; no ranking", ""]
        payload = None
        try:
            psy = None
            if hasattr(self, "_psyche_for_tick"):
                psy = self._psyche_for_tick(tick)
            if isinstance(psy, dict):
                payload = (psy.get("working") or {}).get("composed_prospective_trajectories")
        except Exception:
            payload = None
        # Prefer experiment artifact if live payload thin
        from pathlib import Path
        import json
        art = Path("results/update412_transition_composition/COMPOSITION_PRESENT.json")
        if art.exists():
            try:
                art_j = json.loads(art.read_text())
                r = art_j.get("result") or {}
                lines.append(f"status={r.get('status')} composition={r.get('composition')}")
                lines.append(f"S0 {r.get('s0_key')}")
                ea = r.get("edge_a") or {}
                eb = r.get("edge_b") or {}
                lines.append(f"A [{ea.get('provenance')}] {ea.get('action')} L{ea.get('lag')} support={ea.get('support')} -> {ea.get('predicted_state_key')}")
                lines.append(f"B [{eb.get('provenance')}] {eb.get('action')} L{eb.get('lag')} support={eb.get('support')} -> {eb.get('predicted_state_key')}")
                lines.append(f"reason_B={eb.get('reason')}")
            except Exception as exc:
                lines.append(f"artifact read error: {exc}")
        if isinstance(payload, dict):
            lines.append("")
            lines.append(f"live sketch keys={list(payload)[:6]}")
            sk = payload.get("sketch_USE_then_WAIT") or {}
            if sk:
                lines.append(f"live USE→WAIT status={sk.get('status')} Ŝ1={sk.get('s_hat_1_key')} Ŝ2={sk.get('s_hat_2_key')}")
            counts = ((payload.get("depth2_tree") or {}).get("counts")) or {}
            if counts:
                lines.append(f"depth2 counts={counts}")
        text = chr(10).join(lines)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _update_prospective_self_state_panel(self, tick) -> None:
        """Update 4.11 Observer: prospective organism-state trajectories (inert)."""
        widget = getattr(self, "prospective_self_state_panel", None)
        if widget is None:
            return
        lines = ["PROSPECTIVE SELF-STATE (4.11 Observer)", ""]
        pss = None
        try:
            agent = getattr(self, "selected_agent_id", None) or getattr(self, "agent_id", None)
            # Prefer live working memory from tick payload
            psy = None
            if hasattr(self, "_psyche_for_tick"):
                psy = self._psyche_for_tick(tick)
            if isinstance(psy, dict):
                pss = ((psy.get("working") or {}).get("prospective_self_state"))
            if pss is None and hasattr(self, "latest_psychology"):
                lp = self.latest_psychology
                if isinstance(lp, dict):
                    pss = ((lp.get("working") or {}).get("prospective_self_state"))
        except Exception:
            pss = None
        if not isinstance(pss, dict):
            lines.append("(no prospective_self_state in working memory yet)")
        else:
            cur = pss.get("current_signals") or {}
            lines.append(f"state_key={pss.get('state_key')}")
            lines.append(
                "CURRENT e={:.3f} h={:.3f} f={:.3f}".format(
                    float(cur.get("energy_signal") or 0),
                    float(cur.get("hydration_signal") or 0),
                    float(cur.get("fatigue_signal") or 0),
                )
            )
            lines.append("aggregation=NONE  habit_in_path=False  SELF_token=False")
            lines.append("")
            trajs = pss.get("trajectories") or {}
            # Prefer WAIT + USE* then others
            keys = []
            if "WAIT" in trajs:
                keys.append("WAIT")
            keys.extend(sorted(k for k in trajs if str(k).startswith("USE")))
            keys.extend(sorted(k for k in trajs if k not in keys))
            for act in keys[:6]:
                tr = trajs.get(act) or {}
                lines.append(f"{act}")
                hz = tr.get("horizons") or {}
                for L in (1, 2, 3):
                    pack = hz.get(L) or hz.get(str(L)) or {}
                    st = pack.get("predicted_state") or {}
                    e = st.get("energy_signal") if isinstance(st, dict) else None
                    lines.append(
                        f"  H{L} status={pack.get('status')} support={pack.get('support')} "
                        f"conf={pack.get('confidence')} pred_e={e} match={pack.get('state_match')}"
                    )
            inter = pss.get("intervention_difference_A_minus_WAIT") or {}
            if inter:
                lines.append("")
                lines.append("INTERVENTION DIFFERENCE (A−WAIT; not value)")
                for act, diffs in list(inter.items())[:3]:
                    parts = []
                    for L in (1, 2, 3):
                        d = (diffs.get(L) or diffs.get(str(L)) or {})
                        delta = d.get("delta") or {}
                        parts.append(
                            f"H{L}:{d.get('status')}"
                            + (
                                f"(de={delta.get('energy_signal')})"
                                if isinstance(delta, dict) and delta.get("energy_signal") is not None
                                else ""
                            )
                        )
                    lines.append(f"  {act}: " + " ".join(parts))
        text = chr(10).join(lines)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _update_prospective_trajectory_calibration_panel(self, tick) -> None:
        """Update 4.10.11 Observer: trajectory calibration (inert)."""
        widget = getattr(self, "prospective_trajectory_calibration_panel", None)
        if widget is None:
            return
        from pathlib import Path
        import json
        lines = ["PROSPECTIVE TRAJECTORY CALIBRATION (4.10.11 Observer)", ""]
        summ = Path("results/update41011_trajectory_calibration/UPDATE41011_SUMMARY.json")
        lines.append("Prediction = EMA mean of absolute cumulative T0→TL deltas (no body-state key).")
        lines.append("Deterministic complete-state repeats under env=off.")
        if summ.exists():
            s = json.loads(summ.read_text())
            lines.append(
                f"deterministic={s.get('deterministic')} background_contamination={s.get('background_contamination')}"
            )
            lines.append(
                f"lags>3 justified={s.get('lags_gt3_justified')} valuation={s.get('temporal_valuation')}"
            )
            lines.append(
                f"S0 realized H3 abs={s.get('s0_realized_h3_energy')} USE-WAIT={s.get('s0_action_specific_h3_energy')}"
            )
        lines.append("H10/H25 cognitive UNKNOWN. No gamma/planning. Shadow only.")
        text = chr(10).join(lines)
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")


    def _update_ordinary_action_economy_panel(self, tick) -> None:
        """Update 4.10.8 Observer: ordinary action economy (inert)."""
        widget = getattr(self, "ordinary_action_economy_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = ["ORDINARY ACTION ECONOMY (4.10.8 Observer)", ""]
        snap = Path("results/update4108_ordinary_action_economy/OBSERVER_UPDATE4108_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                s0 = data.get("S0") or {}
                wc = s0.get("WAIT_values_components") or {}
                lines.append(f"S0 tick={s0.get('tick')} severe={s0.get('severe')} USE_avail={s0.get('USE_available')}")
                lines.append(f"WAIT habit={wc.get('habit')} reg={wc.get('regulation')} total={wc.get('base_total')}")
                uc = s0.get("USE_candidate") or {}
                lines.append(f"USE ordinary={uc.get('ordinary_action_value')} src={uc.get('source')}")
                lines.append(f"gap={s0.get('gap')} selected={s0.get('selected')}")
                lines.append(f"first_severe={data.get('first_severe')} tts={data.get('tts')}")
            except Exception as exc:
                lines.append(f"(error: {exc})")
        else:
            lines.append("(no snapshot yet)")
        lines += ["", "Does not feed cognition."]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_developmental_physiology_panel(self, tick) -> None:
        """Update 4.10.7 Observer: developmental physiology (inert)."""
        widget = getattr(self, "developmental_physiology_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = ["DEVELOPMENTAL PHYSIOLOGY (4.10.7 Observer)", ""]
        snap = Path("results/update4107_developmental_initialization/OBSERVER_UPDATE4107_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                lock = data.get("lock") or {}
                lines.append(f"rule={lock.get('physical_rule')}")
                lines.append(f"locked={lock.get('DERIVATION_LOCKED')} expected={lock.get('expected_severity')}")
                for row in (data.get("matrix") or [])[:4]:
                    lines.append(
                        f"{row.get('condition')}: sev0={row.get('severe_at0')} nonsev={row.get('non_severe_ticks')} "
                        f"first_sev={row.get('first_severe_tick')} active={row.get('first_active')} gapmin={row.get('min_gap')}"
                    )
            except Exception as exc:
                lines.append(f"(error: {exc})")
        else:
            lines.append("(no OBSERVER_UPDATE4107_SNAPSHOT.json)")
        lines.append("")
        lines.append("Does not feed cognition.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_natural_physiological_window_panel(self, tick) -> None:
        """Update 4.10.6 Observer: natural physiological window (inert)."""
        widget = getattr(self, "natural_physiological_window_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = [
            "NATURAL PHYSIOLOGICAL WINDOW (4.10.6 Observer)",
            "",
        ]
        snap = Path("results/update4106_natural_physiological_window/OBSERVER_UPDATE4106_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                lines.append(f"initial_severe={data.get('initial_severe')} release_severe={data.get('release_severe')}")
                lines.append(f"timing={data.get('timing_class')} outcome={data.get('outcome')}")
                sn = data.get("snapshot") or {}
                lines.append(f"KNOWN support={sn.get('support')} conf={sn.get('confidence')}")
                lines.append(f"mean_body_delta={sn.get('mean_body_delta')}")
                mg = data.get("min_gap") or {}
                lines.append(f"min_gap={mg.get('gap')} @ tick {mg.get('tick')}")
                lines.append(f"free500={data.get('free500')}")
                t1 = data.get("tick1") or {}
                lines.append("")
                lines.append(f"t1 sev={t1.get('severity')} USE={t1.get('USE_score')} WAIT={t1.get('WAIT_score')} gap={t1.get('gap')}")
                lines.append(f"selected={t1.get('selected')}")
            except Exception as exc:
                lines.append(f"(snapshot error: {exc})")
        else:
            lines.append("(no OBSERVER_UPDATE4106_SNAPSHOT.json)")
        lines.append("")
        lines.append("Does not feed cognition.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_action_economics_panel(self, tick) -> None:
        """Update 4.10.5 Observer: WAIT vs USE score economy (inert)."""
        widget = getattr(self, "action_economics_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = [
            "ACTION ECONOMICS (4.10.5 Observer)",
            "score = ordinary - (0.35+0.04 if severe & active)",
            "",
        ]
        snap = Path("results/update4105_action_economics/OBSERVER_UPDATE4105_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                body = data.get("body") or {}
                lines.append(f"hydration={body.get('hydration_signal')} energy={body.get('energy_signal')} severe={data.get('severe')}")
                lines.append(f"USE ordinary={data.get('USE_ordinary')} penalty={data.get('USE_penalty')} score={data.get('USE_score')}")
                lines.append(f"WAIT score={data.get('WAIT_score')} selected={data.get('selected')}")
                lines.append("")
                for row in (data.get("ledger") or [])[:6]:
                    lines.append(f"{row.get('label')}: ord={row.get('ordinary_action_value')} pen={row.get('severe_total_penalty')} score={row.get('reconstructed_score')}")
            except Exception as exc:
                lines.append(f"(snapshot error: {exc})")
        else:
            lines.append("(no OBSERVER_UPDATE4105_SNAPSHOT.json)")
        lines.append("")
        lines.append("Does not feed cognition.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_predictive_utilization_panel(self, tick) -> None:
        """Update 4.10.3 Observer: KNOWN->retrieval->prediction->value (inert)."""
        widget = getattr(self, "predictive_utilization_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = [
            "PREDICTIVE UTILIZATION (4.10.3 Observer)",
            "KNOWN -> RETRIEVAL -> PAYLOAD -> PREDICTION -> VALUE -> CANDIDATE",
            "",
        ]
        snap = Path("results/update4104_schema_alignment/OBSERVER_UPDATE4104_SNAPSHOT.json")
        if not snap.exists():
            snap = Path("results/update4103_predictive_utilization/OBSERVER_UPDATE4103_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                fu = data.get("first_unsupported") or {}
                num = data.get("numeric") or {}
                lines.append(f"stored/retrieved energy_signal present; mapped_signal_deltas={num.get('mapped_signal_deltas')}")
                lines.append(f"ordinary_value={num.get('ordinary_value')} selected={num.get('selected')}")
                lines.append("")
                pp = data.get("pre_post") or {}
                post = (pp.get("POST") or {})
                if post:
                    lines.append("SCHEMA ALIGNMENT POST map nonempty; see snapshot")
                    lines.append(f"POST ordinary_value={post.get('prospective_ordinary_value')} selected={post.get('selected')}")
                lines.append(f"FIRST_UNSUPPORTED: {fu.get('arrow')}")
                lines.append(f"status={fu.get('status')}")
                if fu.get("mechanism"):
                    lines.append(f"mechanism: {fu.get('mechanism')}")
                lines.append("")
                for row in (data.get("stages") or [])[:9]:
                    lines.append(
                        f"{row.get('STAGE')}: out_nz={row.get('OUTPUT_NONZERO')} "
                        f"{row.get('STATUS')} fail={row.get('FIRST_FAILURE')}"
                    )
            except Exception as exc:
                lines.append(f"(snapshot error: {exc})")
        else:
            lines.append("(no OBSERVER_UPDATE4103_SNAPSHOT.json yet)")
        lines.append("")
        lines.append("Does not feed cognition. Diagnostic only.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_action_execution_attribution_panel(self, tick) -> None:
        """Update 4.10.2 Observer: POLICY / EXECUTION / PHYSICS / TEMPORAL (inert)."""
        widget = getattr(self, "action_execution_attribution_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = [
            "ACTION EXECUTION ATTRIBUTION (4.10.2 Observer)",
            "POLICY | EXECUTION | PHYSICS | TEMPORAL — cognition lacks override labels",
            "",
        ]
        # Live evidence from psyche working
        selected = executed = tkey = opened = None
        source_obs = None
        try:
            ms = getattr(tick, "mechanism_states", None) or getattr(tick, "agent_mechanism_states", None)
            if isinstance(ms, dict):
                for block in ms.values():
                    if not isinstance(block, dict):
                        continue
                    psy = block.get("psyche") or block
                    if not isinstance(psy, dict):
                        continue
                    working = psy.get("working") or {}
                    ev = working.get("action_execution_evidence") or {}
                    sel = working.get("last_selection") or {}
                    if isinstance(ev, dict) and ev:
                        selected = ev.get("selected_action")
                        executed = ev.get("executed_action")
                        tkey = ev.get("temporal_action_key")
                        opened = ev.get("temporal_opened")
                    if isinstance(sel, dict) and sel.get("action") is not None:
                        selected = selected or sel.get("action")
                    break
            source_obs = getattr(tick, "action_source", None) or getattr(tick, "action_sources", None)
        except Exception:
            pass
        lines.append(f"POLICY selected={selected}")
        lines.append(f"EXECUTION executed={executed}")
        lines.append(f"TEMPORAL key={tkey} opened={opened}")
        if source_obs is not None:
            lines.append(f"OBSERVER_ONLY source={source_obs}")
        snap = Path("results/update4102_executed_action_attribution/OBSERVER_UPDATE4102_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                ba = data.get("before_after") or {}
                lines.append("")
                lines.append("BEFORE/AFTER forced USE/MOVE:")
                for label in ("PRE_forced_USE", "POST_forced_USE", "PRE_forced_MOVE", "POST_forced_MOVE"):
                    row = ba.get(label) or {}
                    lines.append(
                        f"  {label}: sel={row.get('selected')} exec={row.get('executed')} "
                        f"key={row.get('temporal_key')} records={row.get('USE_records', row.get('MOVE_records'))}"
                    )
                chain = data.get("chain") or {}
                ufu = chain.get("use_first_unsupported") or {}
                mfu = chain.get("move_first_unsupported") or {}
                lines.append("")
                lines.append(f"USE frontier: {ufu.get('arrow')} = {ufu.get('status')}")
                lines.append(f"MOVE frontier: {mfu.get('arrow')} = {mfu.get('status')}")
            except Exception as exc:
                lines.append(f"(snapshot error: {exc})")
        lines.append("")
        lines.append("Does not feed cognition.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_ecological_stabilization_panel(self, tick) -> None:

        """Update 4.10.1 Observer: ecological contingency stabilization (inert)."""
        widget = getattr(self, "ecological_stabilization_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = [
            "ECOLOGICAL CONTINGENCY STABILIZATION (4.10.1 Observer)",
            "forced override ≠ selected; TC binds selection; confidence≠value",
            "",
        ]
        snap = Path("results/update4101_ecological_stabilization/OBSERVER_STABILIZATION_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                chain = data.get("chain") or {}
                ufu = chain.get("use_first_unsupported") or {}
                mfu = chain.get("move_first_unsupported") or {}
                lines.append(
                    f"USE known={data.get('use_became_known')} records={data.get('use_records')} "
                    f"threshold={((data.get('threshold_use') or {}).get('status'))}"
                )
                lines.append(
                    f"MOVE known={data.get('move_became_known')} records={data.get('move_records')} "
                    f"class={data.get('move_class')}"
                )
                free = data.get("free500") or {}
                lines.append(f"free500 WAIT={free.get('WAIT')} wait_only={free.get('wait_only')}")
                lines.append("")
                lines.append(f"USE first_unsupported: {ufu.get('arrow')} = {ufu.get('status')}")
                if ufu.get("note"):
                    lines.append(f"  note: {ufu.get('note')}")
                lines.append(f"MOVE first_unsupported: {mfu.get('arrow')} = {mfu.get('status')}")
                if mfu.get("note"):
                    lines.append(f"  note: {mfu.get('note')}")
                if data.get("note"):
                    lines.append("")
                    lines.append(str(data.get("note")))
            except Exception as exc:
                lines.append(f"(snapshot read error: {exc})")
        else:
            lines.append("(no OBSERVER_STABILIZATION_SNAPSHOT.json yet)")
        lines.append("")
        lines.append("Does not feed cognition. Ground truth ≠ organism experience.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_env_regulation_probe_panel(self, tick) -> None:

        """Update 4.9.1 Observer: compact regulation probe table (inert)."""
        widget = getattr(self, "env_regulation_probe_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = [
            "ENVIRONMENTAL REGULATION PROBE (Observer / experiment ground truth)",
            "tick | action | pos | avail | exchange | internal | bodyE | retrieval | selected",
            "",
        ]
        body = getattr(tick, "body_truth", None) or getattr(tick, "body", None) or {}
        world = getattr(tick, "objective_world", None) or {}
        pos = None
        try:
            ap = (world.get("agent_positions") or {})
            if ap:
                pos = list(ap.values())[0]
        except Exception:
            pos = None
        avail = None
        if pos is not None and isinstance(world.get("env_material_field"), dict):
            key = f"{int(pos[0])},{int(pos[1])}"
            avail = world["env_material_field"].get(key)
        lines.append(
            f"live: pos={pos} avail={avail} ex={body.get('last_env_exchange')} "
            f"int={body.get('internal_materials')} E={body.get('energy_reserve')}"
        )
        snap = Path("results/update491_environmental_regulation_probe/OBSERVER_PROBE_SNAPSHOT.json")
        if snap.exists():
            try:
                data = json.loads(snap.read_text())
                fu = data.get("first_unsupported") or {}
                lines.append("")
                lines.append(f"FIRST_UNSUPPORTED: {fu.get('arrow')} = {fu.get('status')}")
                lines.append(str(fu.get("reason") or "")[:200])
                auto = data.get("autonomous") or {}
                lines.append(f"AUTONOMOUS: wait_only={auto.get('wait_only')} counts={auto.get('action_counts')}")
                wi = auto.get("wait_interpretation") or {}
                lines.append(f"WAIT_WHY: {wi.get('earliest_explanation')}")
            except Exception:
                pass
        lines.append("")
        lines.append("Instrumentation is causally inert — not a context cue.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_env_causal_frontier_panel(self, tick) -> None:
        """Update 4.9.1 Observer: causal frontier stages table."""
        widget = getattr(self, "env_causal_frontier_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = ["Stage | Evidence | Status | Ref", "-" * 72]
        chain = Path("results/update491_environmental_regulation_probe/UPDATE491_CAUSAL_CHAIN.json")
        if chain.exists():
            try:
                data = json.loads(chain.read_text())
                for row in data.get("arrows") or []:
                    lines.append(
                        f"{row.get('stage')}|{row.get('evidence')}|{row.get('status')}|{row.get('ref')}"
                    )
                fu = data.get("first_unsupported") or {}
                lines.append("")
                lines.append(f"FIRST: {fu.get('arrow')} [{fu.get('status')}]")
            except Exception as exc:
                lines.append(f"(read error {exc})")
        else:
            lines.append("(run update 4.9.1 probe to populate)")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_world_organism_exchange_panel(self, tick) -> None:
        """Update 4.9 Observer: continuous local env exchange (physics only)."""
        widget = getattr(self, "world_organism_exchange_panel", None)
        if widget is None:
            return
        lines = [
            "LOCAL ENV → EXCHANGE → INTERNAL MATERIALS → PROCESSING → BODY",
            "",
        ]
        body = getattr(tick, "body_truth", None) or getattr(tick, "body", None) or {}
        world = getattr(tick, "objective_world", None) or {}
        if isinstance(body, dict):
            lines.append(f"last_env_availability={body.get('last_env_availability')}")
            lines.append(f"last_env_exchange={body.get('last_env_exchange')}")
            lines.append(f"last_intake_processed={body.get('last_intake_processed')}")
            lines.append(f"internal_materials={body.get('internal_materials')}")
            lines.append(
                f"energy={body.get('energy_reserve')} hydration={body.get('hydration')}"
            )
        field = world.get("env_material_field") if isinstance(world, dict) else None
        if isinstance(field, dict) and field:
            vals = [float(v) for v in field.values() if isinstance(v, (int, float))]
            if vals:
                lines.append("")
                lines.append(
                    f"env_field cells={len(vals)} min={min(vals):.3f} "
                    f"max={max(vals):.3f} mean={sum(vals)/len(vals):.3f}"
                )
        lines.append("")
        lines.append("MOVE affects exchange only via position → local availability.")
        lines.append("Observer ground truth does not enter cognition.")
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _update_physical_intake_panel(self, tick) -> None:
        """Update 4.8 Observer: physical intake & processing (not food semantics)."""
        widget = getattr(self, "physical_intake_panel", None)
        if widget is None:
            return
        import json
        from pathlib import Path
        lines = ["OBJECT → TRANSFER → INTERNAL → PROCESSING → BODY", ""]
        # Prefer live body truth on tick if fields exist
        body = getattr(tick, "body_truth", None) or getattr(tick, "body", None) or {}
        if isinstance(body, dict) and (
            body.get("internal_materials") is not None
            or body.get("last_intake_transfer") is not None
        ):
            lines.append(f"internal_materials={body.get('internal_materials')}")
            lines.append(f"last_transfer={body.get('last_intake_transfer')}")
            lines.append(f"last_processed={body.get('last_intake_processed')}")
            lines.append(f"energy={body.get('energy_reserve')} hydration={body.get('hydration')}")
        summary = Path("results/update48_bounded_intake/DELAYED_PROCESSING_SUMMARY.json")
        if summary.exists():
            try:
                data = json.loads(summary.read_text())
                series = data.get("series") or []
                lines.append("")
                lines.append("recent probe series (tick qty xfer internal proc energy):")
                for row in series[:8]:
                    lines.append(
                        f"{row.get('tick')}  qty={row.get('qty')}  xfer={row.get('xfer')}  "
                        f"int={row.get('internal_total')}  proc={row.get('proc')}  E={row.get('energy')}"
                    )
                lines.append("")
                lines.append("CHAIN: OBJECT STATE → TRANSFER → STORAGE → PROCESSING → BODY → EXPERIENCE")
                lines.append("association with earlier USE: ASSOCIATION_UNPROVEN / NULL until demonstrated")
            except Exception:
                pass
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n".join(lines))
        widget.configure(state="disabled")

    def _build_footer(self):
        footer = self._frame(self.root, "surface.navigation")
        footer.grid(row=2, column=0, sticky="ew")
        self.footer_label = self._label(
            footer,
            "Mechanistic Mind v0.4.0 • NO LEGACY EXPERIMENT ACTIVE",
            surface="surface.navigation",
            foreground="text.secondary",
            font=("TkDefaultFont", 8),
        )
        self.footer_label.pack(side="left", padx=14, pady=7)
        self._label(
            footer,
            "World truth and causal receipts remain observer-only",
            surface="surface.navigation",
            foreground="status.info",
            font=("TkDefaultFont", 8),
        ).pack(side="right", padx=14, pady=7)

    # ---------- execution ----------

    @property
    def current_runtime(self):
        """The sole Current MM simulation owner exposed through the UI adapter."""
        return self.planet_session.runtime

    @property
    def current_world(self):
        return self.current_runtime.world if self.current_runtime is not None else None

    @property
    def current_body(self):
        return self.current_runtime.body if self.current_runtime is not None else None

    @property
    def current_internal(self):
        return self.current_runtime.internal if self.current_runtime is not None else None

    def _mode_selector_changed(self, _event=None) -> None:
        """Map user-facing modes to existing view workspaces without touching state."""
        self.view_mode_var.set(
            "physical_world"
            if self.mode_selector_var.get() == "Current MM"
            else "organism"
        )
        self._view_mode_changed()

    def legacy_mode_snapshot(self):
        return legacy_mode_snapshot(
            enabled=bool(self.legacy_mode_enabled.get()),
            selected_preset=str(self.prospective_preset_var.get()),
            controller_is_active=bool(self.controller.is_active),
        )

    def _on_legacy_mode_toggled(self) -> None:
        """Explicit enter/exit historical experiment mode. No physics/RNG."""
        want = bool(self.legacy_mode_enabled.get())
        if want and getattr(self, "_planet_running", False):
            self.legacy_mode_enabled.set(False)
            messagebox.showinfo(
                "Legacy Experiments",
                "Pause Current MM before enabling Legacy Experiments.",
                parent=self.root,
            )
            return
        if not want and not can_disable_legacy_mode(
            controller_is_active=bool(self.controller.is_active)
        ):
            # Revert checkbox; require Stop first.
            self.legacy_mode_enabled.set(True)
            messagebox.showinfo(
                "Legacy Experiments",
                "A historical run is active. Stop it before disabling Legacy Experiments.",
                parent=self.root,
            )
            return
        self._apply_legacy_mode_chrome()


    def _left_managed_widgets(self) -> tuple:
        """Persistent left-panel widgets owned by view/legacy chrome (never destroyed)."""
        return (
            getattr(self, "current_setup_header", None),
            getattr(self, "current_setup_frame", None),
            getattr(self, "legacy_mode_header", None),
            getattr(self, "legacy_mode_gate_frame", None),
            getattr(self, "current_organism_null_header", None),
            getattr(self, "current_organism_null_frame", None),
            getattr(self, "legacy_setup_header", None),
            getattr(self, "legacy_setup_frame", None),
            getattr(self, "run_identity_header", None),
            getattr(self, "run_identity_frame", None),
            getattr(self, "ontology_header", None),
            getattr(self, "ontology_frame", None),
            getattr(self, "scientific_boundary_header", None),
            getattr(self, "scientific_boundary_frame", None),
        )

    def _pack_left_section(self, header, frame) -> None:
        """Pack header+frame at end of left column. Never use before= on forgotten widgets."""
        if header is not None:
            header.pack(anchor="w", padx=14, pady=(12, 5))
        if frame is not None:
            frame.pack(fill="x", padx=12)

    def _remount_left_workspace(self) -> None:
        """Deterministic left remount for view/legacy switches. UI-only; no Planet touch.

        Source cause of CURRENT-RUN-1.1: packing with before=run_identity_header while
        that header was pack_forget'ten raised TclError (swallowed), so current setup
        never remounted after organism ↔ physical_world round-trips.
        """
        if not hasattr(self, "left"):
            return
        pw = str(self.view_mode_var.get()) == "physical_world"
        legacy_on = bool(getattr(self, "legacy_mode_enabled", None) and self.legacy_mode_enabled.get())

        for w in self._left_managed_widgets():
            if w is None:
                continue
            try:
                w.pack_forget()
            except Exception:
                pass

        if pw:
            # CURRENT PHYSICAL WORLD — independent of legacy checkbox
            self._pack_left_section(
                getattr(self, "current_setup_header", None),
                getattr(self, "current_setup_frame", None),
            )
        else:
            # Organism view = historical workspace entry (no current organism runtime)
            self._pack_left_section(
                getattr(self, "legacy_mode_header", None),
                getattr(self, "legacy_mode_gate_frame", None),
            )
            if legacy_on:
                self._pack_left_section(
                    getattr(self, "legacy_setup_header", None),
                    getattr(self, "legacy_setup_frame", None),
                )
                self._pack_left_section(
                    getattr(self, "run_identity_header", None),
                    getattr(self, "run_identity_frame", None),
                )
                self._pack_left_section(
                    getattr(self, "ontology_header", None),
                    getattr(self, "ontology_frame", None),
                )
                self._pack_left_section(
                    getattr(self, "scientific_boundary_header", None),
                    getattr(self, "scientific_boundary_frame", None),
                )
            else:
                # Historical workspace explanation while Legacy is disabled.
                self._pack_left_section(
                    getattr(self, "current_organism_null_header", None),
                    getattr(self, "current_organism_null_frame", None),
                )

        # Start button availability follows legacy mode (refresh_buttons is authoritative)
        if hasattr(self, "start_button"):
            try:
                if pw or not legacy_on:
                    self.start_button.configure(state="disabled")
                # else leave to _refresh_buttons
            except Exception:
                pass
        if not pw and not legacy_on and not self.controller.is_active:
            try:
                self.run_var.set("No historical run")
                self.status_var.set("IDLE")
            except Exception:
                pass

    def _apply_legacy_mode_chrome(self) -> None:
        """Show/hide historical workspace from explicit legacy_mode_enabled."""
        if getattr(self, "_legacy_chrome_busy", False):
            return
        self._legacy_chrome_busy = True
        try:
            self._apply_legacy_mode_chrome_body()
        finally:
            self._legacy_chrome_busy = False

    def _apply_legacy_mode_chrome_body(self) -> None:
        enabled = bool(self.legacy_mode_enabled.get())
        self.legacy_mode_status_var.set(
            LEGACY_MODE_ON_STATUS if enabled else LEGACY_MODE_OFF_STATUS
        )
        pw = str(self.view_mode_var.get()) == "physical_world"

        # Left column: single remount path (CURRENT-RUN-1.1)
        self._remount_left_workspace()

        # Timeline: historical telemetry — hide when legacy OFF (organism) or PW
        if hasattr(self, "timeline_card") and hasattr(self, "center_splitter"):
            hide_timeline = pw or not enabled
            if hide_timeline:
                if getattr(self, "timeline_visible", False):
                    try:
                        self.center_splitter.forget(self.timeline_card)
                    except Exception:
                        pass
                    self.timeline_visible = False
                    self._timeline_hidden_by_legacy = True
                    try:
                        self.timeline_toggle_button.configure(text="Timeline ▼")
                    except Exception:
                        pass
            else:
                if getattr(self, "_timeline_hidden_by_legacy", False):
                    try:
                        self.center_splitter.add(
                            self.timeline_card,
                            height=getattr(self, "_timeline_height", 300),
                            minsize=90,
                            stretch="never",
                        )
                        self.timeline_visible = True
                        self._timeline_hidden_by_legacy = False
                        self.timeline_toggle_button.configure(text="Timeline ▲")
                    except Exception:
                        pass

        # Organism right panels: hide when legacy OFF (organism view)
        if not pw:
            for w in getattr(self, "_organism_right_sections", []):
                try:
                    if enabled:
                        w.pack(fill="x", padx=12, pady=(0, 8))
                    else:
                        w.pack_forget()
                except Exception:
                    pass

        self._refresh_buttons()


    def _world_changed(self, _event=None):

        world = self.world_var.get()
        obstacle_mode = world == "obstacle-value"
        organism_mode = world == "organism"
        persistent_mode = world == "persistent-targets"
        badges = {
            "organism": "ORGANISM × WORLD",
            "obstacle-value": "OBSTACLE × VALUE ECOLOGY",
            "persistent-targets": "PERSISTENT TARGETS",
            "contextual-objects": "CONTEXTUAL OBJECT ECOLOGY",
            "object-manipulation": "OBJECT MANIPULATION PROTOCOL",
        }
        if self.view_mode_var.get() == "physical_world":
            self.world_badge_var.set("CURRENT MM")
        else:
            self.world_badge_var.set(badges.get(world, world.upper()))
        obstacle_state = "readonly" if obstacle_mode else "disabled"
        persistent_state = "readonly" if persistent_mode else "disabled"
        organism_combo_state = "readonly" if organism_mode else "disabled"
        organism_entry_state = "normal" if organism_mode else "disabled"
        memory_state = (
            "readonly" if world == "contextual-objects" else "disabled"
        )
        if hasattr(self, "obstacle_combo"):
            self.obstacle_combo.configure(state=obstacle_state)
        if hasattr(self, "layout_combo"):
            self.layout_combo.configure(state=organism_combo_state)
        if hasattr(self, "persistent_combo"):
            self.persistent_combo.configure(state=persistent_state)
        if hasattr(self, "random_rate_entry"):
            self.random_rate_entry.configure(state=organism_entry_state)
        if hasattr(self, "memory_architecture_combo"):
            self.memory_architecture_combo.configure(state=memory_state)
        if hasattr(self, "run_setup_canvas"):
            self.run_setup_form.update_idletasks()
            self._update_run_setup_scrollregion()

    def start(self):
        if not bool(self.legacy_mode_enabled.get()):
            messagebox.showinfo(
                "Legacy Experiments",
                "No legacy experiment is active.\n"
                "Enable Legacy Experiments and select a historical experiment first.",
                parent=self.root,
            )
            return
        if logical_active_legacy_experiment(
            enabled=True,
            selected_preset=str(self.prospective_preset_var.get()),
        ) is None:
            messagebox.showinfo(
                "Legacy Experiments",
                "Select a historical experiment before Start Run.",
                parent=self.root,
            )
            return
        try:
            spec = PsychologyLaunchSpec(
                ticks=int(self.ticks_var.get()),
                seed=int(self.seed_var.get()),
                world=self.world_var.get(),
                resource_layout=self.layout_var.get(),
                random_event_rate=float(self.random_rate_var.get()),
                obstacle_condition=self.obstacle_condition_var.get(),
                persistent_condition=self.persistent_condition_var.get(),
                memory_architecture=self.memory_architecture_var.get(),
                world_dynamics=self.world_dynamics_var.get(),
                perception_mode=self.perception_mode_var.get(),
                cue_mode=self.cue_mode_var.get(),
                ecology_condition=self.ecology_condition_var.get(),
                resistance_mode=self.resistance_mode_var.get(),
                experiment_preset=self.prospective_preset_var.get(),
                tick_delay_ms=(
                    350
                    if self.world_var.get() == "object-manipulation"
                    else 60
                ),
            )
            self.controller.start(spec)
            self.timeline.delete(*self.timeline.get_children())
            self.events.delete(0, "end")
            self._last_event_keys.clear()
            self.last_tick_count = 0
            self.run_var.set(self.controller.launch_id or "Launching")
            self.path_var.set(str(self.controller.run_dir or ""))
            self.model_status_var.set("MODEL ↔ WORLD: initializing")
            self._refresh_buttons()
        except Exception as exc:
            messagebox.showerror(
                "Could not start Psychology run",
                str(exc),
                parent=self.root,
            )

    def stop(self):
        try:
            self.controller.stop()
        except Exception as exc:
            messagebox.showerror(
                "Could not stop Psychology run",
                str(exc),
                parent=self.root,
            )

    def _poll(self):
        self.controller.poll_telemetry()
        view = self.controller.view

        if len(view.ticks) != self.last_tick_count:
            new_ticks = view.ticks[self.last_tick_count :]
            for tick in new_ticks:
                self._append_tick(tick)
            self.last_tick_count = len(view.ticks)
            self._refresh_latest()
            self._draw_map()

        # The 4.18.1 runner intentionally avoids per-tick full telemetry during
        # long runs. Refresh its compact checkpoint artifact about once/second.
        if self.prospective_preset_var.get() in {"4.18.1 Prospective Space Development", "4.18.2 Dynamic Sustaining Ecology"}:
            self._development_poll_counter = (self._development_poll_counter + 1) % 13
            if self._development_poll_counter == 0:
                self._update_prospective_hub_panels(view.latest)

        state = self.controller.state
        self.status_var.set(state)
        token = {
            "RUNNING": "status.running",
            "COMPLETED": "status.completed",
            "FAILED": "status.failed",
            "STOPPING": "status.waiting",
        }.get(state, "status.info")
        self.status_label.configure(foreground=self.palette[token])

        if self.controller.error:
            self.status_var.set(f"{state} • {self.controller.error}")

        self._refresh_buttons()
        try:
            if self.root.winfo_exists():
                self.root.after(80, self._poll)
        except tk.TclError:
            pass

    def _refresh_buttons(self):
        active = self.controller.is_active
        legacy_ok = False
        if hasattr(self, "legacy_mode_enabled"):
            from .legacy_mode import legacy_start_run_available
            legacy_ok = legacy_start_run_available(
                enabled=bool(self.legacy_mode_enabled.get()),
                selected_preset=str(self.prospective_preset_var.get()),
            )
        else:
            legacy_ok = True
        start_state = "disabled" if active or not legacy_ok else "normal"
        self.start_button.configure(state=start_state)
        self.stop_button.configure(state="normal" if active else "disabled")
        # Mode checkbox: disable while historical run active
        if hasattr(self, "legacy_mode_check"):
            try:
                self.legacy_mode_check.configure(
                    state="disabled" if active else "normal"
                )
            except Exception:
                pass

    # ---------- projection to UI ----------

    def _append_tick(self, tick: PsychologyTickView):
        body = tick.body_truth
        signals = tick.accessible_signals
        pos = tick.objective_position

        self.timeline.insert(
            "",
            "end",
            values=(
                self._life_day(tick),
                self._pos(pos),
                self._fmt(body.get("mass_kg"), 2),
                tick.action,
                self._triple(
                    body.get("energy_reserve"),
                    body.get("hydration"),
                    body.get("fatigue"),
                ),
                self._triple(
                    signals.get("energy_signal"),
                    signals.get("hydration_signal"),
                    signals.get("fatigue_signal"),
                ),
                self._fmt(tick.prediction_error_magnitude),
                self._fmt(tick.selected_uncertainty),
                self._fmt(tick.selected_value),
                tick.selection_reason or "—",
            ),
        )
        children = self.timeline.get_children()
        if children:
            self.timeline.see(children[-1])

        for memory_event in tick.memory_events:
            event_type = str(memory_event.get("type") or "MEMORY_EVENT")
            key = json.dumps(memory_event, sort_keys=True, default=str)
            if key in self._last_event_keys:
                continue
            self._last_event_keys.add(key)
            details = []
            if memory_event.get("pattern_id") is not None:
                details.append(str(memory_event["pattern_id"]))
            if memory_event.get("prediction_error") is not None:
                details.append(
                    "PE=" + self._fmt(memory_event["prediction_error"])
                )
            self._event(
                f"t={tick.tick:04d} {event_type.upper()}"
                + (" • " + " • ".join(details) if details else "")
            )

        receipt = tick.world_action_receipt
        for update in receipt.get("environmental_object_updates", []):
            if not isinstance(update, dict):
                continue
            if self.map_renderer.selected != (
                "object",
                str(update.get("object_id")),
            ):
                continue
            before = update.get("before", {})
            after = update.get("after", {})
            if isinstance(before, dict) and isinstance(after, dict):
                self._event(
                    f"day={self._life_day(tick):04d} "
                    f"{update.get('object_id', '?')} REGENERATED "
                    f"q={self._fmt(before.get('quantity'))}→"
                    f"{self._fmt(after.get('quantity'))}"
                )

        if tick.action.startswith("USE:"):
            before = receipt.get("object_state_before")
            after = receipt.get("object_state_after")
            if isinstance(before, dict) and isinstance(after, dict) and before != after:
                object_id = receipt.get("object_id") or tick.action.split(":", 1)[1]
                self._event(
                    f"day={self._life_day(tick):04d} {object_id} STATE "
                    f"q={self._fmt(before.get('quantity'))}→"
                    f"{self._fmt(after.get('quantity'))} • "
                    f"d={self._fmt(before.get('durability'))}→"
                    f"{self._fmt(after.get('durability'))}"
                )
            if receipt.get("effect_available") is False:
                self._event(
                    f"day={self._life_day(tick):04d} "
                    f"{receipt.get('object_id', '?')} EFFECT UNAVAILABLE"
                )

        if tick.action.startswith(("TAKE:", "RELEASE:", "PUSH:")):
            valid = bool(receipt.get("valid"))
            object_id = receipt.get("object_id") or tick.action.split(":", 2)[1]
            if valid:
                state = (
                    "CARRIED" if tick.action.startswith("TAKE:")
                    else "DROPPED" if tick.action.startswith("RELEASE:")
                    else "PUSHED"
                )
                destination = (
                    receipt.get("object_position_after")
                    or receipt.get("position_after")
                )
                self._event(
                    f"day={self._life_day(tick):04d} {object_id} "
                    f"{state} → {self._pos(destination)}"
                )
            else:
                self._event(
                    f"day={self._life_day(tick):04d} {object_id} "
                    f"REJECTED • {receipt.get('rejection_reason', 'UNAVAILABLE')}"
                )

        for receipt in tick.exogenous_event_receipts:
            key = json.dumps(receipt, sort_keys=True, default=str)
            if key not in self._last_event_keys:
                self._last_event_keys.add(key)
                self._event(
                    f"t={tick.tick:04d} EXOGENOUS "
                    f"{receipt.get('kind', 'EVENT')}  [OBSERVER ONLY]"
                )

        for receipt in tick.delayed_effect_receipts:
            key = json.dumps(receipt, sort_keys=True, default=str)
            if key not in self._last_event_keys:
                self._last_event_keys.add(key)
                self._event(
                    f"t={tick.tick:04d} DELAYED EFFECT from "
                    f"{receipt.get('source_action', '?')}  [OBSERVER ONLY]"
                )

        if tick.world_action_receipt.get("obstacle_contact"):
            obstacle_id = tick.world_action_receipt.get(
                "obstacle_id",
                "?",
            )
            key = f"{tick.tick}:OBSTACLE:{obstacle_id}"
            if key not in self._last_event_keys:
                self._last_event_keys.add(key)
                applied = tick.world_action_receipt.get(
                    "obstacle_effect_applied"
                )
                suffix = "EFFECT" if applied else "NO EFFECT"
                self._event(
                    f"day={self._life_day(tick):04d} OBSTACLE CONTACT "
                    f"{obstacle_id} • {suffix}  [OBSERVER TRUTH]"
                )

        for divergence in tick.model_world_divergences:
            key = f"{tick.tick}:{divergence}"
            if key not in self._last_event_keys:
                self._last_event_keys.add(key)
                self._event(
                    f"t={tick.tick:04d} MODEL≠WORLD "
                    f"{divergence.get('entity_kind', 'OBJECT')} "
                    f"{divergence.get('object_id')} "
                    f"{self._pos(divergence.get('memory_position'))}"
                    f" → {self._pos(divergence.get('world_position'))}"
                )

    def _event(self, text):
        self.events.insert("end", text)
        if self.events.size() > 120:
            self.events.delete(0)
        self.events.see("end")

    def _refresh_latest(self):
        tick = self.controller.view.latest
        available = list(self.controller.projector.available_agent_ids)
        if available and hasattr(self, "agent_combo"):
            self.agent_combo.configure(values=tuple(available))
            if self.agent_var.get() not in available:
                self.agent_var.set(available[0])
                self.controller.projector.selected_agent_id = available[0]
        if tick is None:
            return

        self.run_var.set(
            self.controller.view.source_run_id
            or self.controller.launch_id
            or "Running"
        )

        divergence_count = len(tick.model_world_divergences)
        if divergence_count:
            self.model_status_var.set(
                f"MODEL ≠ WORLD: {divergence_count} divergence"
                f"{'s' if divergence_count != 1 else ''}"
            )
            self.model_status_label.configure(
                foreground=self.palette["status.failed"]
            )
        else:
            if tick.memory_mode != "LEGACY_PSYCHE_V03":
                self.model_status_var.set(
                    f"BOUNDED {tick.memory_mode}: "
                    f"{tick.memory_pattern_count} patterns • "
                    f"{tick.memory_episode_count} episodes • "
                    f"{tick.retrieval.get('total_candidates_inspected', 0)} inspected"
                )
            else:
                self.model_status_var.set(
                    f"MODEL ↔ WORLD: aligned • "
                    f"{len(tick.known_objects)} objects + "
                    f"{len(tick.known_obstacles)} obstacles known"
                )
            self.model_status_label.configure(
                foreground=self.palette["status.running"]
            )

        self._update_cross_agent_trace_panel(tick)
        self._update_temporal_contingency_panel(tick)
        self._update_action_execution_attribution_panel(tick)
        self._update_predictive_utilization_panel(tick)
        self._update_action_economics_panel(tick)
        self._update_natural_physiological_window_panel(tick)
        self._update_developmental_physiology_panel(tick)
        self._update_ordinary_action_economy_panel(tick)
        self._update_prospective_temporal_economy_panel(tick)
        self._update_bounded_prospective_trajectory_panel(tick)
        self._update_prospective_trajectory_calibration_panel(tick)
        self._update_prospective_self_state_panel(tick)
        self._update_composed_prospective_trajectories_panel(tick)
        self._update_prospective_hub_panels(tick)
        self._update_ecological_stabilization_panel(tick)
        self._update_env_regulation_probe_panel(tick)
        self._update_env_causal_frontier_panel(tick)
        self._update_world_organism_exchange_panel(tick)
        self._update_physical_intake_panel(tick)

        # World truth
        self._set(self.world_values, "position", self._pos(tick.objective_position))
        self._set(self.world_values, "progress", self._fmt(tick.progress))
        self._set(
            self.world_values,
            "objective objects",
            str(len(tick.world_objects)),
        )
        self._set(
            self.world_values,
            "objective obstacles",
            str(len(tick.world_obstacles)),
        )
        self._set(
            self.world_values,
            "obstacle contacts",
            str(
                sum(
                    1
                    for row in self.controller.view.ticks
                    if row.world_action_receipt.get(
                        "obstacle_contact"
                    )
                )
            ),
        )
        self._set(
            self.world_values,
            "random events",
            str(tick.random_event_count),
        )
        world_event = (
            tick.exogenous_event_receipts[-1].get("kind")
            if tick.exogenous_event_receipts
            else "—"
        )
        self._set(self.world_values, "current world event", world_event)

        # Body truth / biological time
        body = tick.body_truth
        self._set(
            self.body_values,
            "life day",
            str(self._life_day(tick)),
        )
        self._set(
            self.body_values,
            "age years",
            self._fmt(body.get("age_years"), 2),
        )
        self._set(
            self.body_values,
            "mass kg",
            self._fmt(body.get("mass_kg"), 2),
        )
        self._set(
            self.body_values,
            "mass status",
            self._mass_status(body),
        )
        self._set(
            self.body_values,
            "mass risk",
            self._mass_risk_text(body),
        )
        self._set(
            self.body_values,
            "mass delta/day",
            self._signed(body.get("last_mass_delta_kg"), 4),
        )
        self._set(
            self.body_values,
            "metabolic balance",
            self._signed(
                body.get("last_daily_metabolic_balance"),
                4,
            ),
        )
        self._set(
            self.body_values,
            "energy reserve",
            self._fmt(body.get("energy_reserve")),
        )
        self._set(self.body_values, "hydration", self._fmt(body.get("hydration")))
        self._set(self.body_values, "fatigue", self._fmt(body.get("fatigue")))
        self._set(self.body_values, "damage", self._fmt(body.get("damage")))
        self._set(
            self.body_values,
            "effort cost",
            self._fmt(body.get("last_effort_cost")),
        )

        # Accessible signals
        signals = tick.accessible_signals
        self._set(
            self.signal_values,
            "energy signal",
            self._fmt(signals.get("energy_signal")),
        )
        self._set(
            self.signal_values,
            "hydration signal",
            self._fmt(signals.get("hydration_signal")),
        )
        self._set(
            self.signal_values,
            "fatigue signal",
            self._fmt(signals.get("fatigue_signal")),
        )
        self._set(
            self.signal_values,
            "discomfort signal",
            self._fmt(signals.get("discomfort_signal")),
        )
        self._set(
            self.signal_values,
            "effort signal",
            self._fmt(signals.get("effort_signal")),
        )
        self._set(
            self.signal_values,
            "last experienced",
            self._compact(tick.last_experienced_effects, 52),
        )
        self._set(
            self.signal_values,
            "new effect → next tick",
            self._compact(tick.current_experienced_effects, 52),
        )

        # Psyche model
        self._set(
            self.model_values,
            "memory mode",
            tick.memory_mode,
        )
        self._set(
            self.model_values,
            "memory episodes",
            (
                f"{tick.memory_episode_count}/{tick.memory_capacity}"
                if tick.memory_capacity is not None
                else str(tick.memory_episode_count)
            ),
        )
        self._set(
            self.model_values,
            "memory patterns",
            str(tick.memory_pattern_count),
        )
        self._set(
            self.model_values,
            "novel fragments",
            str(tick.memory_novel_fragment_count),
        )
        retrieval = tick.retrieval
        self._set(
            self.model_values,
            "retrieval stage",
            str(retrieval.get("terminal_stage") or "—"),
        )
        self._set(
            self.model_values,
            "candidates P/X/E/T",
            "/".join(
                str(retrieval.get(key, "—"))
                for key in (
                    "pattern_candidates_inspected",
                    "exception_candidates_inspected",
                    "episode_candidates_inspected",
                    "total_candidates_inspected",
                )
            ),
        )
        self._set(
            self.model_values,
            "retrieval confidence",
            self._fmt(retrieval.get("selected_prediction_confidence")),
        )
        perceptual = tick.perceptual_dynamics
        self._set(self.model_values, "active modalities", ", ".join(perceptual.get("active_modalities", ())) or "—")
        self._set(self.model_values, "expectation", "UNKNOWN" if perceptual.get("unknown", True) else "SUPPORTED")
        self._set(self.model_values, "perceptual mismatch", self._fmt(perceptual.get("mismatch")))
        self._set(self.model_values, "perceptual activation", self._fmt(perceptual.get("perceptual_activation")))
        self._set(
            self.model_values,
            "retention",
            (
                f"{tick.retention.get('decision', '—')} / "
                f"{tick.retention.get('reason', '—')}"
                if tick.retention
                else "—"
            ),
        )
        self._set(
            self.model_values,
            "known positions",
            str(len(tick.known_positions)),
        )
        self._set(
            self.model_values,
            "known objects",
            str(len(tick.known_objects)),
        )
        self._set(
            self.model_values,
            "known obstacles",
            str(len(tick.known_obstacles)),
        )
        self._set(
            self.model_values,
            "action models",
            str(len(tick.learning_models)),
        )
        self._set(
            self.model_values,
            "object cue models",
            str(len(tick.object_cue_models)),
        )
        self._set(
            self.model_values,
            "obstacle cue models",
            str(len(tick.obstacle_cue_models)),
        )
        self._set(
            self.model_values,
            "physiology context",
            tick.physiology_context or "—",
        )
        self._set(
            self.model_values,
            "prediction source",
            (
                f"{tick.selected_prediction_source} / "
                f"{tick.selected_prediction_scope}"
            ),
        )
        self._set(
            self.model_values,
            "context samples",
            (
                str(tick.selected_context_sample_count)
                if tick.selected_context_sample_count is not None
                else "—"
            ),
        )
        self._set(
            self.model_values,
            "prediction error",
            self._fmt(tick.prediction_error_magnitude),
        )
        self._set(
            self.model_values,
            "selected prediction",
            self._compact(tick.selected_prediction, 50),
        )
        self._set(
            self.model_values,
            "selected uncertainty",
            self._fmt(tick.selected_uncertainty),
        )
        self._set(
            self.model_values,
            "selected value",
            self._fmt(tick.selected_value),
        )
        self._set(
            self.model_values,
            "selected habit",
            self._fmt(tick.selected_habit),
        )

        # Behavior
        self._set(self.behavior_values, "action", tick.action)
        self._set(
            self.behavior_values,
            "selection reason",
            tick.selection_reason or "—",
        )
        self._set(
            self.behavior_values,
            "selection score",
            self._fmt(tick.selection_score),
        )
        self._set(
            self.behavior_values,
            "action source",
            tick.action_source,
        )

        self.map_hint.configure(
            text=(
                f"WORLD {tick.width}×{tick.height} • "
                f"pos {self._pos(tick.objective_position)} • "
                f"{len(tick.world_objects)} objects • "
                f"{len(tick.known_objects)} known • "
                f"{len(tick.observation.get('visible_objects', []))} visible"
            )
        )
        self._refresh_inspector()

    def _set(self, mapping, key, value):
        mapping[key].configure(text=value)

    # ---------- map ----------

    def _draw_map(self):
        if not hasattr(self, "canvas"):
            return
        if self.view_mode_var.get() == "physical_world":
            display = self.planet_session.display
            self.planet_renderer.layer = self.planet_layer_var.get()
            self.planet_renderer.show_boundary_overlay = bool(
                self.planet_boundary_overlay_var.get()
            )
            self.planet_renderer.draw(self.canvas, display, self.palette)
            self._draw_current_agent_overlay(display)
            self._refresh_planet_panels()
            if display is not None:
                self.map_hint.configure(
                    text=(
                        f"PLANET {display.width}×{display.height} toroidal • "
                        f"tick {display.tick} • layer {self.planet_layer_var.get()} • "
                        f"boundary {'ON' if display.boundary.enabled else 'OFF'} • "
                        f"{self.planet_lifecycle_var.get()}"
                    )
                )
            else:
                self.map_hint.configure(
                    text="CURRENT MM • Apply setup, then Run — one physical system"
                )
            return
        tick = self.controller.view.latest
        trajectory = tuple(
            row.objective_position
            for row in self.controller.view.ticks[-256:]
            if row.objective_position is not None
        )
        self.map_renderer.draw(
            self.canvas,
            tick,
            self.palette,
            show_truth=self.truth_overlay_var.get(),
            show_memory=self.memory_overlay_var.get(),
            trajectory=trajectory,
            follow_agent=self.follow_agent_var.get(),
        )

    def _draw_current_agent_overlay(self, display) -> None:
        """High-contrast read-only BODY annotation, trail, and tick heartbeat."""
        try:
            self.canvas.delete("current_agent")
        except Exception:
            return
        runtime = self.current_runtime
        if display is None or runtime is None:
            return
        viewport = self.planet_renderer._viewport(self.canvas)
        position = (float(runtime.body.x), float(runtime.body.y))
        if not self._current_agent_trail or self._current_agent_trail[-1] != position:
            self._current_agent_trail.append(position)
            self._current_agent_trail = self._current_agent_trail[-96:]
        if len(self._current_agent_trail) > 1:
            points = []
            for x, y in self._current_agent_trail:
                sx, sy = self.planet_renderer.camera.world_to_screen(
                    (x, y), viewport=viewport,
                    world_size=(display.width, display.height),
                )
                points.extend((sx, sy))
            self.canvas.create_line(
                *points, fill="#ff2d55", width=3, dash=(5, 3),
                tags=("current_agent",),
            )
        cells = runtime.body.cells(
            display.width, display.height, runtime.config.body.footprint
        )
        inset = max(4.0, self.planet_renderer.camera.cell_px * 0.42)
        for y, x in cells:
            cx, cy = self.planet_renderer.camera.world_to_screen(
                (x, y), viewport=viewport, world_size=(display.width, display.height)
            )
            self.canvas.create_oval(
                cx - inset, cy - inset, cx + inset, cy + inset,
                fill="#ff2d55", outline="#ffffff", width=2,
                tags=("current_agent",),
            )
        cx, cy = self.planet_renderer.camera.world_to_screen(
            position, viewport=viewport, world_size=(display.width, display.height)
        )
        pulse = max(11.0, self.planet_renderer.camera.cell_px * (0.72 + 0.12 * (runtime.tick % 4)))
        self.canvas.create_oval(
            cx - pulse, cy - pulse, cx + pulse, cy + pulse,
            fill="", outline="#ff2d55", width=3,
            tags=("current_agent",),
        )
        self.canvas.create_text(
            cx, cy - pulse - 10, text="CURRENT AGENT",
            fill="#d0003b", font=("TkDefaultFont", 9, "bold"),
            tags=("current_agent",),
        )
        sync = runtime.tick == runtime.world.tick == runtime.body.tick == runtime.internal.tick
        self.canvas.create_rectangle(
            viewport[0] - 238, 10, viewport[0] - 10, 72,
            fill="#101b2d", outline="#ff2d55", width=2,
            tags=("current_agent",),
        )
        self.canvas.create_text(
            viewport[0] - 224, 20, anchor="nw",
            text=(f"TICK  {runtime.tick:,}\n"
                  f"● {'RUNNING' if self._planet_running else 'PAUSED'}   "
                  f"W/B/I {'SYNC' if sync else 'MISMATCH'}"),
            fill="#ffffff", font=("TkDefaultFont", 11, "bold"),
            tags=("current_agent",),
        )

    def _view_mode_changed(self, _event=None):
        mode = self.view_mode_var.get()
        self.mode_selector_var.set(
            "Current MM" if mode == "physical_world" else "Legacy Experiments"
        )
        if mode != "physical_world" and self._planet_running:
            self._planet_pause()
        # Re-scope legacy vs current chrome (no experiment auto-activation).
        if hasattr(self, "legacy_mode_enabled"):
            self._apply_legacy_mode_chrome()
        if mode == "physical_world":
            self.world_badge_var.set("CURRENT MM")
            self.model_status_var.set("PhysicalSystemRuntime • WORLD + BODY + INTERNAL")
            if self.planet_session.display is None:
                apply_current_setup(self.planet_session, self._current_physical_world_setup())
        else:
            self.world_badge_var.set("LEGACY EXPERIMENTS")
            if bool(self.legacy_mode_enabled.get()):
                self.model_status_var.set("LEGACY EXPERIMENT WORKSPACE • historical Start Run")
            else:
                self.model_status_var.set(
                    "HISTORICAL WORKSPACE • Current MM remains preserved"
                )
        self._apply_view_chrome()
        self._draw_map()

    def _planet_layer_changed(self):
        # Display-only: must not advance simulation.
        self._draw_map()


    def _bootstrap_current_physical_world(self) -> None:
        """Default CURRENT PHYSICAL WORLD: apply setup once so workspace is READY (no auto-run)."""
        if str(self.view_mode_var.get()) != "physical_world":
            return
        self.world_badge_var.set("CURRENT MM")
        self.model_status_var.set("PhysicalSystemRuntime • WORLD + BODY + INTERNAL")
        if self.planet_session.display is not None:
            self.planet_lifecycle_var.set(
                "RUNNING" if self._planet_running else (
                    "PAUSED" if self.planet_session.display.tick else "READY"
                )
            )
            self._apply_view_chrome()
            self._draw_map()
            return
        try:
            self._apply_current_planet_setup()
        except Exception:
            self.planet_lifecycle_var.set("UNCONFIGURED")

    def _sync_fixture_id_from_display(self) -> None:
        raw = str(self.planet_fixture_var_display.get())
        fid = raw.split(" — ", 1)[0].strip()
        if fid in FIXTURE_IDS:
            self.planet_boundary_fixture_var.set(fid)

    def _current_physical_world_setup(self) -> CurrentPhysicalWorldSetup:
        self._sync_fixture_id_from_display()
        return CurrentPhysicalWorldSetup(
            seed=int(self.planet_seed_var.get()),
            boundary_fixture_id=str(self.planet_boundary_fixture_var.get()),
        )

    def _apply_current_planet_setup(self) -> None:
        """Setup-time apply: pause run, reset seed, apply boundary fixture catalog."""
        self.view_mode_var.set("physical_world")
        self._planet_pause()
        setup = self._current_physical_world_setup()
        apply_current_setup(self.planet_session, setup)
        self._current_agent_trail = []
        self.planet_renderer.selected_cell = None
        self.planet_renderer.invalidate_cache(getattr(self, "canvas", None))
        d = self.planet_session.display
        tick = d.tick if d is not None else 0
        on = bool(d and d.boundary.enabled)
        self.planet_run_status_var.set(
            f"Current MM: setup applied @ tick {tick} • boundary {'ON' if on else 'OFF'}"
        )
        self.planet_lifecycle_var.set("READY")
        self._apply_view_chrome()
        self._draw_map()

    def _ensure_planet_session(self) -> None:
        if self.planet_session.display is None:
            apply_current_setup(self.planet_session, self._current_physical_world_setup())

    def _planet_reset(self):
        self.view_mode_var.set("physical_world")
        saved = self._planet_stop(stop_reason="reset")
        apply_current_setup(self.planet_session, self._current_physical_world_setup())
        self._current_agent_trail = []
        self.planet_renderer.selected_cell = None
        self.planet_renderer.invalidate_cache(getattr(self, "canvas", None))
        if saved is None:
            self.planet_run_status_var.set("Current MM: paused @ tick 0")
        else:
            self.planet_run_status_var.set(f"Saved {saved.name} • reset @ tick 0")
        self.planet_lifecycle_var.set("READY")
        self._apply_view_chrome()
        self._draw_map()

    def _planet_step(self):
        self.view_mode_var.set("physical_world")
        if self._planet_running:
            self._planet_pause()
        self._ensure_planet_session()
        self.planet_session.step(1)
        d = self.planet_session.display
        self.planet_run_status_var.set(
            f"Current MM: paused @ tick {d.tick if d else 0}"
        )
        self.planet_lifecycle_var.set(f"PAUSED • tick {d.tick if d else 0}")
        self._apply_view_chrome()
        self._draw_map()

    def _planet_run(self):
        self.view_mode_var.set("physical_world")
        self._apply_view_chrome()
        self._ensure_planet_session()
        if self._planet_running:
            return
        self._planet_run_error = None
        self._planet_running = True
        self.planet_run_status_var.set("Current MM: running")
        self.planet_lifecycle_var.set("RUNNING")
        self._planet_last_render = 0.0
        self._schedule_planet_batch()

    def _planet_pause(self):
        self._planet_running = False
        aid = self._planet_after_id
        self._planet_after_id = None
        if aid is not None:
            try:
                self.root.after_cancel(aid)
            except Exception:
                pass
        d = self.planet_session.display
        tick = d.tick if d is not None else 0
        err = self._planet_run_error
        if err:
            self.planet_run_status_var.set(f"Current MM: error @ tick {tick} • {err}")
        else:
            self.planet_run_status_var.set(f"Current MM: paused @ tick {tick}")
            self.planet_lifecycle_var.set(f"PAUSED • tick {tick}" if tick else "READY • tick 0")

    def _planet_stop(self, *, stop_reason: str = "stop"):
        """Stop the current run and persist it without resetting the display."""
        self._planet_pause()
        display = self.planet_session.display
        if display is None or display.tick <= 0:
            return None
        key = (id(self.planet_session.runtime), int(display.tick))
        if key == self._planet_last_saved_key:
            return self._planet_last_saved_dir
        try:
            saved = self.planet_session.save_run(
                self.controller.results_root,
                stop_reason=stop_reason,
                boundary_fixture_id=str(self.planet_boundary_fixture_var.get()),
            )
        except Exception as exc:
            self.planet_run_status_var.set(
                f"Current MM: stopped @ tick {display.tick} • save failed: {exc}"
            )
            self.planet_lifecycle_var.set(f"STOPPED • SAVE FAILED • tick {display.tick}")
            messagebox.showerror(
                "Could not save Current Physical World run", str(exc), parent=self.root
            )
            return None
        self._planet_last_saved_key = key
        self._planet_last_saved_dir = saved
        if saved is not None:
            self.path_var.set(str(saved))
            self.planet_run_status_var.set(
                f"Current MM: stopped + saved @ tick {display.tick}"
            )
            self.planet_lifecycle_var.set(f"STOPPED • SAVED • tick {display.tick}")
        return saved

    def _schedule_planet_batch(self):
        if not self._planet_running:
            return
        # single pending callback only (no queue)
        if self._planet_after_id is not None:
            try:
                self.root.after_cancel(self._planet_after_id)
            except Exception:
                pass
        self._planet_after_id = self.root.after(1, self._planet_tick_batch)

    def _planet_tick_batch(self):
        self._planet_after_id = None
        if not self._planet_running:
            return
        if self.view_mode_var.get() != "physical_world":
            self._planet_pause()
            return
        try:
            t0 = time.perf_counter()
            n = 0
            while (
                n < self._planet_batch_max_ticks
                and (time.perf_counter() - t0) * 1000.0 < self._planet_batch_wall_ms
            ):
                self.planet_session.step(1)
                n += 1
        except Exception as exc:
            self._planet_run_error = str(exc)
            self._planet_pause()
            self._draw_map()
            return
        now = time.perf_counter()
        if now - self._planet_last_render >= self._planet_render_interval_s:
            self._planet_last_render = now
            d = self.planet_session.display
            self.planet_run_status_var.set(
                f"Current MM: running @ tick {d.tick if d else 0}"
            )
            self.planet_lifecycle_var.set(f"RUNNING • tick {d.tick if d else 0}")
            self._draw_map()
        if self._planet_running:
            self._schedule_planet_batch()


    def _register_view_chrome(self):
        """Bind existing widgets into view-specific groups (no deletion)."""
        self._planet_map_controls = [
            w for w in (
                getattr(self, "planet_run_button", None),
                getattr(self, "planet_pause_button", None),
                getattr(self, "planet_stop_button", None),
                getattr(self, "planet_step_button", None),
                getattr(self, "planet_reset_button", None),
                getattr(self, "planet_layer_combo", None),
                getattr(self, "planet_boundary_check", None),
            ) if w is not None
        ]
        self._organism_map_controls = [
            w for w in (
                getattr(self, "truth_check", None) if hasattr(self, "truth_check") else None,
            ) if w is not None
        ]
        # Right panels: planet vs organism by known attributes
        self._planet_right_sections = [
            w for w in (
                getattr(self, "planet_status_panel", None),
                getattr(self, "planet_boundary_panel", None),
                getattr(self, "planet_analyzer_panel", None),
            ) if w is not None
        ]
        # parents of planet panels are cards — hide card frames if we stored them
        self._planet_right_headers = []
        self._organism_right_sections = [
            w for w in (
                getattr(self, "physical_intake_panel", None),
            ) if w is not None
        ]
        self._organism_right_headers = []
        # Prefer packing parent cards
        def parents(widgets):
            out = []
            for w in widgets:
                try:
                    out.append(w.master)
                except Exception:
                    pass
            return out
        self._planet_right_sections = parents(self._planet_right_sections) or self._planet_right_sections
        self._organism_right_sections = parents(self._organism_right_sections) or self._organism_right_sections
        # Also hide ontology-ish text panels if present
        for attr in (
            "world_truth_panel",
            "body_truth_panel",
            "signals_panel",
            "psyche_panel",
            "behavior_panel",
            "scientific_boundary_panel",
            "inspector",
        ):
            w = getattr(self, attr, None)
            if w is None:
                continue
            try:
                parent = w.master
            except Exception:
                parent = w
            if attr == "inspector":
                # keep inspector in both views (cell vs agent)
                continue
            if parent not in self._organism_right_sections:
                self._organism_right_sections.append(parent)
        self._apply_view_chrome()

    def _apply_view_chrome(self):
        """Show instruments relevant to current view; preserve widgets (no delete)."""
        pw = self.view_mode_var.get() == "physical_world"
        # Agent selector: hide in physical_world
        if hasattr(self, "agent_combo"):
            if pw:
                self.agent_combo.pack_forget()
                if hasattr(self, "_agent_label"):
                    self._agent_label.pack_forget()
            else:
                if hasattr(self, "_agent_label"):
                    self._agent_label.pack(side="right")
                self.agent_combo.pack(side="right", padx=(4, 10), pady=12)
        # Left panel: Current setup in physical_world; Legacy experiments otherwise.
        # Keep left visible in both views (CONFIG-1); do not delete legacy widgets.
        if hasattr(self, "left"):
            try:
                panes = self.body_splitter.panes()
                if str(self.left) not in map(str, panes):
                    self.body_splitter.add(
                        self.left,
                        width=self.LEFT_PANEL_INITIAL_WIDTH,
                        minsize=self.LEFT_PANEL_MIN_WIDTH,
                        stretch="never",
                    )
            except Exception:
                pass
            # Left workspace remount is owned by _remount_left_workspace
            # (via _apply_legacy_mode_chrome at end). Do not pack(before=forgotten).
        # Timeline
        if hasattr(self, "timeline_card") and hasattr(self, "center_splitter"):
            if pw:
                if self.timeline_visible:
                    try:
                        self.center_splitter.forget(self.timeline_card)
                    except Exception:
                        pass
                    self._timeline_hidden_by_view = True
            else:
                if getattr(self, "_timeline_hidden_by_view", False):
                    try:
                        self.center_splitter.add(
                            self.timeline_card,
                            height=self._timeline_height,
                            minsize=90,
                            stretch="never",
                        )
                    except Exception:
                        pass
                    self.timeline_visible = True
                    self._timeline_hidden_by_view = False
        # Right organism panels vs planet panels
        for name in (
            "ontology_frame",
            "physical_intake_frame",
            "selection_inspector_frame",
        ):
            pass
        # Use stored organism section widgets
        for w in getattr(self, "_organism_right_sections", []):
            try:
                if pw:
                    w.pack_forget()
                else:
                    w.pack(fill="x", padx=12, pady=(0, 8))
            except Exception:
                pass
        for w in getattr(self, "_organism_right_headers", []):
            try:
                if pw:
                    w.pack_forget()
                else:
                    w.pack(fill="x", padx=12, pady=(8, 2))
            except Exception:
                pass
        for w in getattr(self, "_planet_right_sections", []):
            try:
                if pw:
                    w.pack(fill="x", padx=12, pady=(0, 8))
                else:
                    w.pack_forget()
            except Exception:
                pass
        for w in getattr(self, "_planet_right_headers", []):
            try:
                if pw:
                    w.pack(fill="x", padx=12, pady=(8, 2))
                else:
                    w.pack_forget()
            except Exception:
                pass
        # Map control visibility
        for w in getattr(self, "_planet_map_controls", []):
            try:
                if pw:
                    if str(w.winfo_manager()) == "":
                        w.pack(side="right", padx=3, pady=4)
                else:
                    w.pack_forget()
            except Exception:
                pass
        for w in getattr(self, "_organism_map_controls", []):
            try:
                if not pw:
                    if str(w.winfo_manager()) == "":
                        w.pack(side="right", padx=(4, 0))
                else:
                    w.pack_forget()
            except Exception:
                pass
        self._update_footer_for_view()
        if hasattr(self, "legacy_mode_enabled") and hasattr(self, "legacy_mode_gate_frame"):
            self._apply_legacy_mode_chrome()

    def _update_footer_for_view(self):
        label = getattr(self, "footer_label", None)
        if label is None:
            return
        if self.view_mode_var.get() == "physical_world":
            label.configure(
                text="Mechanistic Mind Observer 0.4.0 • CURRENT MM • one WORLD + one embodied agent"
            )
        else:
            if bool(self.legacy_mode_enabled.get()):
                foot = "LEGACY ORGANISM EXPERIMENTS"
            else:
                foot = "LEGACY EXPERIMENTS • disabled • Current MM preserved"
            label.configure(text="Mechanistic Mind v0.4.0 • " + foot)

    def _refresh_planet_panels(self):
        display = self.planet_session.display
        if display is None or not hasattr(self, "planet_status_panel"):
            return
        from .planet_analyzer import analyze_physical_world
        from .planet_model import format_boundary_panel, format_world_status
        status = format_world_status(display)
        runtime = self.current_runtime
        cognition_text = "Current MM cognition unavailable."
        if runtime is not None:
            body = runtime.body
            internal = runtime.internal
            status += (
                "\n\nCURRENT AGENT (RAW PHYSICAL FACTS)\n"
                f"canonical_tick={runtime.tick} · synchronized="
                f"{runtime.tick == runtime.world.tick == body.tick == internal.tick}\n"
                f"BODY position=({body.x:.3f}, {body.y:.3f}) "
                f"velocity=({body.vx:.4f}, {body.vy:.4f}) T={body.T:.6f}\n"
                f"BODY B={body.B.astype(float).tolist()} "
                f"B_core={body.B_core.astype(float).tolist()} mech={body.mech:.6f}\n"
                f"INTERNAL shape={tuple(internal.c.shape)} "
                f"sum={float(internal.c.sum()):.9f} "
                f"norm={float(np.linalg.norm(internal.c)):.9f}"
            )
            try:
                views = runtime.observation_views()
                cog = runtime.cognitive_view()
                obs = views.get("agent_observation") or {}
                truth = views.get("world_truth") or {}
                act = cog.get("action") or {}
                mem = cog.get("memory") or {}
                pred = cog.get("predictive_organization") or {}
                prosp = cog.get("prospection") or {}
                inst = cog.get("instrumental_observation") or {}
                trace = cog.get("causal_trace") or {}
                bridges = cog.get("bridges") or {}
                cognition_text = (
                    "OBSERVATION BOUNDARY\n"
                    f"world_truth.T_mean={truth.get('T_mean')}  "
                    f"agent_keys={len(obs)}  "
                    f"cognition_receives=AGENT_OBSERVATION_ONLY\n"
                    f"agent_obs_sample={{{', '.join(f'{k}={obs[k]:.4f}' for k in list(obs)[:6])}}}\n\n"
                    "MEMORY (4.21)\n"
                    f"{mem}\n\n"
                    "PREDICTION (4.22)\n"
                    f"local/broader snapshot keys={list(pred)[:12]}\n\n"
                    "PROSPECTION (4.23)\n"
                    f"current={prosp.get('current')}\n\n"
                    "INSTRUMENTAL (4.25)\n"
                    f"physical_emit_path={inst.get('physical_emit_path')}  "
                    f"prediction={inst.get('current_prediction')}\n\n"
                    "ACTION\n"
                    f"selected={act.get('selected')} source={act.get('source')}  "
                    f"apply={act.get('last_apply')}\n"
                    f"candidates={act.get('candidates')}\n\n"
                    "BRIDGES\n"
                    f"{bridges}\n\n"
                    "CAUSAL TRACE\n"
                    f"events={len(trace.get('events') or [])} edges={len(trace.get('edges') or [])}\n"
                    f"tail_events={(trace.get('events') or [])[-4:]}\n"
                )
            except Exception as exc:  # noqa: BLE001 — UI must not crash on panel fill
                cognition_text = f"cognition panel error: {exc}"
        boundary = format_boundary_panel(display)
        report = analyze_physical_world(
            display,
            history=self.planet_session.history.as_list(),
        )
        pairs = [
            (self.planet_status_panel, status),
            (self.planet_boundary_panel, boundary),
        ]
        if hasattr(self, "planet_cognition_panel"):
            pairs.append((self.planet_cognition_panel, cognition_text))
        if hasattr(self, "planet_analyzer_panel"):
            pairs.append((self.planet_analyzer_panel, report.summary_text))
        for widget, content in pairs:
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", content)
            widget.configure(state="disabled")
        # cell inspector when selected
        if self.planet_renderer.selected_cell is not None and hasattr(self, "inspector"):
            y, x = self.planet_renderer.selected_cell
            self._set_inspector_text(format_cell_inspector_text(display, y, x))

    def observer_mm_obs1_read_only_contract(self) -> dict:
        """Programmatic audit: no live boundary edit controls introduced."""
        return {
            "forbidden_controls": list(assert_read_only_surface()),
            "has_live_K_slider": False,
            "has_live_mask_paint": False,
            "has_live_M_ext_slider": False,
            "view_modes": ("organism", "physical_world"),
            "user_modes": ("Current MM", "Legacy Experiments"),
            "field_layers": list(FIELD_LAYERS),
            "canonical_current_runtime": "PhysicalSystemRuntime",
            "no_canonical_current_organism_runtime": False,
            "current_agent": "runtime.body + runtime.internal",
            "organism_view_is_legacy": True,
            "current_launch_depends_on_legacy_mode": False,
        }

    def _map_fit(self):
        if self.view_mode_var.get() == "physical_world":
            display = self.planet_session.display
            if display is not None:
                self.planet_renderer.fit(self.canvas, display)
                self._draw_map()
            return
        tick = self.controller.view.latest
        if tick is not None:
            self.map_renderer.fit(self.canvas, tick)
            self._draw_map()

    def _map_zoom(self, factor, event=None):
        if self.view_mode_var.get() == "physical_world":
            display = self.planet_session.display
            if display is None:
                return
            viewport = self.planet_renderer._viewport(self.canvas)
            anchor = (
                (float(event.x), float(event.y))
                if event is not None and hasattr(event, "x")
                else (viewport[0] / 2, viewport[1] / 2)
            )
            self.planet_renderer.camera.change_zoom(
                factor,
                anchor=anchor,
                viewport=viewport,
                world_size=(display.width, display.height),
            )
            self._draw_map()
            return
        tick = self.controller.view.latest
        if tick is None:
            return
        viewport = self.map_renderer._viewport(self.canvas)
        anchor = (
            (float(event.x), float(event.y))
            if event is not None and hasattr(event, "x")
            else (viewport[0] / 2, viewport[1] / 2)
        )
        self.follow_agent_var.set(False)
        self.map_renderer.camera.change_zoom(
            factor,
            anchor=anchor,
            viewport=viewport,
            world_size=(tick.width, tick.height),
        )
        self._draw_map()

    def _map_wheel(self, event):
        self._map_zoom(1.12 if event.delta > 0 else 0.89, event)

    def _map_press(self, event):
        self._map_drag_origin = (event.x, event.y)
        self._map_dragged = False

    def _map_drag(self, event):
        if self._map_drag_origin is None:
            return
        old_x, old_y = self._map_drag_origin
        dx, dy = event.x - old_x, event.y - old_y
        if abs(dx) + abs(dy) > 1:
            self._map_dragged = True
        if self.view_mode_var.get() == "physical_world":
            self.planet_renderer.camera.pan_x += dx
            self.planet_renderer.camera.pan_y += dy
        else:
            self.map_renderer.camera.pan_x += dx
            self.map_renderer.camera.pan_y += dy
        self._map_drag_origin = (event.x, event.y)
        self.follow_agent_var.set(False)
        self._draw_map()

    def _map_release(self, event):
        if not self._map_dragged:
            if self.view_mode_var.get() == "physical_world":
                display = self.planet_session.display
                if display is not None:
                    viewport = self.planet_renderer._viewport(self.canvas)
                    self.planet_renderer.selected_cell = self.planet_renderer.screen_to_cell(
                        (float(event.x), float(event.y)),
                        viewport=viewport,
                        display=display,
                    )
                    self._refresh_planet_panels()
                    self._draw_map()
            else:
                selected = self.map_renderer.hit_test(event.x, event.y)
                self.map_renderer.selected = selected
                self._refresh_inspector()
                self._draw_map()
        self._map_drag_origin = None

    def _refresh_inspector(self):
        if not hasattr(self, "inspector"):
            return
        tick = self.controller.view.latest
        selected = self.map_renderer.selected
        if tick is None or selected is None:
            return
        snapshot = selection_snapshot(tick, selected[0], selected[1])
        lines = [
            f"{snapshot['entity']['kind']}  {snapshot['entity']['id']}",
        ]
        for label, key in (
            ("OBJECTIVE", "objective"),
            ("PERCEIVED", "perceived"),
            ("LEARNED", "learned"),
        ):
            value = snapshot[key]
            lines.extend(
                [
                    "",
                    label,
                    (
                        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
                        if value is not None
                        else "UNAVAILABLE / NOT CURRENTLY REPRESENTED"
                    ),
                ]
            )
        self._set_inspector_text("\n".join(lines))

    def _set_inspector_text(self, text):
        self.inspector.configure(state="normal")
        self.inspector.delete("1.0", "end")
        self.inspector.insert("1.0", text)
        self.inspector.configure(state="disabled")

    # ---------- formatting ----------

    @staticmethod
    def _position(value):
        if (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and all(isinstance(item, int) for item in value)
        ):
            return int(value[0]), int(value[1])
        return None

    @staticmethod
    def _pos(value):
        if value is None:
            return "—"
        try:
            return f"({int(value[0])},{int(value[1])})"
        except Exception:
            return "—"

    @staticmethod
    def _fmt(value, digits=3):
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.{digits}f}".rstrip("0").rstrip(".")
        return str(value)

    def _triple(self, a, b, c):
        return f"{self._fmt(a)}/{self._fmt(b)}/{self._fmt(c)}"

    @staticmethod
    def _compact(value, limit=60):
        if value is None:
            return "—"
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return text if len(text) <= limit else text[: limit - 1] + "…"


    @staticmethod
    def _life_day(tick: PsychologyTickView) -> int:
        value = tick.body_truth.get("life_day")
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(tick.tick) + 1

    @staticmethod
    def _signed(value, digits=3):
        if value is None:
            return "—"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{number:+.{digits}f}"

    @staticmethod
    def _mass_status(body):
        try:
            mass = float(body.get("mass_kg"))
        except (TypeError, ValueError):
            return "—"
        if mass < 45.0:
            return "LOW-MASS RISK"
        if mass > 120.0:
            return "HIGH-MASS RISK"
        return "OPERATING RANGE"

    @staticmethod
    def _mass_risk_text(body):
        low = body.get("low_mass_risk")
        high = body.get("high_mass_risk")
        total = body.get("physiological_mass_risk")
        try:
            low_f = float(low)
            high_f = float(high)
            total_f = float(total)
        except (TypeError, ValueError):
            return "—"
        if total_f <= 0.0:
            return "0"
        if low_f >= high_f:
            return f"LOW {low_f:.3f}"
        return f"HIGH {high_f:.3f}"

    # ---------- theme ----------

    def _agent_changed(self, _event=None):
        """Update 4.7 thin psyche selector — reprojects telemetry for one agent."""
        agent_id = str(self.agent_var.get() or "A001")
        self.controller.projector.selected_agent_id = agent_id
        # Rebuild projected ticks from JSONL with the new psyche focus.
        if self.controller.psychology_jsonl and self.controller.psychology_jsonl.exists():
            self.controller.projector.view.ticks.clear()
            self.controller._offset = 0
            self.controller.poll_telemetry()
            self._refresh_latest()

    def _theme_changed(self, _event=None):
        self.theme_mode = ThemeMode(self.theme_var.get())
        self.scheme = resolve_scheme(
            self.theme_mode,
            system_scheme=detect_system_scheme(),
            last_resolved=self.scheme,
        )
        self.palette = palette_for(self.scheme)
        self._apply_theme()

    def _apply_theme(self):
        p = self.palette
        self.root.configure(background=p["surface.app"])

        self.style.configure(
            "TCombobox",
            fieldbackground=p["surface.control"],
            background=p["surface.control"],
            foreground=p["text.primary"],
            arrowcolor=p["text.primary"],
            bordercolor=p["border.default"],
            lightcolor=p["border.default"],
            darkcolor=p["border.default"],
        )
        self.style.configure(
            "TEntry",
            fieldbackground=p["surface.control"],
            foreground=p["text.primary"],
            bordercolor=p["border.default"],
        )
        self.style.configure(
            "Treeview",
            background=p["surface.card"],
            fieldbackground=p["surface.card"],
            foreground=p["text.primary"],
            rowheight=24,
            bordercolor=p["border.default"],
        )
        self.style.configure(
            "Treeview.Heading",
            background=p["surface.elevated"],
            foreground=p["text.secondary"],
            bordercolor=p["border.default"],
        )
        self.style.map(
            "Treeview",
            background=[("selected", p["surface.selected"])],
            foreground=[("selected", p["text.primary"])],
        )

        for widget, options in tuple(self._semantic):
            try:
                if not widget.winfo_exists():
                    continue
            except tk.TclError:
                continue
            widget.configure(
                **{
                    key: p[token]
                    for key, token in options.items()
                }
            )

        self._draw_map()

    def close(self):
        try:
            self._planet_stop(stop_reason="window_close")
        except Exception:
            pass
        if self.controller.is_active:
            if not messagebox.askyesno(
                "Simulation run is active",
                "Stop the active run and close?",
                parent=self.root,
            ):
                return
            try:
                self.controller.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass
