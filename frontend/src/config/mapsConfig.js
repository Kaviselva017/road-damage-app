// ── RoadWatch Map Configuration — OpenStreetMap / Leaflet ─────────────────────
// No API key required. 100% free.

/** Default map centre (centre of India) — used when no complaints loaded yet */
export const DEFAULT_CENTER = [20.5937, 78.9629]; // [lat, lng] — Leaflet tuple format

/** Zoom level when no data */
export const DEFAULT_ZOOM = 5;

/** Zoom level when centred on actual complaint data */
export const DETAIL_ZOOM = 14;

/**
 * Marker colours per the RoadWatch severity/status spec.
 * severity=high   && status≠completed → RED
 * severity=medium && status≠completed → ORANGE
 * severity=low    && status≠completed → GREEN
 * status=completed                    → GREY
 */
export const MARKER_COLORS = {
  high:      '#DC2626',
  medium:    '#EA580C',
  low:       '#16A34A',
  completed: '#6B7280',
};

/** OpenStreetMap Carto tile URL (free, no key) */
export const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';

/** OSM attribution — required by OSM licence */
export const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
