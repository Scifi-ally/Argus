from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FE_DIR = ROOT_DIR.parent / "SIHFrontend" / "src"

# ==============================================================================
# 1. Update DronePointsLayer.ts with Exact Icon from Screenshot
# ==============================================================================
drone_points_code = """import maplibregl, { Map as MapLibreMap } from 'maplibre-gl';
import { BaseLayer } from '../BaseLayer';

/**
 * Tactical Drone Marker
 * Exact matching icon from reference screenshot:
 * - Outer dashed radar circle
 * - Dark olive-slate gradient elliptical puck with specular rim & drop shadow
 * - Pure white navigation arrowhead with central HUD notch pointing in heading direction
 */
export class DronePointsLayer extends BaseLayer {
  readonly id = 'drone-points';
  readonly name = 'Drone Position & Markers';

  private map: MapLibreMap | null = null;
  private marker: maplibregl.Marker | null = null;
  private arrowElement: SVGGElement | null = null;

  init(map: MapLibreMap): void {
    this.map = map;

    // Create container for custom SVG marker
    const el = document.createElement('div');
    el.className = 'tactical-drone-marker';
    el.style.width = '120px';
    el.style.height = '120px';
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    el.style.pointerEvents = 'none';
    el.style.userSelect = 'none';

    el.innerHTML = `
      <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="dronePuckGrad" cx="42%" cy="36%" r="65%">
            <stop offset="0%" stop-color="#5E6860" />
            <stop offset="55%" stop-color="#464E48" />
            <stop offset="100%" stop-color="#2D342F" />
          </radialGradient>
          <linearGradient id="droneRimGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="rgba(255, 255, 255, 0.65)" />
            <stop offset="45%" stop-color="rgba(255, 255, 255, 0.15)" />
            <stop offset="100%" stop-color="rgba(0, 0, 0, 0.5)" />
          </linearGradient>
          <filter id="dronePuckShadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="4" stdDeviation="4.5" flood-color="#000000" flood-opacity="0.75" />
          </filter>
        </defs>

        <!-- 1. Outer Dashed Circle -->
        <circle
          cx="60"
          cy="60"
          r="52"
          stroke="rgba(255, 255, 255, 0.72)"
          stroke-width="1.2"
          stroke-dasharray="4.5 4.5"
          fill="none"
        />

        <!-- 2. Dark Greenish-Gray Elliptical Puck with Specular Highlight -->
        <g transform="translate(60, 60)" filter="url(#dronePuckShadow)">
          <ellipse
            cx="0"
            cy="0"
            rx="25"
            ry="19"
            fill="url(#dronePuckGrad)"
            stroke="url(#droneRimGrad)"
            stroke-width="1.2"
          />

          <!-- Top Specular Crescent Rim -->
          <path
            d="M -20 -4 C -15 -14, 15 -14, 20 -4 C 15 -10, -15 -10, -20 -4 Z"
            fill="rgba(255, 255, 255, 0.22)"
          />

          <!-- 3. White Tactical Avionics Dart in Center -->
          <g id="drone-arrow-dart">
            <path
              d="M -7 -6 C -6.5 -6, 2 -2.5, 7.5 -0.5 C 8.2 -0.2, 8.2 0.2, 7.5 0.5 C 2 2.5, -6.5 6, -7 6 C -7.5 6, -7.8 5.4, -7.4 4.8 L -4.8 1 C -4.5 0.5, -4.5 -0.5, -4.8 -1 L -7.4 -4.8 C -7.8 -5.4, -7.5 -6, -7 -6 Z"
              fill="#FFFFFF"
            />
            <rect
              x="-2"
              y="-1"
              width="4.8"
              height="2"
              rx="1"
              fill="#3F4640"
            />
          </g>
        </g>
      </svg>
    `;

    this.arrowElement = el.querySelector('#drone-arrow-dart') as SVGGElement | null;

    this.marker = new maplibregl.Marker({
      element: el,
      anchor: 'center',
    });

    this.marker.addTo(map);
  }

  updatePosition(lng: number, lat: number, _altitude?: number, headingDeg?: number): void {
    if (!this.marker || !this.map) return;
    this.marker.setLngLat([lng, lat]);

    if (this.arrowElement && headingDeg !== undefined && !isNaN(headingDeg)) {
      this.arrowElement.setAttribute('transform', `rotate(${headingDeg})`);
    }
  }

  destroy(map: MapLibreMap): void {
    if (this.marker) {
      this.marker.remove();
      this.marker = null;
    }
    this.arrowElement = null;
    this.map = null;
  }
}

export default DronePointsLayer;
"""

(FE_DIR / "layers" / "drone" / "DronePointsLayer.ts").write_text(drone_points_code, encoding="utf-8")
print("[OK] DronePointsLayer.ts updated with exact screenshot icon")

# ==============================================================================
# 2. Update MapView.tsx to pass headingDeg to pointsLayer.updatePosition
# ==============================================================================
mapview_path = FE_DIR / "components" / "MapView.tsx"
mapview_code = mapview_path.read_text(encoding="utf-8")

# Add heading helper function inside MapView
heading_helper = """
    // Helper to calculate visual heading degrees (0 deg points East / right)
    const getHeadingDeg = (p1: [number, number], p2: [number, number]) => {
      const dx = (p2[0] - p1[0]) * Math.cos((p1[1] * Math.PI) / 180);
      const dy = p2[1] - p1[1];
      return Math.atan2(-dy, dx) * (180 / Math.PI);
    };
"""

# Replace the updatePosition calls to include heading
old_ratio_zero = """    if (ratio <= 0) {
      const startCoord = allCoords[0];
      pointsLayer?.updatePosition(startCoord[0], startCoord[1], 14);
      pathLayer?.updatePath(null);
      footprintLayer?.updateFootprint(null);
      return;
    }"""

new_ratio_zero = """    // Helper to calculate visual heading degrees (0 deg points East / right)
    const getHeadingDeg = (p1: [number, number], p2: [number, number]) => {
      const dx = (p2[0] - p1[0]) * Math.cos((p1[1] * Math.PI) / 180);
      const dy = p2[1] - p1[1];
      return Math.atan2(-dy, dx) * (180 / Math.PI);
    };

    // Initial Standby (ratio <= 0): Standing at start point, oriented along corridor
    if (ratio <= 0) {
      const startCoord = allCoords[0];
      const nextCoord = allCoords[1] || allCoords[0];
      const heading = getHeadingDeg(startCoord, nextCoord);
      pointsLayer?.updatePosition(startCoord[0], startCoord[1], 14, heading);
      pathLayer?.updatePath(null);
      footprintLayer?.updateFootprint(null);
      return;
    }"""

old_ratio_mid = """      pointsLayer?.updatePosition(curLng, curLat, 14);

      const sliced = allCoords.slice(0, baseIdx + 1);"""

new_ratio_mid = """      const heading = getHeadingDeg(allCoords[baseIdx], allCoords[nextIdx]);
      pointsLayer?.updatePosition(curLng, curLat, 14, heading);

      const sliced = allCoords.slice(0, baseIdx + 1);"""

old_ratio_one = """    pathLayer?.updatePath({ type: 'LineString', coordinates: allCoords });
    const lastCoord = allCoords[allCoords.length - 1];
    pointsLayer?.updatePosition(lastCoord[0], lastCoord[1], 14);"""

new_ratio_one = """    pathLayer?.updatePath({ type: 'LineString', coordinates: allCoords });
    const lastCoord = allCoords[allCoords.length - 1];
    const prevCoord = allCoords[allCoords.length - 2] || lastCoord;
    const finalHeading = getHeadingDeg(prevCoord, lastCoord);
    pointsLayer?.updatePosition(lastCoord[0], lastCoord[1], 14, finalHeading);"""

# Apply replacements with CRLF handling
def do_replace(target, old, new):
    if old in target:
        return target.replace(old, new)
    old_crlf = old.replace("\\n", "\\r\\n")
    new_crlf = new.replace("\\n", "\\r\\n")
    if old_crlf in target:
        return target.replace(old_crlf, new_crlf)
    print(f"[WARN] Failed to replace block:\\n{old[:50]}...")
    return target

mapview_code = do_replace(mapview_code, old_ratio_zero, new_ratio_zero)
mapview_code = do_replace(mapview_code, old_ratio_mid, new_ratio_mid)
mapview_code = do_replace(mapview_code, old_ratio_one, new_ratio_one)

mapview_path.write_text(mapview_code, encoding="utf-8")
print("[OK] MapView.tsx updated with heading calculation")
print("Exact map icon applied successfully!")
