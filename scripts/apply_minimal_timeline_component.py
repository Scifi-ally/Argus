import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FE_DIR = ROOT_DIR.parent / "SIHFrontend" / "src"

# ==============================================================================
# 1. TimelinePanel.tsx - Super Clean Minimal Timeline Component in Bottom Right Box
# ==============================================================================
timeline_code = """import React, { useState, useRef } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const TimelinePanel: React.FC = () => {
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
    resetPlayback,
    seekToFrame,
    setSpeed,
    altitudeM,
    gsdCmPx,
    rtkStatus,
  } = useReconstruction();

  const [hoverPercent, setHoverPercent] = useState<number | null>(null);
  const trackRef = useRef<HTMLDivElement | null>(null);

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  const duration = totalSeconds || 45;
  const frames = totalFrames || 1350;
  const ratio = frames > 0 ? Math.min(1, currentFrame / frames) : 0;
  const livePoints = Math.round(ratio * 1455200);

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const update = (clientX: number) => {
      const x = Math.max(0, Math.min(rect.width, clientX - rect.left));
      const pct = x / rect.width;
      seekToFrame(Math.round(pct * frames));
    };
    update(e.clientX);

    const onPointerMove = (moveEvent: PointerEvent) => update(moveEvent.clientX);
    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    setHoverPercent((x / rect.width) * 100);
  };

  // 42 keyframe ticks along duration
  const keyframes = Array.from({ length: 42 }, (_, i) => i);

  return (
    <div
      className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-3.5"
      style={glassStyle}
    >
      {/* 1. Header: Play button, Timecode, Points & State */}
      <div className="flex items-center justify-between">
        {/* Left: Essential Controls Cluster */}
        <div className="flex items-center space-x-2.5">
          {/* Tactile Circular Play/Pause Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="w-7 h-7 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-[0_0_12px_rgba(255,255,255,0.45)] cursor-pointer shrink-0"
            title={isPlaying ? 'Pause' : 'Start'}
          >
            {isPlaying ? (
              <Pause className="w-3.5 h-3.5 fill-black stroke-black" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-black stroke-black translate-x-0.5" />
            )}
          </button>

          {/* Quick Reset */}
          <button
            type="button"
            onClick={resetPlayback}
            className="w-5 h-5 rounded-full bg-white/[0.08] hover:bg-white/[0.18] text-white/60 hover:text-white flex items-center justify-center transition-all cursor-pointer"
            title="Reset to 00:00"
          >
            <RotateCcw className="w-2.5 h-2.5" />
          </button>

          {/* Clean Timecode */}
          <div className="flex items-baseline space-x-1 font-mono text-[12px]">
            <span className="text-white font-medium tracking-tight">
              {formatTime(currentSeconds)}
            </span>
            <span className="text-white/30">/</span>
            <span className="text-white/50">
              {formatTime(duration)}
            </span>
          </div>

          {/* Frame Count */}
          <div className="flex items-baseline space-x-1 font-mono text-[9px] text-white/40 pl-1 border-l border-white/[0.08]">
            <span className="text-white/25">F:</span>
            <span className="text-white/80 font-medium">{currentFrame}</span>
            <span className="text-white/25">/</span>
            <span>{frames}</span>
          </div>

          {/* Speed Toggle */}
          <button
            type="button"
            onClick={() => setSpeed(playbackSpeed === 1 ? 2 : playbackSpeed === 2 ? 4 : 1)}
            className="px-1.5 py-0.5 rounded bg-white/[0.08] hover:bg-white/15 text-[9px] font-mono text-white/70 hover:text-white transition-all cursor-pointer border border-white/[0.08]"
            title="Toggle playback speed"
          >
            {playbackSpeed}x
          </button>
        </div>

        {/* Right: Live Reconstructed Points & Status */}
        <div className="flex items-center space-x-2.5 font-mono">
          <div className="flex items-baseline space-x-1">
            <span className="text-[17px] font-light text-white tracking-tight leading-none">
              {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}
            </span>
            <span className="text-[8.5px] text-white/40 uppercase">pts</span>
          </div>

          <div className="flex items-center space-x-1.5 text-[8.5px] text-white/70">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isCompleted
                  ? 'bg-[#1DA1F2] shadow-[0_0_8px_#1DA1F2]'
                  : isPlaying
                  ? 'bg-white animate-pulse shadow-[0_0_8px_#ffffff]'
                  : 'bg-white/40'
              }`}
            />
            <span className={isCompleted ? 'text-[#1DA1F2] font-medium' : ''}>
              {isCompleted ? 'COMPLETED' : isPlaying ? 'MAPPING' : 'STANDBY'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Interactive Scrubber Track */}
      <div
        ref={trackRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setHoverPercent(null)}
        className="relative w-full my-1.5 flex flex-col justify-center cursor-pointer select-none py-1 group"
      >
        {/* Track Bar */}
        <div className="relative w-full h-[28px] bg-white/[0.05] rounded-lg border border-white/[0.10] overflow-hidden group-hover:border-white/20 transition-all flex items-center">
          {/* Traversed progress fill */}
          <div
            className="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-white/10 via-white/20 to-white/30 border-r border-white/60 transition-all duration-75"
            style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
          />

          {/* Keyframe tick marks */}
          <div className="absolute inset-0 flex items-center justify-between px-1 pointer-events-none">
            {keyframes.map((k) => {
              const kPct = (k / keyframes.length) * 100;
              const isPast = kPct <= progressPercent;
              return (
                <div
                  key={k}
                  className={`w-[1px] rounded-full transition-all duration-150 ${
                    isPast
                      ? 'h-2.5 bg-white/90 shadow-[0_0_3px_#ffffff]'
                      : 'h-1.5 bg-white/15'
                  }`}
                />
              );
            })}
          </div>

          {/* Hover ghost line */}
          {hoverPercent !== null && (
            <div
              className="absolute top-0 bottom-0 w-[1px] bg-white/40 pointer-events-none transition-opacity"
              style={{ left: `${hoverPercent}%` }}
            />
          )}

          {/* Active playhead needle */}
          <div
            className="absolute top-0 bottom-0 pointer-events-none transition-all duration-75 flex flex-col items-center z-20"
            style={{ left: `${Math.max(0, Math.min(100, progressPercent))}%` }}
          >
            <div className="w-2.5 h-2.5 rounded-full bg-white shadow-[0_0_8px_#ffffff] -translate-y-1.5 border border-black/20 shrink-0" />
            <div className="w-[1.5px] flex-1 bg-white shadow-[0_0_6px_#ffffff]" />
            <div className="w-1.5 h-0.5 bg-white rounded-b-sm shadow-[0_0_4px_#ffffff] translate-y-0.5 shrink-0" />
          </div>
        </div>
      </div>

      {/* 3. Footer Telemetry & RTK Status */}
      <div className="flex items-center justify-between text-[8.5px] font-mono text-white/50 pt-1 border-t border-white/[0.08]">
        <div className="flex items-center space-x-2.5">
          <span>ALT: <strong className="text-white font-normal">{altitudeM ? altitudeM.toFixed(1) : '14.0'}m</strong></span>
          <span className="text-white/20">•</span>
          <span>GSD: <strong className="text-white font-normal">{gsdCmPx ? gsdCmPx.toFixed(2) : '1.42'} cm/px</strong></span>
          <span className="text-white/20">•</span>
          <span>PROGRESS: <strong className="text-white font-normal">{progressPercent}%</strong></span>
        </div>

        <div className="flex items-center space-x-2">
          <span>GNSS: <strong className="text-white font-normal">{rtkStatus ? 'RTK FIXED' : 'CARRIER LOCK'}</strong></span>
        </div>
      </div>
    </div>
  );
};

export default TimelinePanel;
"""

(FE_DIR / "components" / "dashboard" / "TimelinePanel.tsx").write_text(timeline_code, encoding="utf-8")
print("[OK] TimelinePanel.tsx updated")

# ==============================================================================
# 2. FleetStatusCounters.tsx - Altitude, RTK, GSD, Speed
# ==============================================================================
fleet_code = """import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const FleetStatusCounters: React.FC = () => {
  const { altitudeM, rtkStatus, gsdCmPx } = useReconstruction();

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="grid grid-cols-2 gap-2.5 select-none shrink-0 h-[64px]">
      {/* Left Card: RTK Status & Altitude */}
      <div className="p-3.5 flex items-center justify-between transition-all hover:border-white/20 h-full" style={glassStyle}>
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-white animate-pulse shadow-[0_0_8px_#ffffff]" />
          <span className="text-[11px] font-mono text-white/90 font-medium">
            {rtkStatus ? 'RTK FIXED' : 'ACTIVE'}
          </span>
        </div>
        <div className="text-right">
          <span className="text-[26px] font-light tracking-tight text-white leading-none font-mono">
            {altitudeM ? altitudeM.toFixed(1) : '14.0'}
          </span>
          <span className="text-[10px] font-mono text-white/45 ml-0.5">m</span>
        </div>
      </div>

      {/* Right Card: GSD Precision */}
      <div className="p-3.5 flex items-center justify-between transition-all hover:border-white/20 h-full" style={glassStyle}>
        <div className="flex items-center space-x-2">
          <span className="text-[10px] text-white/80 font-mono">▲</span>
          <span className="text-[11px] font-mono text-white/90 font-medium">GSD</span>
        </div>
        <div className="text-right">
          <span className="text-[26px] font-light tracking-tight text-white leading-none font-mono">
            {gsdCmPx ? gsdCmPx.toFixed(2) : '1.42'}
          </span>
          <span className="text-[10px] font-mono text-white/45 ml-0.5">cm</span>
        </div>
      </div>
    </div>
  );
};

export default FleetStatusCounters;
"""

(FE_DIR / "components" / "dashboard" / "FleetStatusCounters.tsx").write_text(fleet_code, encoding="utf-8")
print("[OK] FleetStatusCounters.tsx updated")

# ==============================================================================
# 3. OperationalEfficiency.tsx - Reconstruction Coverage & Inlier Tracking
# ==============================================================================
op_code = """import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const OperationalEfficiency: React.FC = () => {
  const { metricAccuracy, isPlaying, isCompleted, progressPercent } = useReconstruction();

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="rounded-2xl p-3.5 shrink-0 select-none overflow-hidden transition-all h-[155px] flex flex-col justify-between" style={glassStyle}>
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
        <div className="flex items-center space-x-2">
          <span className="text-[10px] font-mono text-white/80 font-medium tracking-wide">RECONSTRUCTION METRICS</span>
        </div>
        <span className="text-[9px] font-mono text-white/40">LIVE QA</span>
      </div>

      <div className="grid grid-cols-2 gap-3 my-auto">
        <div className="flex flex-col">
          <span className="text-[9.5px] font-mono text-white/45">Coverage</span>
          <div className="flex items-baseline space-x-1 mt-0.5">
            <span className="text-[20px] font-light text-white font-mono leading-none">
              {isCompleted ? '98.6' : isPlaying ? (60 + progressPercent * 0.38).toFixed(1) : '94.2'}%
            </span>
            <span className="text-[8px] font-mono text-white/40">PASSED</span>
          </div>
        </div>

        <div className="flex flex-col">
          <span className="text-[9.5px] font-mono text-white/45">Collinearity</span>
          <div className="flex items-baseline space-x-1 mt-0.5">
            <span className="text-[20px] font-light text-white font-mono leading-none">
              {metricAccuracy.toFixed(1)}%
            </span>
            <span className="text-[8px] font-mono text-white/40">VALID</span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-[9px] font-mono text-white/40 pt-1.5 border-t border-white/[0.06]">
        <span>Reproj Error: <strong className="text-white font-normal">0.18px</strong></span>
        <span>Tracks: <strong className="text-white font-normal">2,651</strong></span>
      </div>
    </div>
  );
};

export default OperationalEfficiency;
"""

(FE_DIR / "components" / "dashboard" / "OperationalEfficiency.tsx").write_text(op_code, encoding="utf-8")
print("[OK] OperationalEfficiency.tsx updated")

# ==============================================================================
# 4. ScheduleOffset.tsx - Tactical Metrology (Footprint, Volume, Elevation Span)
# ==============================================================================
schedule_code = """import React from 'react';
import { useMission } from '../../state/missionStore';

export const ScheduleOffset: React.FC = () => {
  const { mission } = useMission();

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  const center = mission?.location?.center;
  const latStr = center ? center.lat.toFixed(5) : '47.3700';
  const lngStr = center ? center.lng.toFixed(5) : '8.5440';

  return (
    <div className="select-none h-full overflow-hidden transition-all p-3.5 flex flex-col justify-between" style={glassStyle}>
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1">
        <span className="text-[10px] font-mono text-white/80 font-medium tracking-wide">SURVEY AREA METROLOGY</span>
        <span className="text-[8.5px] font-mono text-white/40">WGS84_ENU</span>
      </div>

      <div className="grid grid-cols-3 gap-2 my-auto">
        <div className="flex flex-col">
          <span className="text-[8.5px] font-mono text-white/45">Footprint Area</span>
          <span className="text-[16px] font-light text-white font-mono leading-tight mt-0.5">156.5 <span className="text-[9px] text-white/40">m²</span></span>
        </div>
        <div className="flex flex-col">
          <span className="text-[8.5px] font-mono text-white/45">Above-Ground Vol</span>
          <span className="text-[16px] font-light text-white font-mono leading-tight mt-0.5">936.0 <span className="text-[9px] text-white/40">m³</span></span>
        </div>
        <div className="flex flex-col">
          <span className="text-[8.5px] font-mono text-white/45">Height Span</span>
          <span className="text-[16px] font-light text-white font-mono leading-tight mt-0.5">22.3 <span className="text-[9px] text-white/40">m</span></span>
        </div>
      </div>

      <div className="flex items-center justify-between text-[8.5px] font-mono text-white/40 pt-1 border-t border-white/[0.06]">
        <span>Center Datum: <strong className="text-white font-normal">{latStr}° N, {lngStr}° E</strong></span>
        <span>Resolution: <strong className="text-white font-normal">4K UHD</strong></span>
      </div>
    </div>
  );
};

export default ScheduleOffset;
"""

(FE_DIR / "components" / "dashboard" / "ScheduleOffset.tsx").write_text(schedule_code, encoding="utf-8")
print("[OK] ScheduleOffset.tsx updated")

# ==============================================================================
# 5. DroneUnitCard.tsx - Tactical UAV specifications
# ==============================================================================
unit_code = """import React from 'react';
import { ArrowUpRight } from 'lucide-react';
import { useMission } from '../../state/missionStore';

export const DroneUnitCard: React.FC = () => {
  const { mission } = useMission();

  const cardStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 12px 32px rgba(0, 0, 0, 0.4)',
  };

  const vname = mission?.video?.filename || 'Flight_Orbit_4K.mp4';

  return (
    <div className="h-full select-none flex flex-col justify-between p-3.5 overflow-hidden transition-all hover:border-white/20" style={cardStyle}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-mono text-white font-medium">UAV-01 TACTICAL</span>
          <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_6px_#ffffff]" />
        </div>
        <ArrowUpRight className="w-3.5 h-3.5 text-white/40 hover:text-white cursor-pointer" />
      </div>

      <div className="text-[9px] font-mono text-white/50 truncate">
        File: {vname}
      </div>

      {/* Sensor Specs */}
      <div className="grid grid-cols-2 gap-2 my-auto bg-white/[0.03] p-2.5 rounded-xl border border-white/[0.06]">
        <div>
          <span className="text-[8.5px] font-mono text-white/40 block">Camera Gimbal</span>
          <span className="text-[11px] font-mono text-white">4K Exmor R</span>
        </div>
        <div>
          <span className="text-[8.5px] font-mono text-white/40 block">Capture Rate</span>
          <span className="text-[11px] font-mono text-white">30 fps</span>
        </div>
        <div>
          <span className="text-[8.5px] font-mono text-white/40 block">Telemetry Link</span>
          <span className="text-[11px] font-mono text-white">GNSS / IMU</span>
        </div>
        <div>
          <span className="text-[8.5px] font-mono text-white/40 block">Collinearity</span>
          <span className="text-[11px] font-mono text-white">Locked</span>
        </div>
      </div>

      <div className="flex items-center justify-between text-[8.5px] font-mono text-white/40 pt-1 border-t border-white/[0.06]">
        <span>Status: <strong className="text-white font-normal">Active Survey</strong></span>
        <span>Mode: <strong className="text-white font-normal">Single-Pass 3D</strong></span>
      </div>
    </div>
  );
};

export default DroneUnitCard;
"""

(FE_DIR / "components" / "dashboard" / "DroneUnitCard.tsx").write_text(unit_code, encoding="utf-8")
print("[OK] DroneUnitCard.tsx updated")

# ==============================================================================
# 6. MapView.tsx - Progressive Route Creation, Start on Map, and Twitter Blue Model Click
# ==============================================================================
mapview_code = """import React, { useEffect, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Box, Play } from 'lucide-react';
import { LayerManager } from '../layers/LayerManager';
import { DronePathLayer } from '../layers/drone/DronePathLayer';
import { DronePointsLayer } from '../layers/drone/DronePointsLayer';
import { ModelFootprintLayer } from '../layers/drone/ModelFootprintLayer';
import {
  MAPTILER_KEY,
  HAS_MAPTILER_KEY,
  MAPTILER_CONFIG,
  ARCGIS_CONFIG,
  IMAGERY_PROVIDER,
  INITIAL_CAMERA_CONFIG,
  VISUAL_CONFIG,
} from '../config/mapConfig';
import { useMission } from '../state/missionStore';
import { useReconstruction } from '../context/ReconstructionContext';

// Default survey corridor coordinates in case mission has no flight path yet
const DEFAULT_CORRIDOR_COORDS: [number, number][] = [
  [-122.419, 37.808],
  [-122.410, 37.805],
  [-122.400, 37.800],
  [-122.395, 37.792],
  [-122.390, 37.785],
  [-122.385, 37.778],
  [-122.388, 37.765],
  [-122.392, 37.750],
  [-122.395, 37.735],
  [-122.394, 37.722],
];

export const MapView: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<MapLibreMap | null>(null);
  const layerManagerRef = useRef<LayerManager | null>(null);
  const [isMapReady, setIsMapReady] = useState(false);
  const { mission, missionState, openViewer } = useMission();
  const { currentFrame, totalFrames, isCompleted, isPlaying, startPlayback } = useReconstruction();

  // 1. Initialize Map Canvas with Fixed Camera and Art-Directed Satellite Base
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
      center: INITIAL_CAMERA_CONFIG.center,
      zoom: INITIAL_CAMERA_CONFIG.zoom,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      minPitch: 0,
      minZoom: 10.8,
      maxZoom: 10.8,
      renderWorldCopies: false,
      fadeDuration: 0,
      dragPan: true,
      scrollZoom: false,
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
    map.on('idle', () => { (window as any).__gisMapIdle = true; });

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

  // 2. Progressive Telemetry & Route Synchronization
  // The route is NOT created instantly; it creates a route as it creates the model!
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

    // Do NOT draw a full planned route line ahead of time so route builds progressively!
    pathLayer?.updatePlannedPath([]);

    const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;

    // Initial Standby (ratio <= 0): Standing at start point, no route drawn yet
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

    // Complete (ratio >= 1): Full traversed route + Twitter Blue Footprint
    pathLayer?.updatePath({ type: 'LineString', coordinates: allCoords });
    const lastCoord = allCoords[allCoords.length - 1];
    pointsLayer?.updatePosition(lastCoord[0], lastCoord[1], 14);

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
    // Highlight in Twitter Blue (#1DA1F2)
    footprintLayer?.updateFootprint(footprint, modelId, true);
  }, [isMapReady, mission, missionState, currentFrame, totalFrames, isCompleted]);

  return (
    <div ref={mapContainerRef} className="map-viewport relative">
      {/* 1. START ON MAP BUTTON: If standing at start, user can press Start directly on the map */}
      {!isPlaying && currentFrame === 0 && (
        <div className="absolute top-[48%] left-[54%] -translate-x-1/2 -translate-y-1/2 z-40 pointer-events-auto">
          <button
            type="button"
            onClick={startPlayback}
            className="flex items-center space-x-2.5 px-4 py-2 rounded-xl bg-white text-black hover:bg-white/90 shadow-[0_0_24px_rgba(255,255,255,0.5)] border border-white/40 cursor-pointer font-medium text-[12px] transition-all hover:scale-105 active:scale-95"
          >
            <Play className="w-3.5 h-3.5 fill-black stroke-black translate-x-0.5" />
            <span>Start Reconnaissance</span>
          </button>
        </div>
      )}

      {/* 2. TWITTER BLUE MODEL READY CHIP: When done, click to show model in-place */}
      {isCompleted && (
        <div className="absolute top-[48%] left-[54%] -translate-x-1/2 -translate-y-1/2 z-40 pointer-events-auto">
          <button
            type="button"
            onClick={openViewer}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-[#1DA1F2] hover:bg-[#1a91da] text-white shadow-[0_0_24px_rgba(29,161,242,0.65)] border border-white/30 cursor-pointer font-medium text-[11.5px] backdrop-blur-md transition-all hover:scale-105 active:scale-95"
          >
            <Box className="w-4 h-4 text-white" />
            <span>3D Model Ready &bull; Click to Inspect</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default MapView;
"""

(FE_DIR / "components" / "MapView.tsx").write_text(mapview_code, encoding="utf-8")
print("[OK] MapView.tsx updated")

# ==============================================================================
# 7. ModelFootprintLayer.ts - Ensure Twitter Blue (#1DA1F2) styling and click
# ==============================================================================
footprint_code = """import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
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
    this.layerIds.forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
    });
    if (map.getSource(this.sourceId)) {
      map.removeSource(this.sourceId);
    }
    this.map = null;
  }
}

export default ModelFootprintLayer;
"""

(FE_DIR / "layers" / "drone" / "ModelFootprintLayer.ts").write_text(footprint_code, encoding="utf-8")
print("[OK] ModelFootprintLayer.ts updated")
print("All updates applied successfully!")
