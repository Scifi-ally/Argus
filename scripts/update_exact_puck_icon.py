from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FE_DIR = ROOT_DIR.parent / "SIHFrontend" / "src"

drone_points_code = """import maplibregl, { Map as MapLibreMap } from 'maplibre-gl';
import { BaseLayer } from '../BaseLayer';

/**
 * Tactical Vehicle Marker
 * Exact matching icon from master reference design:
 * - Concentric outer dashed circle (radius 54px, dash 4 4)
 * - Solid circular dark smoky slate puck (radius 27px, radial gradient #6F7872 to #3B433E)
 * - Solid white navigation triangle cursor with rounded corners pointing in the flight heading
 */
export class DronePointsLayer extends BaseLayer {
  readonly id = 'drone-points';
  readonly name = 'Drone Position & Markers';

  private map: MapLibreMap | null = null;
  private marker: maplibregl.Marker | null = null;
  private arrowElement: SVGGElement | null = null;

  init(map: MapLibreMap): void {
    this.map = map;

    // Create container for exact SVG marker
    const el = document.createElement('div');
    el.className = 'tactical-drone-marker';
    el.style.width = '140px';
    el.style.height = '140px';
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    el.style.pointerEvents = 'none';
    el.style.userSelect = 'none';

    el.innerHTML = `
      <svg width="140" height="140" viewBox="0 0 140 140" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="puckRadialGrad" cx="44%" cy="38%" r="65%">
            <stop offset="0%" stop-color="#6F7872" stop-opacity="0.95" />
            <stop offset="55%" stop-color="#555E58" stop-opacity="0.92" />
            <stop offset="100%" stop-color="#3B433E" stop-opacity="0.96" />
          </radialGradient>
          <filter id="puckDropShadow" x="-25%" y="-25%" width="150%" height="150%">
            <feDropShadow dx="0" dy="4" stdDeviation="4.5" flood-color="#000000" flood-opacity="0.6" />
          </filter>
        </defs>

        <!-- 1. Outer Dashed Circle -->
        <circle
          cx="70"
          cy="70"
          r="54"
          stroke="rgba(255, 255, 255, 0.65)"
          stroke-width="1.2"
          stroke-dasharray="4 4"
          fill="none"
        />

        <!-- 2. Circular Slate Puck with Soft Rim -->
        <circle
          cx="70"
          cy="70"
          r="27"
          fill="url(#puckRadialGrad)"
          stroke="rgba(255, 255, 255, 0.28)"
          stroke-width="1"
          filter="url(#puckDropShadow)"
        />

        <!-- 3. Solid White Navigation Triangle Cursor in Center -->
        <g id="drone-nav-arrow" transform="translate(70, 70) rotate(0)">
          <path
            d="M 8 0 L -6 -6.5 L -6 6.5 Z"
            fill="#FFFFFF"
            stroke="#FFFFFF"
            stroke-width="2"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        </g>
      </svg>
    `;

    this.arrowElement = el.querySelector('#drone-nav-arrow') as SVGGElement | null;

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
      this.arrowElement.setAttribute('transform', `translate(70, 70) rotate(${headingDeg})`);
    }
  }

  destroy(_map: MapLibreMap): void {
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
print("[OK] DronePointsLayer.ts updated with exact circular puck and white triangle cursor!")
