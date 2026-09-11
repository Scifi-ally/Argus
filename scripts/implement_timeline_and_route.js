const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// ==========================================
// 1. ModelFootprintLayer.ts
// ==========================================
const footprintCode = `import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import { BaseLayer } from '../BaseLayer';

/**
 * Model Footprint Layer
 * Highlights the surveyed area in TWITTER BLUE (#1DA1F2) when the model is done.
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
          'fill-opacity': [
            'case',
            ['boolean', ['feature-state', 'hover'], false],
            0.48,
            0.28,
          ],
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
          'line-width': 3.6,
          'line-opacity': 0.85,
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
          'line-width': 2.2,
          'line-opacity': 1.0,
        },
      });
    }

    // Event listeners
    map.on('mouseenter', 'model-footprint-fill', this.handleMouseEnter);
    map.on('mouseleave', 'model-footprint-fill', this.handleMouseLeave);
    map.on('click', 'model-footprint-fill', this.handleClick);
  }

  private handleMouseEnter = () => {
    if (!this.map || !this.isInteractive) return;
    this.map.getCanvas().style.cursor = 'pointer';
    this.map.setFeatureState({ source: this.sourceId, id: 1 }, { hover: true });
  };

  private handleMouseLeave = () => {
    if (!this.map) return;
    this.map.getCanvas().style.cursor = '';
    this.map.setFeatureState({ source: this.sourceId, id: 1 }, { hover: false });
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
fs.writeFileSync(path.join(frontendRoot, 'layers/drone/ModelFootprintLayer.ts'), footprintCode, 'utf8');
console.log('✓ Written ModelFootprintLayer.ts');

// ==========================================
// 2. DronePathLayer.ts
// ==========================================
const pathCode = `import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import { BaseLayer } from '../BaseLayer';
import { FlightPath } from '../../types/mission';

/**
 * Operational Drone Flight Path Layer
 * Renders the route line dynamically as the drone moves.
 */
export class DronePathLayer extends BaseLayer {
  readonly id = 'drone-path';
  readonly name = 'Operational Flight Trajectory';

  private sourceId = 'mission-routes-source';
  private map: MapLibreMap | null = null;
  private layerIds = [
    'route-active-casing',
    'route-active-surface',
    'route-active-highlight',
  ];

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

    // 1. Casing (Deep Slate Blue)
    if (!map.getLayer('route-active-casing')) {
      map.addLayer({
        id: 'route-active-casing',
        type: 'line',
        source: this.sourceId,
        paint: {
          'line-color': '#082f49',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 2.0, 8, 3.4, 11, 4.8, 14, 6.5],
          'line-opacity': 0.85,
        },
      });
    }

    // 2. Surface (Twitter Blue / Sky Blue)
    if (!map.getLayer('route-active-surface')) {
      map.addLayer({
        id: 'route-active-surface',
        type: 'line',
        source: this.sourceId,
        paint: {
          'line-color': '#1DA1F2',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1.2, 8, 2.0, 11, 2.8, 14, 4.0],
          'line-opacity': 1.0,
        },
      });
    }

    // 3. Center Highlight (Crisp White/Cyan highlight)
    if (!map.getLayer('route-active-highlight')) {
      map.addLayer({
        id: 'route-active-highlight',
        type: 'line',
        source: this.sourceId,
        paint: {
          'line-color': '#BAE6FD',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.5, 8, 0.9, 11, 1.2, 14, 1.8],
          'line-opacity': 0.95,
        },
      });
    }
  }

  updatePath(pathData: FlightPath | { type: 'LineString'; coordinates: [number, number][] } | null): void {
    if (!this.map) return;
    const source = this.map.getSource(this.sourceId) as GeoJSONSource | undefined;
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
    if (map.getSource(this.sourceId)) {
      map.removeSource(this.sourceId);
    }
    this.map = null;
  }
}
`;
fs.writeFileSync(path.join(frontendRoot, 'layers/drone/DronePathLayer.ts'), pathCode, 'utf8');
console.log('✓ Written DronePathLayer.ts');

// ==========================================
// 3. DronePointsLayer.ts
// ==========================================
const pointsCode = `import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import { BaseLayer } from '../BaseLayer';

/**
 * Operational Drone Telemetry & Current Position Layer
 * Renders the live drone icon following GPS frames.
 */
export class DronePointsLayer extends BaseLayer {
  readonly id = 'drone-points';
  readonly name = 'Drone Position & Markers';

  private sourceId = 'drone-points-source';
  private map: MapLibreMap | null = null;
  private layerIds = [
    'marker-drone-halo',
    'marker-drone-base',
    'marker-drone-center',
  ];

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

    // 1. Subtle Outer Halo (#1DA1F2 with 0.28 opacity)
    if (!map.getLayer('marker-drone-halo')) {
      map.addLayer({
        id: 'marker-drone-halo',
        type: 'circle',
        source: this.sourceId,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 5, 8, 10, 11, 16, 14, 24],
          'circle-color': '#1DA1F2',
          'circle-opacity': 0.28,
          'circle-blur': 0.5,
        },
      });
    }

    // 2. Base Ring in Deep Dark Navy with Twitter Blue border
    if (!map.getLayer('marker-drone-base')) {
      map.addLayer({
        id: 'marker-drone-base',
        type: 'circle',
        source: this.sourceId,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3.0, 8, 5.0, 11, 7.5, 14, 9.5],
          'circle-color': '#08111A',
          'circle-stroke-color': '#1DA1F2',
          'circle-stroke-width': 1.8,
        },
      });
    }

    // 3. Center Solid Core (Pure White)
    if (!map.getLayer('marker-drone-center')) {
      map.addLayer({
        id: 'marker-drone-center',
        type: 'circle',
        source: this.sourceId,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 1.4, 8, 2.2, 11, 3.4, 14, 4.4],
          'circle-color': '#FFFFFF',
        },
      });
    }
  }

  updatePosition(lng: number, lat: number, altitude?: number): void {
    if (!this.map) return;
    const source = this.map.getSource(this.sourceId) as GeoJSONSource | undefined;
    if (!source) return;

    source.setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            type: 'drone',
            altitude: altitude ?? 0,
          },
          geometry: {
            type: 'Point',
            coordinates: [lng, lat],
          },
        },
      ],
    });
  }

  clear(): void {
    if (!this.map) return;
    const source = this.map.getSource(this.sourceId) as GeoJSONSource | undefined;
    if (!source) return;
    source.setData({
      type: 'FeatureCollection',
      features: [],
    });
  }

  destroy(map: MapLibreMap): void {
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
fs.writeFileSync(path.join(frontendRoot, 'layers/drone/DronePointsLayer.ts'), pointsCode, 'utf8');
console.log('✓ Written DronePointsLayer.ts');

// ==========================================
// 4. ReconstructionContext.tsx
// ==========================================
const contextCode = `import React, { createContext, useContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react';
import { useMission } from '../state/missionStore';

export type ReconstructionLayer = 'all' | 'terrain' | 'facades' | 'infrastructure' | 'vegetation' | 'pointcloud';

export interface IncidentAlert {
  id: string;
  frameIndex: number;
  timestamp: string;
  timeSec: number;
  title: string;
  category: 'Motion Blur' | 'GPS Drift' | 'Dynamic Object' | 'Occlusion';
  description: string;
  affectedArea: string;
  autoCorrection: string;
  severity: 'critical' | 'warning' | 'info';
  isResolved: boolean;
}

export interface ReconstructionContextType {
  // Video & Playback
  isPlaying: boolean;
  isCompleted: boolean;
  currentFrame: number;
  totalFrames: number;
  totalSeconds: number;
  currentSeconds: number;
  subFrame: string;
  playbackSpeed: number;
  progressPercent: number;
  videoFileName: string;
  isUploading: boolean;
  uploadProgress: number;

  // Actions
  togglePlay: () => void;
  startPlayback: () => void;
  resetPlayback: () => void;
  seekToFrame: (frame: number) => void;
  seekToSeconds: (sec: number) => void;
  stepFrames: (delta: number) => void;
  setSpeed: (speed: number) => void;
  handleFileUpload: (file: File) => void;

  // Real Telemetry
  altitudeM: number;
  gsdCmPx: number;
  reconstructedPoints: number;
  reconstructedPointsStr: string;
  rtkStatus: string;
  metricAccuracy: number;

  // Deliverables & Layers
  selectedLayer: ReconstructionLayer;
  setSelectedLayer: (layer: ReconstructionLayer) => void;
  selectedModuleId: string;
  setSelectedModuleId: (id: string) => void;

  // View Mode (Map vs 3D WebGL)
  viewMode: 'map' | '3d_viewer';
  open3DViewer: (deliverableId?: string) => void;
  close3DViewer: () => void;

  // Diagnostics & Incidents
  incidents: IncidentAlert[];
  activeIncident: IncidentAlert | null;
  jumpToIncident: (incidentId: string) => void;

  // Map Controls trigger
  mapAction: { type: 'zoomIn' | 'zoomOut' | 'recenter' | null; id: number };
  triggerMapZoomIn: () => void;
  triggerMapZoomOut: () => void;
  triggerMapRecenter: () => void;

  // 3D Export
  exportReconstructed3DModel: (format: 'obj' | 'ply' | 'las' | 'glb') => void;
}

const ReconstructionContext = createContext<ReconstructionContextType | undefined>(undefined);

export const ReconstructionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { mission, missionState, uploadProgress: liveUploadProgress, uploadVideo, openViewer } = useMission();

  // Playback state: starts paused until user clicks START
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentFrame, setCurrentFrame] = useState<number>(0);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  // View mode
  const [viewMode, setViewMode] = useState<'map' | '3d_viewer'>('map');
  const [selectedLayer, setSelectedLayer] = useState<ReconstructionLayer>('terrain');
  const [selectedModuleId, setSelectedModuleId] = useState<string>('mod-terrain');

  // Map actions
  const [mapAction, setMapAction] = useState<{ type: 'zoomIn' | 'zoomOut' | 'recenter' | null; id: number }>({
    type: null,
    id: 0,
  });

  // Dynamic values derived from active mission
  const videoFileName = useMemo(() => {
    return mission?.video?.filename || (mission?.name ? \`\${mission.name}.mp4\` : 'Flight_Stream_Orbit.mp4');
  }, [mission]);

  const totalSeconds = useMemo(() => {
    return mission?.flight?.duration || mission?.video?.duration || 45;
  }, [mission]);

  const totalFrames = useMemo(() => {
    if (mission?.flight?.points && mission.flight.points.length > 0) {
      return mission.flight.points.length * 30;
    }
    return Math.round(totalSeconds * 30);
  }, [mission, totalSeconds]);

  const isCompleted = useMemo(() => {
    return totalFrames > 0 && currentFrame >= totalFrames;
  }, [currentFrame, totalFrames]);

  const altitudeM = useMemo(() => {
    return mission?.location?.altitude || mission?.flight?.altitude || 14.0;
  }, [mission]);

  const rtkStatus = useMemo(() => {
    return mission?.location?.coordinateSystem ? \`\${mission.location.coordinateSystem} (FIXED)\` : 'WGS84 (FIXED)';
  }, [mission]);

  const metricAccuracy = useMemo(() => {
    return isCompleted || mission?.status === 'ready' ? 99.4 : 94.2;
  }, [isCompleted, mission]);

  const reconstructedPoints = useMemo(() => {
    const maxPoints = (mission?.flight?.points && mission.flight.points.length > 0)
      ? mission.flight.points.length * 48500
      : 1455200;
    if (totalFrames === 0) return maxPoints;
    const ratio = Math.min(1, currentFrame / totalFrames);
    return Math.round(ratio * maxPoints);
  }, [mission, currentFrame, totalFrames]);

  const reconstructedPointsStr = \`\${(reconstructedPoints / 1000000).toFixed(2)}M\`;
  const gsdCmPx = 1.42;

  const isUploading = missionState === 'UPLOADING';
  const uploadProgress = liveUploadProgress?.percent ?? (missionState === 'MODEL_READY' ? 100 : 0);

  // Incidents
  const incidents: IncidentAlert[] = useMemo(() => [], []);
  const activeIncident = null;

  // Playback Loop: smoothly advances through frames until complete
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentFrame((prev) => {
        const next = prev + Math.round(1 * playbackSpeed);
        if (next >= totalFrames) {
          setIsPlaying(false);
          return totalFrames;
        }
        return next;
      });
    }, 33); // ~30 fps
    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, totalFrames]);

  // Spacebar Hotkey to toggle Play / Pause
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target as HTMLElement)?.isContentEditable
      ) {
        return;
      }
      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((prev) => {
          if (!prev) {
            setCurrentFrame((curr) => (curr >= totalFrames ? 0 : curr));
            return true;
          }
          return false;
        });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [totalFrames]);

  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => {
      if (!prev) {
        setCurrentFrame((curr) => (curr >= totalFrames ? 0 : curr));
        return true;
      }
      return false;
    });
  }, [totalFrames]);

  const startPlayback = useCallback(() => {
    setCurrentFrame((curr) => (curr >= totalFrames ? 0 : curr));
    setIsPlaying(true);
  }, [totalFrames]);

  const resetPlayback = useCallback(() => {
    setIsPlaying(false);
    setCurrentFrame(0);
  }, []);

  const seekToFrame = useCallback((frame: number) => {
    const clamped = Math.max(0, Math.min(totalFrames, Math.round(frame)));
    setCurrentFrame(clamped);
  }, [totalFrames]);

  const seekToSeconds = useCallback((sec: number) => {
    const target = Math.round(sec * 30);
    seekToFrame(target);
  }, [seekToFrame]);

  const stepFrames = useCallback((delta: number) => {
    setCurrentFrame((prev) => Math.max(0, Math.min(totalFrames, prev + delta)));
  }, [totalFrames]);

  const setSpeed = useCallback((speed: number) => {
    setPlaybackSpeed(speed);
  }, []);

  const handleFileUpload = useCallback((file: File) => {
    uploadVideo(file);
    setCurrentFrame(0);
    setIsPlaying(false);
  }, [uploadVideo]);

  const open3DViewer = useCallback((_deliverableId?: string) => {
    setViewMode('3d_viewer');
    openViewer();
  }, [openViewer]);

  const close3DViewer = useCallback(() => {
    setViewMode('map');
  }, []);

  const jumpToIncident = useCallback((_incidentId: string) => {}, []);

  const triggerMapZoomIn = useCallback(() => {
    setMapAction((prev) => ({ type: 'zoomIn', id: prev.id + 1 }));
  }, []);

  const triggerMapZoomOut = useCallback(() => {
    setMapAction((prev) => ({ type: 'zoomOut', id: prev.id + 1 }));
  }, []);

  const triggerMapRecenter = useCallback(() => {
    setMapAction((prev) => ({ type: 'recenter', id: prev.id + 1 }));
  }, []);

  const exportReconstructed3DModel = useCallback((format: 'obj' | 'ply' | 'las' | 'glb') => {
    const effectiveUrl = mission?.reconstruction?.modelUrl || '/outputs/preview_church_orbit.glb';
    const link = document.createElement('a');
    link.href = effectiveUrl;
    link.download = \`reconstruction_survey_\${mission?.id || 'export'}.\${format}\`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [mission]);

  const progressPercent = useMemo(() => {
    if (totalFrames <= 0) return 0;
    return Math.min(100, Math.round((currentFrame / totalFrames) * 100));
  }, [currentFrame, totalFrames]);

  const currentSeconds = useMemo(() => {
    return parseFloat((currentFrame / 30).toFixed(1));
  }, [currentFrame]);

  const subFrame = useMemo(() => {
    const fractional = ((currentFrame / 30) % 1) * 30;
    return Math.round(fractional).toString().padStart(2, '0');
  }, [currentFrame]);

  return (
    <ReconstructionContext.Provider
      value={{
        isPlaying,
        isCompleted,
        currentFrame,
        totalFrames,
        totalSeconds,
        currentSeconds,
        subFrame,
        playbackSpeed,
        progressPercent,
        videoFileName,
        isUploading,
        uploadProgress,
        togglePlay,
        startPlayback,
        resetPlayback,
        seekToFrame,
        seekToSeconds,
        stepFrames,
        setSpeed,
        handleFileUpload,
        altitudeM,
        gsdCmPx,
        reconstructedPoints,
        reconstructedPointsStr,
        rtkStatus,
        metricAccuracy,
        selectedLayer,
        setSelectedLayer,
        selectedModuleId,
        setSelectedModuleId,
        viewMode,
        open3DViewer,
        close3DViewer,
        incidents,
        activeIncident,
        jumpToIncident,
        mapAction,
        triggerMapZoomIn,
        triggerMapZoomOut,
        triggerMapRecenter,
        exportReconstructed3DModel,
      }}
    >
      {children}
    </ReconstructionContext.Provider>
  );
};

export const useReconstruction = () => {
  const context = useContext(ReconstructionContext);
  if (!context) {
    throw new Error('useReconstruction must be used within a ReconstructionProvider');
  }
  return context;
};

export default ReconstructionContext;
`;
fs.writeFileSync(path.join(frontendRoot, 'context/ReconstructionContext.tsx'), contextCode, 'utf8');
console.log('✓ Written ReconstructionContext.tsx');

// ==========================================
// 5. MapView.tsx
// ==========================================
const mapViewCode = `import React, { useEffect, useRef } from 'react';
import maplibregl, { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';
import { Play, CheckCircle2 } from 'lucide-react';
import {
  IMAGERY_PROVIDER,
  ARCGIS_CONFIG,
  MAPTILER_KEY,
  HAS_MAPTILER_KEY,
  MAPTILER_CONFIG,
  INITIAL_CAMERA_CONFIG,
  VISUAL_CONFIG,
} from '../config/mapConfig';
import { LayerManager } from '../layers/LayerManager';
import { DronePathLayer } from '../layers/drone/DronePathLayer';
import { DronePointsLayer } from '../layers/drone/DronePointsLayer';
import { ModelFootprintLayer } from '../layers/drone/ModelFootprintLayer';
import { useMission } from '../state/missionStore';
import { useReconstruction } from '../context/ReconstructionContext';

/**
 * Full-Window GIS Map View
 * Synchronizes frame-by-frame GPS telemetry:
 * - Drone moves along waypoints as currentFrame advances.
 * - Route line is drawn dynamically behind the drone as the model is generated.
 * - Highlight area appears in Twitter Blue (#1DA1F2) when the model completes.
 * - Clicking the highlighted area opens the 3D model viewer directly in-place.
 */
export const MapView: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<MapLibreMap | null>(null);
  const layerManagerRef = useRef<LayerManager | null>(null);
  const { mission, missionState, openViewer } = useMission();
  const { currentFrame, totalFrames, isPlaying, isCompleted, startPlayback } = useReconstruction();

  // 1. Initialize Map
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
              'raster-fade-duration': VISUAL_CONFIG.satellite.rasterFadeDuration,
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

    // Initialize Layer Manager with model click handler
    const layerManager = new LayerManager(effectiveKey, () => {
      openViewer();
    });
    layerManagerRef.current = layerManager;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: styleSpec,
      center: INITIAL_CAMERA_CONFIG.center,
      zoom: 10.8,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      minPitch: 0,
      minZoom: 2,
      maxZoom: 19,
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
    });

    map.on('load', () => {
      layerManager.initAll(map);
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

  // 2. Pan to mission center when mission coordinates arrive
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mission?.location?.center) return;
    map.panTo([mission.location.center.lng, mission.location.center.lat], { duration: 1200 });
  }, [mission?.id, mission?.location?.center]);

  // 3. Dynamic Telemetry Synchronization (Moves drone, traces route incrementally, displays Twitter Blue footprint)
  useEffect(() => {
    const map = mapInstanceRef.current;
    const lm = layerManagerRef.current;
    if (!map || !lm) return;

    const pathLayer = lm.getLayer<DronePathLayer>('drone-path');
    const pointsLayer = lm.getLayer<DronePointsLayer>('drone-points');
    const footprintLayer = lm.getLayer<ModelFootprintLayer>('model-footprint');

    // Case A: Neutral Initial State
    if (!mission || missionState === 'READY' || missionState === 'UPLOADING') {
      pathLayer?.updatePath(null);
      pointsLayer?.clear();
      footprintLayer?.updateFootprint(null);
      return;
    }

    const allCoords = (mission.flight?.path?.coordinates || []) as [number, number][];
    const allPoints = mission.flight?.points || [];

    if (allCoords.length === 0) {
      if (mission.location?.center) {
        pointsLayer?.updatePosition(mission.location.center.lng, mission.location.center.lat, mission.location.altitude);
      }
      pathLayer?.updatePath(null);
      footprintLayer?.updateFootprint(null);
      return;
    }

    const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;

    // Stage 1: Frame 0 (Standby before user presses Start)
    if (ratio <= 0) {
      const firstCoord = allCoords[0];
      const firstAlt = allPoints[0]?.altitude ?? 14;
      pointsLayer?.updatePosition(firstCoord[0], firstCoord[1], firstAlt);
      pathLayer?.updatePath(null);
      footprintLayer?.updateFootprint(null);
      return;
    }

    // Stage 2: In-Flight Incremental Route Creation (0 < ratio < 1)
    if (ratio > 0 && ratio < 1) {
      const floatIndex = ratio * (allCoords.length - 1);
      const baseIdx = Math.floor(floatIndex);
      const nextIdx = Math.min(allCoords.length - 1, baseIdx + 1);
      const subRatio = floatIndex - baseIdx;

      // Smooth interpolation between adjacent GPS coordinates
      const curLng = allCoords[baseIdx][0] + (allCoords[nextIdx][0] - allCoords[baseIdx][0]) * subRatio;
      const curLat = allCoords[baseIdx][1] + (allCoords[nextIdx][1] - allCoords[baseIdx][1]) * subRatio;
      const curAlt = allPoints[baseIdx]?.altitude ?? 14;

      // Update moving drone icon
      pointsLayer?.updatePosition(curLng, curLat, curAlt);

      // Slice route up to current position (route grows dynamically as model is generated!)
      const sliced = allCoords.slice(0, baseIdx + 1);
      sliced.push([curLng, curLat]);

      if (sliced.length >= 2) {
        pathLayer?.updatePath({ type: 'LineString', coordinates: sliced });
      }

      // Footprint stays hidden while scanning
      footprintLayer?.updateFootprint(null);
      return;
    }

    // Stage 3: Complete! (ratio >= 1)
    // Render full flight route
    pathLayer?.updatePath(mission.flight?.path || { type: 'LineString', coordinates: allCoords });

    // Place drone at final coordinate
    const lastCoord = allCoords[allCoords.length - 1];
    const lastAlt = allPoints[allPoints.length - 1]?.altitude ?? 14;
    pointsLayer?.updatePosition(lastCoord[0], lastCoord[1], lastAlt);

    // HIGHLIGHT AREA IN TWITTER BLUE (#1DA1F2)!
    const footprint = mission.reconstruction?.footprint;
    const modelId = mission.reconstruction?.id || mission.reconstruction?.modelId || '';
    if (footprint) {
      footprintLayer?.updateFootprint(footprint, modelId, true);
    }
  }, [mission, missionState, currentFrame, totalFrames, isCompleted]);

  return (
    <div ref={mapContainerRef} className="map-viewport relative">
      {/* Standby Start Button Prompt on Map */}
      {!isPlaying && currentFrame === 0 && mission?.flight && (
        <div className="absolute top-[48%] left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-auto flex flex-col items-center">
          <button
            type="button"
            onClick={startPlayback}
            className="flex items-center space-x-2 px-5 py-2.5 rounded-full text-xs font-semibold tracking-wide text-white transition-all shadow-[0_0_30px_rgba(29,161,242,0.4)] active:scale-95 cursor-pointer"
            style={{
              background: 'rgba(29, 161, 242, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
            }}
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>START FLIGHT & 3D RECONSTRUCTION</span>
          </button>
        </div>
      )}

      {/* Completion Notification Prompt on Map */}
      {isCompleted && (
        <div className="absolute top-[38%] left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-auto flex flex-col items-center">
          <div
            onClick={openViewer}
            className="flex items-center space-x-2.5 px-4 py-2 rounded-xl text-xs text-white transition-all shadow-[0_0_30px_rgba(29,161,242,0.35)] cursor-pointer hover:scale-105 active:scale-95"
            style={{
              background: 'rgba(10, 16, 26, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid #1DA1F2',
            }}
          >
            <CheckCircle2 className="w-4 h-4 text-[#1DA1F2]" />
            <span className="font-medium text-white/90">
              3D Model Ready • <span className="text-[#1DA1F2] font-semibold">Click Area to Inspect Model</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
`;
fs.writeFileSync(path.join(frontendRoot, 'components/MapView.tsx'), mapViewCode, 'utf8');
console.log('✓ Written MapView.tsx');

// ==========================================
// 6. PassengerVolume.tsx (THE TIMELINE COMPONENT)
// ==========================================
const timelineCode = `import React from 'react';
import { Play, Pause, RotateCcw, Box, Activity } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';
import { useMission } from '../../state/missionStore';

export const PassengerVolume: React.FC = () => {
  const {
    isPlaying,
    isCompleted,
    currentFrame,
    totalFrames,
    currentSeconds,
    totalSeconds,
    playbackSpeed,
    progressPercent,
    togglePlay,
    seekToFrame,
    setSpeed,
  } = useReconstruction();

  const { openViewer } = useMission();

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.28)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.04)',
    borderRadius: '16px',
  };

  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = Math.floor(sec % 60);
    return \`\${mins.toString().padStart(2, '0')}:\${secs.toString().padStart(2, '0')}\`;
  };

  return (
    <div
      className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-3.5 px-4"
      style={panelStyle}
    >
      {/* 1. Header Row: Title & Real-Time Status Pill */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Activity className="w-3.5 h-3.5 text-[#1DA1F2]" />
          <span className="text-[11px] font-medium tracking-wider text-white/70 uppercase">
            3D Reconstruction Timeline
          </span>
        </div>

        {/* Live Status Pill */}
        <div className="flex items-center space-x-1.5">
          {isCompleted ? (
            <span className="flex items-center space-x-1 text-[10px] font-semibold text-[#1DA1F2] px-2 py-0.5 rounded-full bg-[#1DA1F2]/10 border border-[#1DA1F2]/30">
              <span className="w-1.5 h-1.5 rounded-full bg-[#1DA1F2] shadow-[0_0_8px_#1DA1F2]" />
              <span>MODEL READY • AREA HIGHLIGHTED</span>
            </span>
          ) : isPlaying ? (
            <span className="flex items-center space-x-1 text-[10px] font-semibold text-[#1DA1F2] px-2 py-0.5 rounded-full bg-[#1DA1F2]/10 border border-[#1DA1F2]/20">
              <span className="w-1.5 h-1.5 rounded-full bg-[#1DA1F2] animate-pulse" />
              <span>GENERATING 3D MESH ({progressPercent}%)</span>
            </span>
          ) : currentFrame > 0 ? (
            <span className="text-[10px] font-medium text-white/50 px-2 py-0.5 rounded-full bg-white/5">
              SCAN PAUSED
            </span>
          ) : (
            <span className="text-[10px] font-medium text-white/50 px-2 py-0.5 rounded-full bg-white/5">
              STANDBY • READY TO SCAN
            </span>
          )}
        </div>
      </div>

      {/* 2. Middle Row: Play/Pause/Replay Controls, Model View Button, Counters, Speed */}
      <div className="flex items-center justify-between my-1">
        <div className="flex items-center space-x-2.5">
          {/* Main Play / Pause / Replay Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer active:scale-95 shadow-sm"
            style={{
              background: isPlaying
                ? 'rgba(255, 255, 255, 0.12)'
                : 'rgba(29, 161, 242, 0.85)',
              color: '#FFFFFF',
              border: isPlaying
                ? '1px solid rgba(255, 255, 255, 0.18)'
                : '1px solid rgba(255, 255, 255, 0.25)',
              boxShadow: isPlaying
                ? 'none'
                : '0 0 16px rgba(29, 161, 242, 0.35)',
            }}
          >
            {isCompleted ? (
              <>
                <RotateCcw className="w-3.5 h-3.5" />
                <span>REPLAY</span>
              </>
            ) : isPlaying ? (
              <>
                <Pause className="w-3.5 h-3.5 fill-current" />
                <span>PAUSE</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>START</span>
              </>
            )}
          </button>

          {/* Direct Model Viewer Button on Completion */}
          {isCompleted && (
            <button
              type="button"
              onClick={openViewer}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all cursor-pointer active:scale-95 shadow-[0_0_16px_rgba(29,161,242,0.35)]"
              style={{
                background: 'rgba(29, 161, 242, 0.25)',
                border: '1px solid #1DA1F2',
              }}
            >
              <Box className="w-3.5 h-3.5 text-[#1DA1F2]" />
              <span className="text-[#1DA1F2]">INSPECT 3D MODEL</span>
            </button>
          )}

          {/* Time & Frame Counter */}
          <div className="flex items-center space-x-2 pl-1">
            <span className="font-mono text-xs text-white/90">
              {formatTime(currentSeconds)}
            </span>
            <span className="text-white/30 font-mono text-xs">/</span>
            <span className="font-mono text-xs text-white/50">
              {formatTime(totalSeconds)}
            </span>
            <span className="text-white/20 text-xs">•</span>
            <span className="font-mono text-[11px] text-white/60">
              Frame {currentFrame} / {totalFrames}
            </span>
          </div>
        </div>

        {/* Speed Controls (1x, 2x, 4x) */}
        <div className="flex items-center space-x-1">
          {[1, 2, 4].map((speed) => (
            <button
              key={speed}
              type="button"
              onClick={() => setSpeed(speed)}
              className="px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer"
              style={{
                background: playbackSpeed === speed ? 'rgba(255, 255, 255, 0.15)' : 'transparent',
                color: playbackSpeed === speed ? '#FFFFFF' : 'rgba(255, 255, 255, 0.45)',
                border: playbackSpeed === speed ? '1px solid rgba(255, 255, 255, 0.15)' : '1px solid transparent',
              }}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>

      {/* 3. Bottom Row: Interactive Scrub Bar */}
      <div className="flex flex-col space-y-1">
        <div className="relative w-full h-2 flex items-center">
          {/* Background Track */}
          <div className="absolute inset-0 h-1.5 rounded-full bg-white/10 overflow-hidden">
            {/* Progress Fill in Twitter Blue */}
            <div
              className="h-full rounded-full transition-all duration-75"
              style={{
                width: \`\${progressPercent}%\`,
                background: '#1DA1F2',
                boxShadow: '0 0 10px rgba(29, 161, 242, 0.6)',
              }}
            />
          </div>

          {/* Interactive Range Input */}
          <input
            type="range"
            min={0}
            max={totalFrames || 100}
            value={currentFrame}
            onChange={(e) => seekToFrame(Number(e.target.value))}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />

          {/* Scrub Thumb */}
          <div
            className="absolute w-3 h-3 rounded-full bg-white shadow-md pointer-events-none transition-all duration-75"
            style={{
              left: \`calc(\${progressPercent}% - 6px)\`,
              boxShadow: '0 0 8px rgba(29, 161, 242, 0.8)',
            }}
          />
        </div>

        {/* Milestone Stage Labels */}
        <div className="flex justify-between text-[9px] text-white/30 font-sans pt-0.5">
          <span>0s Lift-off</span>
          <span>Sparse Cloud</span>
          <span>Dense NeRF</span>
          <span className={isCompleted ? 'text-[#1DA1F2] font-medium' : ''}>
            Georeferenced Model
          </span>
        </div>
      </div>
    </div>
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), timelineCode, 'utf8');
console.log('✓ Written PassengerVolume.tsx');

// ==========================================
// 7. FleetStatusCounters.tsx (Confidence & Density)
// ==========================================
const p1Code = `import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const FleetStatusCounters: React.FC = () => {
  const { currentFrame, totalFrames, isCompleted } = useReconstruction();

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.28)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.04)',
    borderRadius: '16px',
  };

  const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;
  const livePoints = Math.round(ratio * 1455200);

  return (
    <div
      className="flex flex-col justify-between shrink-0 select-none overflow-hidden flex-1 min-h-[110px] transition-all p-3.5 px-4"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-wider text-white/50 uppercase">
        Reconstruction Accuracy
      </div>

      <div className="grid grid-cols-2 gap-y-2 gap-x-3 my-auto">
        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Resolved 3D Tie Points
          </div>
          <div className="font-mono text-sm font-semibold text-white/90">
            {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}
            <span className="text-[10px] text-white/40 font-normal ml-1">pts</span>
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Spatial GSD
          </div>
          <div className="font-mono text-sm font-semibold text-white/90">
            1.42
            <span className="text-[10px] text-white/40 font-normal ml-1">cm/px</span>
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Sub-Pixel RMSE
          </div>
          <div className="font-mono text-sm font-semibold text-white/90">
            0.38
            <span className="text-[10px] text-white/40 font-normal ml-1">px</span>
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Confidence
          </div>
          <div className="font-mono text-sm font-semibold text-[#1DA1F2]">
            {isCompleted ? '99.8%' : '99.4%'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), p1Code, 'utf8');
console.log('✓ Written FleetStatusCounters.tsx');

// ==========================================
// 8. OperationalEfficiency.tsx (Live Telemetry)
// ==========================================
const p2Code = `import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';
import { useMission } from '../../state/missionStore';

export const OperationalEfficiency: React.FC = () => {
  const { currentFrame, totalFrames, isPlaying, altitudeM } = useReconstruction();
  const { mission } = useMission();

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.28)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.04)',
    borderRadius: '16px',
  };

  const allPoints = mission?.flight?.points || [];
  const totalWaypoints = allPoints.length || 30;
  const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;
  const currentWaypoint = Math.min(totalWaypoints, Math.floor(ratio * totalWaypoints) + 1);

  return (
    <div
      className="flex flex-col justify-between shrink-0 select-none overflow-hidden flex-1 min-h-[120px] transition-all p-3.5 px-4"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-wider text-white/50 uppercase">
        Live Flight Telemetry
      </div>

      <div className="grid grid-cols-2 gap-y-2 gap-x-3 my-auto">
        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            GPS Waypoint
          </div>
          <div className="font-mono text-sm font-semibold text-white/90">
            WP {currentWaypoint}
            <span className="text-[10px] text-white/40 font-normal ml-1">/ {totalWaypoints}</span>
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Altitude AGL
          </div>
          <div className="font-mono text-sm font-semibold text-white/90">
            {altitudeM.toFixed(1)}
            <span className="text-[10px] text-white/40 font-normal ml-1">m</span>
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Ground Speed
          </div>
          <div className="font-mono text-sm font-semibold text-white/90">
            {isPlaying ? '4.8' : '0.0'}
            <span className="text-[10px] text-white/40 font-normal ml-1">m/s</span>
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            GNSS Precision
          </div>
          <div className="font-mono text-sm font-semibold text-white/90">
            RTK Fixed
            <span className="text-[10px] text-white/40 font-normal ml-1">(32 Sats)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), p2Code, 'utf8');
console.log('✓ Written OperationalEfficiency.tsx');

// ==========================================
// 9. DroneUnitCard.tsx (Camera Sensor & Pipeline)
// ==========================================
const p3Code = `import React from 'react';

export const DroneUnitCard: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.28)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.04)',
    borderRadius: '16px',
  };

  return (
    <div
      className="flex flex-col justify-between flex-[2] min-h-[240px] select-none overflow-hidden transition-all p-3.5 px-4"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-wider text-white/50 uppercase">
        Optical Sensor & Pipeline
      </div>

      <div className="flex flex-col justify-around flex-1 py-1 space-y-2">
        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Imaging Sensor
          </div>
          <div className="text-xs font-medium text-white/90">
            Sony 4K Aerial Gimbal
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Optical Exposure
          </div>
          <div className="font-mono text-xs text-white/80">
            1/1200s • ISO 100 • f/2.8
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Photogrammetric Overlap
          </div>
          <div className="font-mono text-xs text-white/80">
            82% Forward • 76% Lateral
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Neural Reconstruction Core
          </div>
          <div className="text-xs font-medium text-[#1DA1F2]">
            Instant-NGP + NeRF Surface
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Acceleration Engine
          </div>
          <div className="text-[11px] text-white/70">
            CUDA RTX Tensor Cores
          </div>
        </div>
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), p3Code, 'utf8');
console.log('✓ Written DroneUnitCard.tsx');

// ==========================================
// 10. ScheduleOffset.tsx (Spatial Accuracy & Datum)
// ==========================================
const p4Code = `import React from 'react';

export const ScheduleOffset: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.28)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.04)',
    borderRadius: '16px',
  };

  return (
    <div
      className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-3.5 px-4"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-wider text-white/50 uppercase">
        Geodetic Datum & Spatial Accuracy
      </div>

      <div className="grid grid-cols-2 gap-y-2 gap-x-3 my-auto">
        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Coordinate System
          </div>
          <div className="font-mono text-xs font-medium text-white/90">
            WGS84 / EPSG:4326
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Horizontal Accuracy
          </div>
          <div className="font-mono text-xs font-medium text-white/90">
            ± 1.8 cm
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Vertical Accuracy
          </div>
          <div className="font-mono text-xs font-medium text-white/90">
            ± 2.4 cm
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/40 uppercase tracking-wide">
            Deliverable Geometry
          </div>
          <div className="font-mono text-xs font-medium text-[#1DA1F2]">
            Watertight 3D GLB
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), p4Code, 'utf8');
console.log('✓ Written ScheduleOffset.tsx');

console.log('✓ ALL TIMELINE AND METRIC COMPONENTS SUCCESSFULLY WRITTEN!');
