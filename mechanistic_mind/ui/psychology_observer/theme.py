"""Semantic, toolkit-independent themes for Psychology Observer."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from types import MappingProxyType
from typing import Mapping


class ThemeMode(str, Enum):
    SYSTEM = "system"
    DARK = "dark"
    LIGHT = "light"


class ColorScheme(str, Enum):
    DARK = "dark"
    LIGHT = "light"


REQUIRED_TOKENS = (
    "surface.app",
    "surface.navigation",
    "surface.canvas",
    "surface.card",
    "surface.elevated",
    "border.default",
    "text.primary",
    "text.secondary",
    "text.muted",
    "action.primary",
    "action.primary_hover",
    "focus.ring",
    "status.running",
    "status.waiting",
    "status.stale",
    "status.failed",
    "status.info",
    "chart.1",
    "chart.2",
    "chart.3",
    "chart.4",
    "chart.5",
)


@dataclass(frozen=True, slots=True)
class ThemePalette:
    scheme: ColorScheme
    colors: Mapping[str, str]

    def __post_init__(self) -> None:
        missing = set(REQUIRED_TOKENS) - set(self.colors)
        if missing:
            raise ValueError(f"theme is missing tokens: {sorted(missing)}")

    def __getitem__(self, token: str) -> str:
        try:
            return self.colors[token]
        except KeyError as exc:
            raise KeyError(f"unknown semantic theme token: {token}") from exc


def _palette(scheme: ColorScheme, values: dict[str, str]) -> ThemePalette:
    return ThemePalette(scheme=scheme, colors=MappingProxyType(dict(values)))


DARK_PALETTE = _palette(
    ColorScheme.DARK,
    {
        "surface.app": "#08131f",
        "surface.navigation": "#0c1a28",
        "surface.canvas": "#07131f",
        "surface.card": "#102131",
        "surface.elevated": "#14283a",
        "surface.selected": "#24385b",
        "surface.control": "#132536",
        "surface.overlay": "#0b1725",
        "border.default": "#294056",
        "border.strong": "#3a536c",
        "text.primary": "#f4f7fb",
        "text.secondary": "#c5d1dc",
        "text.muted": "#9bafc1",
        "text.inverse": "#ffffff",
        "action.primary": "#684ac7",
        "action.primary_hover": "#7c5ce0",
        "action.danger": "#b84255",
        "action.danger_hover": "#d55265",
        "action.disabled": "#2a3c4e",
        "focus.ring": "#b29cff",
        "status.running": "#54d887",
        "status.waiting": "#f3b64d",
        "status.stale": "#e89c3d",
        "status.failed": "#ff6b7a",
        "status.info": "#63a9ff",
        "status.offline": "#9bafc1",
        "status.completed": "#54d887",
        "grid.line": "#132a3d",
        "cell.primary": "#3d5095",
        "cell.secondary": "#684ac7",
        "cell.quiet": "#18314a",
        "chart.1": "#b29cff",
        "chart.2": "#55d6c8",
        "chart.3": "#ffa148",
        "chart.4": "#69bfff",
        "chart.5": "#f47caf",
    },
)


LIGHT_PALETTE = _palette(
    ColorScheme.LIGHT,
    {
        "surface.app": "#f3f6fa",
        "surface.navigation": "#ffffff",
        "surface.canvas": "#e7edf4",
        "surface.card": "#ffffff",
        "surface.elevated": "#edf2f7",
        "surface.selected": "#e8e1fb",
        "surface.control": "#f7f9fc",
        "surface.overlay": "#ffffff",
        "border.default": "#c4d0dc",
        "border.strong": "#9bacc0",
        "text.primary": "#172435",
        "text.secondary": "#40536a",
        "text.muted": "#586b80",
        "text.inverse": "#ffffff",
        "action.primary": "#6042bd",
        "action.primary_hover": "#4f35a2",
        "action.danger": "#a51f38",
        "action.danger_hover": "#86162c",
        "action.disabled": "#d8e0e8",
        "focus.ring": "#5638b4",
        "status.running": "#147748",
        "status.waiting": "#8a5b00",
        "status.stale": "#a65300",
        "status.failed": "#ae243b",
        "status.info": "#2367aa",
        "status.offline": "#586b80",
        "status.completed": "#147748",
        "grid.line": "#d5dee8",
        "cell.primary": "#6776c8",
        "cell.secondary": "#7955d4",
        "cell.quiet": "#cbd6e5",
        "chart.1": "#6746c3",
        "chart.2": "#087f75",
        "chart.3": "#a95200",
        "chart.4": "#1769a8",
        "chart.5": "#a72d69",
    },
)


PALETTES = MappingProxyType(
    {
        ColorScheme.DARK: DARK_PALETTE,
        ColorScheme.LIGHT: LIGHT_PALETTE,
    }
)


def palette_for(scheme: ColorScheme | str) -> ThemePalette:
    return PALETTES[ColorScheme(scheme)]


def detect_system_scheme(
    environment: Mapping[str, str] | None = None,
) -> ColorScheme | None:
    """Best-effort desktop detection with no shell commands or dependencies."""
    values = os.environ if environment is None else environment
    explicit = str(
        values.get("MECHANISTIC_MIND_COLOR_SCHEME", "")
        or values.get("ARCHON_COLOR_SCHEME", "")
    ).strip().lower()
    if explicit in {item.value for item in ColorScheme}:
        return ColorScheme(explicit)
    gtk_theme = str(values.get("GTK_THEME", "")).lower()
    if "dark" in gtk_theme:
        return ColorScheme.DARK
    colorfgbg = str(values.get("COLORFGBG", ""))
    if colorfgbg:
        try:
            background = int(colorfgbg.split(";")[-1])
        except ValueError:
            pass
        else:
            return ColorScheme.DARK if background < 8 else ColorScheme.LIGHT
    return None


def resolve_scheme(
    preference: ThemeMode | str,
    *,
    system_scheme: ColorScheme | str | None = None,
    last_resolved: ColorScheme | str | None = None,
) -> ColorScheme:
    mode = ThemeMode(preference)
    if mode is ThemeMode.DARK:
        return ColorScheme.DARK
    if mode is ThemeMode.LIGHT:
        return ColorScheme.LIGHT
    if system_scheme is not None:
        return ColorScheme(system_scheme)
    if last_resolved is not None:
        return ColorScheme(last_resolved)
    return ColorScheme.DARK


def _linear_channel(value: int) -> float:
    channel = value / 255.0
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    if len(color) != 7 or not color.startswith("#"):
        raise ValueError(f"six-digit RGB color required: {color}")
    channels = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
    red, green, blue = (_linear_channel(value) for value in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    first = _luminance(foreground)
    second = _luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def accessibility_failures(palette: ThemePalette) -> tuple[str, ...]:
    """Return WCAG-AA failures for every normal-text pairing used by SHELL1."""
    pairs = (
        ("text.primary", "surface.app"),
        ("text.primary", "surface.navigation"),
        ("text.primary", "surface.canvas"),
        ("text.primary", "surface.card"),
        ("text.primary", "surface.elevated"),
        ("text.secondary", "surface.app"),
        ("text.secondary", "surface.card"),
        ("text.muted", "surface.app"),
        ("text.muted", "surface.card"),
        ("text.inverse", "action.primary"),
        ("text.inverse", "action.primary_hover"),
        ("text.inverse", "action.danger"),
    )
    failures = []
    for foreground, background in pairs:
        ratio = contrast_ratio(palette[foreground], palette[background])
        if ratio < 4.5:
            failures.append(f"{foreground}/{background}={ratio:.2f}")
    return tuple(failures)
