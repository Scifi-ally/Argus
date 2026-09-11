const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. ModelFootprintLayer.ts: Ensure robust fill and line paint
const footprintLayerCode = `import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import { BaseLayer } from '../BaseLayer';

/**
 * Model Footprint Layer
 * Highlights the surveyed area in TWITTER BLUE (#1DA1F2) when the model is completed.
 * Clicking on the highlighted area opens the 3D model viewer directly in-place.
 */
export class ModelFootprintLayer extends BaseLayer {
  readonly id = 'model-footprint';
  readonly name = '3D Model Reconstruction Footprint';

  private sourceId = 'model-footprint-source';
  private map: MapLibreMap | null = null;
  private layerIds = [
    'model-footprint-fill',
    'model-footprint-casing',
    'model-footprint-line',
  ];

  private onModelClickCb: ((modelId: string) => void) | null = null;
  private isInteractive = false;
  private activeModelId: string = '';

  constructor(onModelClick?: (modelId: string) => void) {
    super();
    if (onModelClick) {
      this.onModelClickCb = onModelClick;
    }
  }

  setOnModelClick(cb: (modelId: string) => void): void {
    this.onModelClickCb = cb;
  }

  init(map: MapLibreMap): void {
    this.map = map;

    const emptyGeoJSON: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [],
    };

    if (!map.getSource(this.sourceId)) {
      map.addSource(this.sourceId, {
        type: 'geojson',
        data: emptyGeoJSON,
      });
    }

    // 1. Polygon Fill in Twitter Blue (#1DA1F2)
    if (!map.getLayer('model-footprint-fill')) {
      map.addLayer({
        id: 'model-footprint-fill',
        type: 'fill',
        source: this.sourceId,
        paint: {
          'fill-color': '#1DA1F2',
          'fill-opacity': 0.38,
        },
      });
    }

    // 2. Outer Casing in deep Twitter Blue tone
    if (!map.getLayer('model-footprint-casing')) {
      map.addLayer({
        id: 'model-footprint-casing',
        type: 'line',
        source: this.sourceId,
        paint: {
          'line-color': '#0B4E75',
          'line-width': 4.0,
          'line-opacity': 0.9,
        },
      });
    }

    // 3. Crisp Inner Boundary in vivid Twitter Blue (#1DA1F2)
    if (!map.getLayer('model-footprint-line')) {
      map.addLayer({
        id: 'model-footprint-line',
        type: 'line',
        source: this.sourceId,
        paint: {
          'line-color': '#1DA1F2',
          'line-width': 2.4,
          'line-opacity': 1.0,
        },
      });
    }

    map.on('mouseenter', 'model-footprint-fill', this.handleMouseEnter);
    map.on('mouseleave', 'model-footprint-fill', this.handleMouseLeave);
    map.on('click', 'model-footprint-fill', this.handleClick);
  }

  private handleMouseEnter = () => {
    if (!this.map || !this.isInteractive) return;
    this.map.getCanvas().style.cursor = 'pointer';
  };

  private handleMouseLeave = () => {
    if (!this.map) return;
    this.map.getCanvas().style.cursor = '';
  };

  private handleClick = () => {
    if (!this.isInteractive || !this.onModelClickCb) return;
    this.onModelClickCb(this.activeModelId);
  };

  updateFootprint(polygon: GeoJSON.Polygon | null, modelId: string = '', isReady: boolean = false): void {
    if (!this.map) return;
    const source = this.map.getSource(this.sourceId) as GeoJSONSource | undefined;
    if (!source) return;

    this.activeModelId = modelId;
    this.isInteractive = isReady;

    if (!isReady || !polygon || !polygon.coordinates || polygon.coordinates.length === 0) {
      source.setData({
        type: 'FeatureCollection',
        features: [],
      });
      return;
    }

    source.setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          id: 1,
          properties: {
            modelId,
            status: isReady ? 'ready' : 'processing',
          },
          geometry: polygon,
        },
      ],
    });
  }

  destroy(map: MapLibreMap): void {
    map.off('mouseenter', 'model-footprint-fill', this.handleMouseEnter);
    map.off('mouseleave', 'model-footprint-fill', this.handleMouseLeave);
    map.off('click', 'model-footprint-fill', this.handleClick);

    this.layerIds.forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
    });
    if (map.getSource(this.sourceId)) {
      map.removeSource(this.sourceId);
    }
    this.map = null;
  }
}
`;
fs.writeFileSync(path.join(frontendRoot, 'layers/drone/ModelFootprintLayer.ts'), footprintLayerCode, 'utf8');
console.log('✓ Written layers/drone/ModelFootprintLayer.ts');

// 2. MapView.tsx with isMapReady state to ensure immediate telemetry sync on style.load
const mapViewCode = `import React, { useEffect, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';
import {
  IMAGERY_PROVIDER,
  ARCGIS_CONFIG,
  MAPTILER_KEY,
  HAS_MAPTILER_KEY,
  MAPTILER_CONFIG,
  VISUAL_CONFIG,
} from '../config/mapConfig';
import { LayerManager } from '../layers/LayerManager';
import { DronePathLayer } from '../layers/drone/DronePathLayer';
import { DronePointsLayer } from '../layers/drone/DronePointsLayer';
import { ModelFootprintLayer } from '../layers/drone/ModelFootprintLayer';
import { useMission } from '../state/missionStore';
import { useReconstruction } from '../context/ReconstructionContext';
import { Box } from 'lucide-react';

const DEFAULT_CORRIDOR_COORDS: [number, number][] = [
  [-122.482, 37.834], // Marin Headlands Viewpoint
  [-122.476, 37.820], // Golden Gate North Tower
  [-122.474, 37.808], // Golden Gate South Tower
  [-122.462, 37.802], // Presidio / Crissy Field
  [-122.446, 37.800], // Marina Green
  [-122.434, 37.796], // Fort Mason / Pacific Heights
  [-122.418, 37.792], // North Beach / Financial District
  [-122.398, 37.790], // Ferry Building / Central Station Area
  [-122.388, 37.778], // Mission Bay Oracle Park
  [-122.384, 37.766], // Chase Center / Dogpatch
  [-122.382, 37.752], // Pier 70 Shipyard
  [-122.386, 37.736], // Hunters Point North
  [-122.394, 37.722], // Bayview Shoreline
  [-122.406, 37.712], // Candlestick Point
];

const DEFAULT_STATIONS = [
  { lng: -122.482, lat: 37.834, type: 'station' },
  { lng: -122.462, lat: 37.802, type: 'station' },
  { lng: -122.434, lat: 37.796, type: 'station' },
  { lng: -122.398, lat: 37.790, type: 'station' }, // Central Station
  { lng: -122.384, lat: 37.766, type: 'station' },
  { lng: -122.394, lat: 37.722, type: 'station' },
  // Semantic Accent Markers
  { lng: -122.390, lat: 37.810, type: 'marker', color: '#1d4ed8' }, // Blue Bay Marker
  { lng: -122.380, lat: 37.792, type: 'marker', color: '#ef4444' }, // Red Alert Marker
  { lng: -122.378, lat: 37.760, type: 'marker', color: '#84cc16' }, // Lime Green Waypoint
];

export const MapView: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<MapLibreMap | null>(null);
  const layerManagerRef = useRef<LayerManager | null>(null);
  const [isMapReady, setIsMapReady] = useState(false);
  const { mission, missionState, openViewer } = useMission();
  const { currentFrame, totalFrames, isCompleted } = useReconstruction();

  // 1. Initialize Map Canvas
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const effectiveKey = HAS_MAPTILER_KEY ? MAPTILER_KEY : '';
    let styleSpec: string | StyleSpecification;

    if (IMAGERY_PROVIDER === 'arcgis') {
      styleSpec = {
        version: 8,
        name: 'ArcGIS World Imagery Base',
        glyphs: effectiveKey
          ? MAPTILER_CONFIG.getGlyphsUrl(effectiveKey)
          : 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
        sources: {
          'arcgis-world-imagery-source': {
            type: 'raster',
            tiles: ARCGIS_CONFIG.tiles,
            tileSize: ARCGIS_CONFIG.tileSize,
            maxzoom: ARCGIS_CONFIG.maxzoom,
            attribution: ARCGIS_CONFIG.attribution,
          },
        },
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: {
              'background-color': VISUAL_CONFIG.canvasBackgroundColor,
            },
          },
          {
            id: 'satellite-base-imagery',
            type: 'raster',
            source: 'arcgis-world-imagery-source',
            paint: {
              'raster-opacity': VISUAL_CONFIG.satellite.rasterOpacity,
              'raster-saturation': VISUAL_CONFIG.satellite.rasterSaturation,
              'raster-contrast': VISUAL_CONFIG.satellite.rasterContrast,
              'raster-brightness-min': VISUAL_CONFIG.satellite.rasterBrightnessMin,
              'raster-brightness-max': VISUAL_CONFIG.satellite.rasterBrightnessMax,
              'raster-hue-rotate': VISUAL_CONFIG.satellite.rasterHueRotate,
              'raster-fade-duration': 0,
            },
          },
        ],
      };
    } else if (HAS_MAPTILER_KEY) {
      styleSpec = MAPTILER_CONFIG.getSatelliteStyleUrl(MAPTILER_KEY);
    } else {
      styleSpec = {
        version: 8,
        name: 'GIS Dark Canvas Base',
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: {
              'background-color': VISUAL_CONFIG.canvasBackgroundColor,
            },
          },
        ],
      };
    }

    const layerManager = new LayerManager(effectiveKey, () => {
      openViewer();
    });
    layerManagerRef.current = layerManager;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: styleSpec,
      center: [-122.39, 37.79],
      zoom: 11.2,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      minPitch: 0,
      minZoom: 11.2,
      maxZoom: 11.2,
      renderWorldCopies: false,
      fadeDuration: 0,
      dragPan: true,
      scrollZoom: true,
      boxZoom: false,
      dragRotate: false,
      keyboard: false,
      doubleClickZoom: false,
      touchZoomRotate: false,
      touchPitch: false,
      attributionControl: false,
    });

    mapInstanceRef.current = map;
    (window as any).gisMap = map;

    const handleReady = () => {
      layerManager.initAll(map).then(() => {
        setIsMapReady(true);
      });
    };

    map.on('style.load', handleReady);
    map.on('load', handleReady);

    const handleResize = () => map.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      layerManager.destroyAll();
      map.remove();
      mapInstanceRef.current = null;
      layerManagerRef.current = null;
      setIsMapReady(false);
    };
  }, [openViewer]);

  // 2. Telemetry Synchronization: Traversed route, moving vehicle, Twitter Blue footprint
  useEffect(() => {
    if (!isMapReady) return;
    const map = mapInstanceRef.current;
    const lm = layerManagerRef.current;
    if (!map || !lm) return;

    const pathLayer = lm.getLayer<DronePathLayer>('drone-path');
    const pointsLayer = lm.getLayer<DronePointsLayer>('drone-points');
    const footprintLayer = lm.getLayer<ModelFootprintLayer>('model-footprint');

    const allCoords = (mission?.flight?.path?.coordinates && mission.flight.path.coordinates.length > 0)
      ? (mission.flight.path.coordinates as [number, number][])
      : DEFAULT_CORRIDOR_COORDS;

    // Ensure planned path and stations are always drawn
    pathLayer?.updatePlannedPath(allCoords);
    pathLayer?.updateStations(DEFAULT_STATIONS);

    const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;

    // Initial Standby (ratio <= 0)
    if (ratio <= 0) {
      const startCoord = allCoords[0];
      pointsLayer?.updatePosition(startCoord[0], startCoord[1], 14);
      pathLayer?.updatePath(null);
      footprintLayer?.updateFootprint(null);
      return;
    }

    // In-Flight: Dynamic route trace advancing with frame progress (0 < ratio < 1)
    if (ratio > 0 && ratio < 1) {
      const floatIndex = ratio * (allCoords.length - 1);
      const baseIdx = Math.floor(floatIndex);
      const nextIdx = Math.min(allCoords.length - 1, baseIdx + 1);
      const subRatio = floatIndex - baseIdx;

      const curLng = allCoords[baseIdx][0] + (allCoords[nextIdx][0] - allCoords[baseIdx][0]) * subRatio;
      const curLat = allCoords[baseIdx][1] + (allCoords[nextIdx][1] - allCoords[baseIdx][1]) * subRatio;

      pointsLayer?.updatePosition(curLng, curLat, 14);

      const sliced = allCoords.slice(0, baseIdx + 1);
      sliced.push([curLng, curLat]);

      if (sliced.length >= 2) {
        pathLayer?.updatePath({ type: 'LineString', coordinates: sliced });
      }

      footprintLayer?.updateFootprint(null);
      return;
    }

    // Complete (ratio >= 1): Full traversed line + Twitter Blue (#1DA1F2) Footprint
    pathLayer?.updatePath({ type: 'LineString', coordinates: allCoords });
    const lastCoord = allCoords[allCoords.length - 1];
    pointsLayer?.updatePosition(lastCoord[0], lastCoord[1], 14);

    // Twitter Blue Footprint Polygon covering surveyed urban zone
    const defaultFootprint: GeoJSON.Polygon = {
      type: 'Polygon',
      coordinates: [[
        [-122.428, 37.808],
        [-122.378, 37.808],
        [-122.372, 37.760],
        [-122.422, 37.760],
        [-122.428, 37.808],
      ]],
    };

    const footprint = mission?.reconstruction?.footprint || defaultFootprint;
    const modelId = mission?.reconstruction?.id || 'sample_model';
    footprintLayer?.updateFootprint(footprint, modelId, true);
  }, [isMapReady, mission, missionState, currentFrame, totalFrames, isCompleted]);

  return (
    <div ref={mapContainerRef} className="map-viewport relative">
      {/* Floating Interactive 3D Model Ready Badge when completed */}
      {isCompleted && (
        <div className="absolute top-[48%] left-[54%] -translate-x-1/2 -translate-y-1/2 z-40 pointer-events-auto animate-bounce">
          <button
            type="button"
            onClick={openViewer}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-[#1DA1F2] hover:bg-[#1A91DA] text-white shadow-[0_0_24px_rgba(29,161,242,0.8)] border border-white/20 cursor-pointer font-medium text-[11.5px] transition-all active:scale-95"
          >
            <Box className="w-4 h-4 text-white" />
            <span>3D Model Ready — Click to Inspect</span>
          </button>
        </div>
      )}
    </div>
  );
};
`;
fs.writeFileSync(path.join(frontendRoot, 'components/MapView.tsx'), mapViewCode, 'utf8');
console.log('✓ Written components/MapView.tsx');
