"""Mapbox raster basemaps (M7). The token is a public `pk.` token; it ends up in the page."""

STYLES = {
    "light": ("Light", "light-v11"),
    "dark": ("Dark", "dark-v11"),
    "streets": ("Streets", "streets-v12"),
    "outdoors": ("Outdoors", "outdoors-v12"),
    "satellite": ("Satellite", "satellite-streets-v12"),
}
ATTRIBUTION = (
    '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> '
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
    '<a href="https://www.mapbox.com/map-feedback/">Improve this map</a>'
)


def basemap_url(style: str, token: str) -> str | None:
    if not token:
        return None
    style_id = STYLES.get(style, STYLES["light"])[1]
    return (
        f"https://api.mapbox.com/styles/v1/mapbox/{style_id}/tiles/512/{{z}}/{{x}}/{{y}}@2x"
        f"?access_token={token}"
    )


def basemaps(token: str) -> dict[str, dict[str, str]]:
    """All styles as {key: {label, url}}, or {} without a token."""
    if not token:
        return {}
    return {
        key: {"label": label, "url": basemap_url(key, token) or ""}
        for key, (label, _) in STYLES.items()
    }
