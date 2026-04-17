/**
 * Backward-compatible shim — re-exports from ../config/mapsConfig.
 * Legacy code that imports MAP_SETTINGS, MARKER_COLORS from this file continues to work.
 */
import { MARKER_COLORS, DEFAULT_CENTER, DEFAULT_ZOOM, TILE_URL, TILE_ATTRIBUTION } from '../config/mapsConfig';

/** Legacy MAP_SETTINGS shape (used by older components) */
export const MAP_SETTINGS = {
  defaultCenter: { lat: DEFAULT_CENTER[0], lng: DEFAULT_CENTER[1] },
  defaultZoom:   DEFAULT_ZOOM,
};

export { MARKER_COLORS, DEFAULT_CENTER, DEFAULT_ZOOM, TILE_URL, TILE_ATTRIBUTION };
