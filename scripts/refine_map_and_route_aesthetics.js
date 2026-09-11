const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. Enhanced DronePathLayer.ts with Planned Dashed Line + Station Nodes + Status Waypoints
const dronePathLayerCode = `import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import { BaseLayer } from '../BaseLayer';
import { FlightPath } from '../../types/mission';

/**
 * Operational Drone & Transit Flight Path Layer
 * Renders:
 * - Planned trajectory as subtle white dashed line
 * - Active traversed trajectory as high-visibility Twitter Blue / Cyan glowing line
 * - Station waypoints as crisp circular nodes (white with dark ring)
 * - Semantic highlight markers (Blue vehicle dot, Red alert dot, Green terminal dot)
 */
export class DronePathLayer extends BaseLayer {
  readonly id = 'drone-path';
  readonly name = 'Operational Trajectory & Waypoints';

  private activeSourceId = 'mission-routes-source';
  private plannedSourceId = 'mission-planned-source';
  private stationsSourceId = 'mission-stations-source';
  private map: MapLibreMap | null = null;

  private layerIds = [
    'route-planned-dashed',
    'route-active-casing',
    'route-active-surface',
    'route-active-highlight',
    'route-station-nodes-casing',
    'route-station-nodes-core',
    'route-special-markers',
  ];

  init(map: MapLibreMap): void {
    this.map = map;

    const emptyGeoJSON: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [],
    };

    [this.activeSourceId, this.plannedSourceId, this.stationsSourceId].forEach((src) => {
      if (!map.getSource(src)) {
        map.addSource(src, {
          type: 'geojson',
          data: emptyGeoJSON,
        });
      }
    });

    // 1. Planned Trajectory: White Dashed Line across the whole corridor
    if (!map.getLayer('route-planned-dashed')) {
      map.addLayer({
        id: 'route-planned-dashed',
        type: 'line',
        source: this.plannedSourceId,
        paint: {
          'line-color': '#FFFFFF',
          'line-width': 1.6,
          'line-dasharray': [3, 2.5],
          'line-opacity': 0.7,
        },
      });
    }

    // 2. Traversed Route: Active Casing (Dark Navy)
    if (!map.getLayer('route-active-casing')) {
      map.addLayer({
        id: 'route-active-casing',
        type: 'line',
        source: this.activeSourceId,
        paint: {
          'line-color': '#082f49',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 2.5, 8, 3.8, 11, 5.2, 14, 7.0],
          'line-opacity': 0.9,
        },
      });
    }

    // 3. Traversed Route: Surface (Golden Amber & Twitter Blue)
    if (!map.getLayer('route-active-surface')) {
      map.addLayer({
        id: 'route-active-surface',
        type: 'line',
        source: this.activeSourceId,
        paint: {
          'line-color': '#f59e0b',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1.8, 8, 2.8, 11, 4.0, 14, 5.2],
          'line-opacity': 1.0,
        },
      });
    }

    // 4. Traversed Route: Center Glow (Pure White/Gold)
    if (!map.getLayer('route-active-highlight')) {
      map.addLayer({
        id: 'route-active-highlight',
        type: 'line',
        source: this.activeSourceId,
        paint: {
          'line-color': '#FFFFFF',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.6, 8, 1.0, 11, 1.4, 14, 2.0],
          'line-opacity': 0.95,
        },
      });
    }

    // 5. Station Waypoint Nodes: Outer Ring (White circle)
    if (!map.getLayer('route-station-nodes-casing')) {
      map.addLayer({
        id: 'route-station-nodes-casing',
        type: 'circle',
        source: this.stationsSourceId,
        filter: ['==', ['get', 'type'], 'station'],
        paint: {
          'circle-radius': 5.5,
          'circle-color': '#FFFFFF',
          'circle-stroke-color': '#0B0F14',
          'circle-stroke-width': 2.2,
          'circle-opacity': 0.95,
        },
      });
    }

    // 6. Station Waypoint Nodes: Inner Core (Dark center hole)
    if (!map.getLayer('route-station-nodes-core')) {
      map.addLayer({
        id: 'route-station-nodes-core',
        type: 'circle',
        source: this.stationsSourceId,
        filter: ['==', ['get', 'type'], 'station'],
        paint: {
          'circle-radius': 2.2,
          'circle-color': '#111827',
        },
      });
    }

    // 7. Semantic Pin Markers: Blue, Red, Green dots
    if (!map.getLayer('route-special-markers')) {
      map.addLayer({
        id: 'route-special-markers',
        type: 'circle',
        source: this.stationsSourceId,
        filter: ['!=', ['get', 'type'], 'station'],
        paint: {
          'circle-radius': 6.0,
          'circle-color': ['get', 'color'],
          'circle-stroke-color': '#FFFFFF',
          'circle-stroke-width': 1.5,
          'circle-opacity': 1.0,
        },
      });
    }
  }

  updatePlannedPath(coords: [number, number][]): void {
    if (!this.map) return;
    const source = this.map.getSource(this.plannedSourceId) as GeoJSONSource | undefined;
    if (!source) return;

    if (!coords || coords.length < 2) {
      source.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    source.setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { status: 'planned' },
          geometry: { type: 'LineString', coordinates: coords },
        },
      ],
    });
  }

  updateStations(stations: { lng: number; lat: number; type: string; color?: string }[]): void {
    if (!this.map) return;
    const source = this.map.getSource(this.stationsSourceId) as GeoJSONSource | undefined;
    if (!source) return;

    source.setData({
      type: 'FeatureCollection',
      features: stations.map((s) => ({
        type: 'Feature',
        properties: { type: s.type, color: s.color || '#3b82f6' },
        geometry: { type: 'Point', coordinates: [s.lng, s.lat] },
      })),
    });
  }

  updatePath(pathData: FlightPath | { type: 'LineString'; coordinates: [number, number][] } | null): void {
    if (!this.map) return;
    const source = this.map.getSource(this.activeSourceId) as GeoJSONSource | undefined;
    if (!source) return;

    if (!pathData || !pathData.coordinates || pathData.coordinates.length === 0) {
      source.setData({
        type: 'FeatureCollection',
        features: [],
      });
      return;
    }

    const feature: GeoJSON.Feature = {
      type: 'Feature',
      properties: { status: 'active' },
      geometry: {
        type: 'LineString',
        coordinates: pathData.coordinates,
      },
    };

    source.setData({
      type: 'FeatureCollection',
      features: [feature],
    });
  }

  destroy(map: MapLibreMap): void {
    this.layerIds.forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
    });
    [this.activeSourceId, this.plannedSourceId, this.stationsSourceId].forEach((src) => {
      if (map.getSource(src)) map.removeSource(src);
    });
    this.map = null;
  }
}
`;
fs.writeFileSync(path.join(frontendRoot, 'layers/drone/DronePathLayer.ts'), dronePathLayerCode, 'utf8');
console.log('✓ Written layers/drone/DronePathLayer.ts');

// 2. Updated MapView.tsx: Configured with San Francisco corridor waypoints, smooth frame tracing, Twitter Blue completion footprint
const mapViewCode = `import React, { useEffect, useRef } from 'react';
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

// Default Golden Gate & SF Bay Corridor Waypoints (Matching Reference Layout exactly)
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

    map.on('style.load', () => {
      layerManager.initAll(map);
      // Initialize planned path and stations immediately for instant visual richness
      const pathLayer = layerManager.getLayer<DronePathLayer>('drone-path');
      pathLayer?.updatePlannedPath(DEFAULT_CORRIDOR_COORDS);
      pathLayer?.updateStations(DEFAULT_STATIONS);
    });

    map.on('load', () => {
      layerManager.initAll(map);
      const pathLayer = layerManager.getLayer<DronePathLayer>('drone-path');
      pathLayer?.updatePlannedPath(DEFAULT_CORRIDOR_COORDS);
      pathLayer?.updateStations(DEFAULT_STATIONS);
    });

    const handleResize = () => map.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      layerManager.destroyAll();
      map.remove();
      mapInstanceRef.current = null;
      layerManagerRef.current = null;
    };
  }, [openViewer]);

  // 2. Telemetry Synchronization: Traversed route, moving vehicle, Twitter Blue footprint
  useEffect(() => {
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

    // Default Twitter Blue Footprint Polygon around Central Station & Bayfront
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
  }, [mission, missionState, currentFrame, totalFrames, isCompleted]);

  return (
    <div ref={mapContainerRef} className="map-viewport relative" />
  );
};
`;
fs.writeFileSync(path.join(frontendRoot, 'components/MapView.tsx'), mapViewCode, 'utf8');
console.log('✓ Written components/MapView.tsx');

// 3. DashboardPanels.tsx: Crisp Reticle, Leader Line to Passenger Load Card, Razor-sharp summer tiles
const dashboardPanelsCode = `import React from 'react';
import { FleetStatusCounters } from './FleetStatusCounters';
import { OperationalEfficiency } from './OperationalEfficiency';
import { DroneUnitCard } from './DroneUnitCard';
import { MapHeader } from './MapHeader';
import { ScheduleOffset } from './ScheduleOffset';
import { PassengerVolume } from './PassengerVolume';
import { VideoUploadButton } from './VideoUploadButton';
import { ArrowUpRight, Play, Plus, Minus, Disc } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const DashboardPanels: React.FC = () => {
  const { togglePlay, isPlaying } = useReconstruction();

  const glassPillStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '16px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
  };

  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 p-4 pb-2 flex flex-col justify-between">
      {/* 1. FLOATING TITLE & DROPDOWNS: Top-left of map next to left sidebar */}
      <div className="absolute top-5 left-[370px] lg:left-[395px] xl:left-[415px] z-40 pointer-events-auto">
        <MapHeader />
      </div>

      {/* 2. TOP-RIGHT ACTIONS: Discreet Video Upload Button */}
      <div className="absolute top-5 right-5 z-40 pointer-events-auto flex items-center space-x-3">
        <VideoUploadButton />
      </div>

      {/* 3. CENTER MAP FLOATING RETICLE & LEADER LINE (Crystal-clear with dashed ring & play icon) */}
      <div className="absolute top-[38%] left-[54%] -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-auto flex items-center justify-center">
        {/* Radar Circular Dashed Ring (ZERO BLUR so buildings stay razor sharp) */}
        <div className="w-24 h-24 rounded-full border border-dashed border-white/50 bg-black/15 flex items-center justify-center shadow-[0_0_24px_rgba(0,0,0,0.4)] relative">
          {/* Inner Play/Start Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="w-9 h-9 rounded-full bg-white/25 hover:bg-white/40 active:scale-95 transition-all flex items-center justify-center cursor-pointer border border-white/40 shadow-lg"
            title={isPlaying ? 'Pause Flight' : 'Start Flight'}
          >
            <Play className="w-3.5 h-3.5 text-white fill-white ml-0.5" />
          </button>
        </div>
      </div>

      {/* 4. FLOATING PASSENGER LOAD 87% CARD HOVERING OVER ROUTE */}
      <div
        className="absolute top-[44%] left-[47%] z-30 pointer-events-auto p-3 flex flex-col space-y-1"
        style={glassPillStyle}
      >
        <div className="flex items-center justify-between space-x-3">
          <span className="text-[10.5px] font-medium text-white/80">Passenger Load</span>
          <ArrowUpRight className="w-3 h-3 text-white/50" />
        </div>
        <div className="text-[8px] font-mono text-white/40">
          Next: Central Station
        </div>
        <div className="text-[26px] font-light tracking-tight text-white font-mono leading-none pt-0.5">
          87%
        </div>
      </div>

      {/* 5. FLOATING ZOOM CONTROLS ON BOTTOM-LEFT OF MAP (Above bottom panels) */}
      <div className="absolute bottom-[205px] lg:bottom-[215px] xl:bottom-[230px] left-[370px] lg:left-[395px] xl:left-[415px] z-40 pointer-events-auto flex items-center space-x-1.5 p-1 rounded-full" style={glassPillStyle}>
        <button
          type="button"
          onClick={() => {
            const map = (window as any).gisMap;
            if (map) map.zoomIn();
          }}
          className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center cursor-pointer transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => {
            const map = (window as any).gisMap;
            if (map) map.panTo([-122.39, 37.79], { duration: 600 });
          }}
          className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center cursor-pointer transition-all"
        >
          <Disc className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => {
            const map = (window as any).gisMap;
            if (map) map.zoomOut();
          }}
          className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center cursor-pointer transition-all"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 6. MAIN SPATIAL WORKSPACE (Left Side Panels & Bottom Row Panels) */}
      <div className="relative z-30 w-full flex-1 flex gap-3.5 overflow-hidden pointer-events-none mb-1">
        {/* LEFT COLUMN STACK: Fleet Counters -> Operational Efficiency -> 2x2 Drone Unit Cards */}
        <aside className="w-[340px] lg:w-[365px] xl:w-[385px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto overflow-hidden">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <div className="flex-1 min-h-0 overflow-hidden">
            <DroneUnitCard />
          </div>
        </aside>

        {/* BOTTOM ROW: Schedule Offset (Left) & Live Passenger Volume / Timeline (Right) */}
        <section className="flex-1 h-full min-h-0 flex flex-col justify-end overflow-hidden relative">
          <div className="h-[175px] lg:h-[185px] xl:h-[195px] shrink-0 w-full pointer-events-auto grid grid-cols-12 gap-3.5">
            <div className="col-span-5 h-full">
              <ScheduleOffset />
            </div>
            <div className="col-span-7 h-full">
              <PassengerVolume />
            </div>
          </div>
        </section>
      </div>

      {/* 7. FOOTER STATUS BAR (At very bottom edge across screen) */}
      <div className="w-full flex items-center justify-between text-[10px] font-mono text-white/40 px-1 pt-1 pointer-events-none">
        <div className="flex items-center space-x-1.5">
          <span>Last updated: Today, 11:29:32 AM</span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block shadow-[0_0_6px_#22c55e]" />
        </div>
        <div className="flex items-center space-x-1.5">
          <span>Data sync: Real-time</span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block shadow-[0_0_6px_#22c55e]" />
        </div>
      </div>
    </div>
  );
};

export default DashboardPanels;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx'), dashboardPanelsCode, 'utf8');
console.log('✓ Written components/dashboard/DashboardPanels.tsx');
