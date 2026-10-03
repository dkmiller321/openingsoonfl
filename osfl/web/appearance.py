"""Theme + palette preference (M8). Stored client-side in the `osfl_appearance` cookie
("theme:palette") and read here so pages render with the right attributes (no flash)."""

from fastapi import Request

COOKIE = "osfl_appearance"
THEMES = {"light": "Light", "dark": "Dark", "system": "System"}
# key: (label, accent, applied, licensed) - the swatch colours shown in the panel
PALETTES = {
    "classic": ("Classic", "#000000", "#e39b1b", "#2e8b57"),
    "ocean": ("Ocean", "#0b4f8a", "#38bdf8", "#0d9488"),
    "sunset": ("Sunset", "#e2553a", "#f59e0b", "#7c3aed"),
    "forest": ("Forest", "#166534", "#ca8a04", "#059669"),
    "grape": ("Grape", "#6d28d9", "#db2777", "#4f46e5"),
    "cb": ("Colour-blind safe", "#0072b2", "#e69f00", "#0072b2"),
}


def appearance(request: Request) -> tuple[str, str]:
    raw = request.cookies.get(COOKIE, "")
    theme, _, palette = raw.partition(":")
    return (
        theme if theme in THEMES else "light",
        palette if palette in PALETTES else "classic",
    )
