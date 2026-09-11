const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. MapHeader.tsx
const mapHeaderCode = `import React, { useState } from 'react';
import { Crosshair, Layers, ChevronDown, Check, Radio } from 'lucide-react';
import { useMission } from '../../state/missionStore';
import { formatMissionTitle } from '../../utils/formatters';

export const MapHeader: React.FC = () => {
  const { mission, availableMissions, selectMission } = useMission();
  const [isMissionDropdownOpen, setIsMissionDropdownOpen] = useState(false);
  const [isLayerDropdownOpen, setIsLayerDropdownOpen] = useState(false);
  const [activeLayerName, setActiveLayerName] = useState('GLB 3D');

  const outputFormats = [
    { id: 'glb', name: 'GLB 3D', tag: 'Binary 3D Scene' },
    { id: 'pointcloud', name: 'Point Cloud', tag: 'Dense LAS / GeoTIFF' },
    { id: 'mesh', name: 'Textured Mesh', tag: 'Textured 3D Surface' },
    { id: 'obj', name: 'Wavefront OBJ', tag: 'OBJ + MTL Assets' },
  ];

  const rawTitle = mission?.name || (availableMissions.length > 0 ? availableMissions[0].name : 'Active Mission');
  const displayTitle = formatMissionTitle(rawTitle);

  const pillStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.75)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.07)',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
  };

  const menuStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.96)',
    backdropFilter: 'blur(32px) saturate(190%)',
    WebkitBackdropFilter: 'blur(32px) saturate(190%)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    boxShadow: '0 20px 48px rgba(0, 0, 0, 0.85)',
  };

  return (
    <div className="flex flex-col space-y-2 pointer-events-auto select-none">
      {/* Title & Brand Header */}
      <div className="flex items-center space-x-2.5">
        <div className="w-6 h-6 rounded-lg bg-white/[0.08] flex items-center justify-center">
          <Radio className="w-3.5 h-3.5 text-white/90" />
        </div>
        <div>
          <h1 className="text-[20px] font-extralight tracking-tight text-white leading-none">
            Single-Pass 3D Reconstruction
          </h1>
          <p className="text-[9.5px] font-mono text-white/40 tracking-wider mt-0.5 uppercase">
            NTRO Defense Geospatial Division • Tactical UAS
          </p>
        </div>
      </div>

      {/* Dropdown Selectors Row */}
      <div className="flex items-center space-x-2 pt-0.5">
        {/* Mission Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsMissionDropdownOpen(!isMissionDropdownOpen);
              setIsLayerDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white/90 hover:text-white active:scale-[0.98] transition-all cursor-pointer shadow-md"
            style={pillStyle}
            title={rawTitle}
          >
            <Crosshair className="w-3.5 h-3.5 text-white/80 shrink-0" />
            <span className="font-mono font-medium max-w-[180px] truncate">{displayTitle}</span>
            <ChevronDown className="w-3.5 h-3.5 text-white/40 shrink-0" />
          </button>

          {isMissionDropdownOpen && (
            <div
              className="absolute top-10 left-0 w-80 rounded-2xl p-2 z-50 flex flex-col space-y-1 max-h-72 overflow-y-auto"
              style={menuStyle}
            >
              <div className="px-2.5 py-1 text-[9px] font-mono uppercase tracking-wider text-white/40 border-b border-white/[0.08]">
                Registered Flight Missions
              </div>
              {availableMissions.length === 0 ? (
                <div className="p-3 text-[10.5px] text-white/40 text-center font-mono">
                  No missions registered
                </div>
              ) : (
                availableMissions.map((m) => {
                  const isSelected = mission?.id === m.id;
                  return (
                    <div
                      key={m.id}
                      onClick={() => {
                        selectMission(m.id);
                        setIsMissionDropdownOpen(false);
                      }}
                      className={\`p-2.5 rounded-xl cursor-pointer transition-all flex items-center justify-between \${
                        isSelected ? 'bg-white/[0.14]' : 'hover:bg-white/[0.06]'
                      }\`}
                    >
                      <div className="flex flex-col min-w-0 pr-2">
                        <span className="text-[11.5px] font-medium text-white/95 truncate">
                          {formatMissionTitle(m.name || m.id)}
                        </span>
                        <span className="text-[9px] font-mono text-white/50 mt-0.5">
                          {m.status?.toUpperCase() || 'STANDBY'}
                          {m.flight?.duration ? \` • \${m.flight.duration}s capture\` : ''}
                        </span>
                      </div>
                      {isSelected && <Check className="w-3.5 h-3.5 text-white shrink-0" />}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Output Layer Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsLayerDropdownOpen(!isLayerDropdownOpen);
              setIsMissionDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white/90 hover:text-white active:scale-[0.98] transition-all cursor-pointer shadow-md"
            style={pillStyle}
          >
            <Layers className="w-3.5 h-3.5 text-white/80 shrink-0" />
            <span className="font-mono font-medium">{activeLayerName}</span>
            <ChevronDown className="w-3.5 h-3.5 text-white/40 shrink-0" />
          </button>

          {isLayerDropdownOpen && (
            <div
              className="absolute top-10 left-0 w-60 rounded-2xl p-2 z-50 flex flex-col space-y-1"
              style={menuStyle}
            >
              <div className="px-2.5 py-1 text-[9px] font-mono uppercase tracking-wider text-white/40 border-b border-white/[0.08]">
                Deliverable Format
              </div>
              {outputFormats.map((l) => (
                <div
                  key={l.id}
                  onClick={() => {
                    setActiveLayerName(l.name);
                    setIsLayerDropdownOpen(false);
                  }}
                  className={\`p-2 rounded-xl cursor-pointer transition-all flex items-center justify-between \${
                    activeLayerName === l.name ? 'bg-white/[0.14]' : 'hover:bg-white/[0.06]'
                  }\`}
                >
                  <div className="flex flex-col">
                    <span className="text-[11px] font-medium text-white/95">{l.name}</span>
                    <span className="text-[8.5px] font-mono text-white/40">{l.tag}</span>
                  </div>
                  {activeLayerName === l.name && (
                    <Check className="w-3.5 h-3.5 text-white" />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MapHeader;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/MapHeader.tsx'), mapHeaderCode, 'utf8');
console.log('✓ Written MapHeader.tsx (no green, clean monochrome)');

// 2. FleetStatusCounters.tsx (Reconstruction Quality - NO INNER BOXES, NO INNER BORDERS, NO GREEN)
const fleetStatusCountersCode = `import React from 'react';
import { ShieldCheck } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const FleetStatusCounters: React.FC = () => {
  const { metricAccuracy, totalSeconds } = useReconstruction();
  const accuracyVal = metricAccuracy ? metricAccuracy.toFixed(1) : '99.4';
  const durationStr = \`\${Math.floor(totalSeconds / 60).toString().padStart(2, '0')}:\${(Math.floor(totalSeconds) % 60).toString().padStart(2, '0')}\`;
  const t1 = Math.round(totalSeconds * 0.25);
  const t2 = Math.round(totalSeconds * 0.5);
  const t3 = Math.round(totalSeconds * 0.75);
  const fmt = (s: number) => \`\${Math.floor(s / 60).toString().padStart(2, '0')}:\${(s % 60).toString().padStart(2, '0')}\`;

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.72)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 12px 36px rgba(0, 0, 0, 0.55)',
  };

  return (
    <div
      className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Header: Title + Neutral Validated Badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-white/80" />
          <span className="text-[9.5px] font-mono tracking-wider text-white/70 uppercase font-semibold">
            Reconstruction Quality
          </span>
        </div>
        <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-white/[0.08]">
          <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_6px_#fff]" />
          <span className="text-[8px] font-mono text-white/90 font-semibold tracking-wider">
            VALIDATED
          </span>
        </div>
      </div>

      {/* Large Primary Metric */}
      <div className="flex items-baseline space-x-2 my-1.5">
        <div className="flex items-baseline">
          <span className="text-[28px] font-light tracking-tight text-white leading-none font-mono tabular-nums">
            {accuracyVal}
          </span>
          <span className="text-[14px] font-light text-white/70 font-mono ml-0.5">%</span>
        </div>
        <span className="text-[9px] font-mono text-white/50">
          Overall Confidence
        </span>
      </div>

      {/* Clean Monochrome Area Curve (No Green!) */}
      <div className="relative w-full h-[32px] my-1">
        <svg className="w-full h-full overflow-visible" viewBox="0 0 290 32" preserveAspectRatio="none">
          <defs>
            <linearGradient id="qualityAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(255, 255, 255, 0.22)" />
              <stop offset="100%" stopColor="rgba(255, 255, 255, 0.0)" />
            </linearGradient>
          </defs>

          {/* Area Fill */}
          <path
            d="M 0 24 Q 70 24 140 14 T 290 5 L 290 32 L 0 32 Z"
            fill="url(#qualityAreaGrad)"
          />

          {/* Stroke Line */}
          <path
            d="M 0 24 Q 70 24 140 14 T 290 5"
            fill="none"
            stroke="rgba(255, 255, 255, 0.9)"
            strokeWidth="1.2"
            strokeLinecap="round"
          />

          {/* Nodes */}
          <circle cx="70" cy="22" r="1.4" fill="#FFFFFF" />
          <circle cx="140" cy="14" r="1.4" fill="#FFFFFF" />
          <circle cx="210" cy="9" r="1.4" fill="#FFFFFF" />
          <circle cx="290" cy="5" r="2.2" fill="#FFFFFF" />
        </svg>
      </div>

      {/* Timeline Labels */}
      <div className="flex justify-between text-[7.5px] font-mono text-white/40 px-0.5">
        <span>00:00</span>
        <span>{fmt(t1)}</span>
        <span>{fmt(t2)}</span>
        <span>{fmt(t3)}</span>
        <span>{durationStr}</span>
      </div>

      {/* Clean Metrics: NO INNER BOXES, NO INNER BORDERS */}
      <div className="flex justify-between items-baseline pt-2.5 border-t border-white/[0.06] font-mono">
        <div>
          <span className="text-white/40 text-[7.5px] uppercase tracking-wider block font-semibold">Pose</span>
          <span className="text-white text-[12px] font-medium mt-0.5 block">99.1%</span>
        </div>
        <div>
          <span className="text-white/40 text-[7.5px] uppercase tracking-wider block font-semibold">Depth</span>
          <span className="text-white text-[12px] font-medium mt-0.5 block">98.4%</span>
        </div>
        <div>
          <span className="text-white/40 text-[7.5px] uppercase tracking-wider block font-semibold">Coverage</span>
          <span className="text-white text-[12px] font-medium mt-0.5 block">97.6%</span>
        </div>
      </div>
    </div>
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), fleetStatusCountersCode, 'utf8');
console.log('✓ Written FleetStatusCounters.tsx (no inner boxes, no green)');

// 3. OperationalEfficiency.tsx (Flight Telemetry - NO INNER BOXES, NO GREEN)
const opEffCode = `import React from 'react';
import { Navigation } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const OperationalEfficiency: React.FC = () => {
  const { currentFrame, totalFrames, totalSeconds, altitudeM, rtkStatus } = useReconstruction();
  const progress = totalFrames > 0 ? Math.max(0, Math.min(1, currentFrame / totalFrames)) : 0;

  const durationStr = \`\${Math.floor(totalSeconds / 60).toString().padStart(2, '0')}:\${(Math.floor(totalSeconds) % 60).toString().padStart(2, '0')}\`;

  const droneX = 18 + progress * (254 - 18);
  const droneY = 24 - Math.sin(progress * Math.PI) * 10;

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.72)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 12px 36px rgba(0, 0, 0, 0.55)',
  };

  return (
    <div
      className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-1.5">
          <Navigation className="w-3.5 h-3.5 text-white/80" />
          <span className="text-[9.5px] font-mono tracking-wider text-white/70 uppercase font-semibold">
            Flight Telemetry
          </span>
        </div>
        <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-white/[0.08]">
          <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_6px_#fff]" />
          <span className="text-[8px] font-mono text-white/90 font-semibold tracking-wider">
            {rtkStatus.includes('float') ? 'GPS RTK FLOAT' : 'GPS RTK FIXED'}
          </span>
        </div>
      </div>

      {/* Primary Counter */}
      <div className="flex items-baseline space-x-2 my-1.5">
        <span className="text-[28px] font-light tracking-tight text-white leading-none font-mono tabular-nums">
          {durationStr}
        </span>
        <span className="text-[9px] font-mono text-white/50">
          Capture Duration
        </span>
      </div>

      {/* Trajectory Arc Diagram (Clean White/Silver) */}
      <div className="relative w-full h-[32px] my-1">
        <svg className="w-full h-full overflow-visible" viewBox="0 0 272 32" preserveAspectRatio="none">
          <path
            d="M 18 24 Q 136 4 254 24"
            fill="none"
            stroke="rgba(255,255,255,0.2)"
            strokeWidth="1.2"
            strokeDasharray="4 3"
          />
          <circle cx="18" cy="24" r="2" fill="rgba(255,255,255,0.4)" />
          <circle cx="77" cy="16" r="1.5" fill="rgba(255,255,255,0.25)" />
          <circle cx="136" cy="14" r="1.5" fill="rgba(255,255,255,0.25)" />
          <circle cx="195" cy="16" r="1.5" fill="rgba(255,255,255,0.25)" />
          <circle cx="254" cy="24" r="2" fill="rgba(255,255,255,0.4)" />

          {/* Active UAV Icon in Pure White */}
          <g transform={\`translate(\${droneX}, \${droneY})\`}>
            <circle cx="0" cy="0" r="4.5" fill="rgba(255, 255, 255, 0.2)" />
            <circle cx="0" cy="0" r="2" fill="#FFFFFF" />
            <path
              d="M -5 -3 L 5 -3 M -5 3 L 5 3 M 0 -4 L 0 4"
              stroke="#FFFFFF"
              strokeWidth="0.8"
              opacity="0.9"
            />
          </g>
        </svg>
      </div>

      {/* Clean Telemetry Metrics: NO INNER BOXES, NO INNER BORDERS */}
      <div className="flex justify-between items-baseline pt-2.5 border-t border-white/[0.06] font-mono text-[8.5px]">
        <div>
          <span className="text-white/40 text-[7.5px] uppercase tracking-wider block font-semibold">Video</span>
          <span className="text-white text-[11px] font-medium mt-0.5 block whitespace-nowrap">4K 30fps</span>
        </div>
        <div>
          <span className="text-white/40 text-[7.5px] uppercase tracking-wider block font-semibold">Altitude</span>
          <span className="text-white text-[11px] font-medium mt-0.5 block">{altitudeM || 14}m</span>
        </div>
        <div>
          <span className="text-white/40 text-[7.5px] uppercase tracking-wider block font-semibold">Points</span>
          <span className="text-white text-[11px] font-medium mt-0.5 block">1.46M</span>
        </div>
        <div>
          <span className="text-white/40 text-[7.5px] uppercase tracking-wider block font-semibold">Heading</span>
          <span className="text-white text-[11px] font-medium mt-0.5 block">048°</span>
        </div>
      </div>
    </div>
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), opEffCode, 'utf8');
console.log('✓ Written OperationalEfficiency.tsx (no inner boxes, no green)');

// 4. DroneUnitCard.tsx (Unified panel, NO NESTED BOXES, NO INNER BORDERS, NO GREEN)
const droneUnitCode = `import React from 'react';
import { Video, Crosshair, Box, Cpu } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';
import { useMission } from '../../state/missionStore';
import { formatVideoFilename } from '../../utils/formatters';

export const DroneUnitCard: React.FC = () => {
  const { totalFrames, altitudeM } = useReconstruction();
  const { mission, missionState } = useMission();

  const isReady = mission?.status === 'ready' || missionState === 'MODEL_READY';
  const isReconstructing = missionState === 'RECONSTRUCTING';
  const isExtracting = missionState === 'EXTRACTING_GPS';

  const rawFilename = mission?.video?.filename || 'flight_survey_01.mp4';
  const displayFilename = formatVideoFilename(rawFilename);

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.72)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 12px 36px rgba(0, 0, 0, 0.55)',
  };

  return (
    <div
      className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* 2x2 Clean Quadrant Layout - ZERO nested boxes, ZERO nested borders */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        {/* QUADRANT 1: VIDEO INGEST */}
        <div className="flex flex-col justify-between min-h-[96px]">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1">
              <Video className="w-3 h-3 text-white/80" />
              <span className="text-[9px] font-mono tracking-wider text-white/70 uppercase font-semibold">
                Video Ingest
              </span>
            </div>
            <span className="text-[7.5px] font-mono text-white/80 bg-white/[0.08] px-1.5 py-0.2 rounded-full">
              INGESTED
            </span>
          </div>

          <div className="text-[8.5px] font-mono text-white/90 truncate my-1">
            {displayFilename}
          </div>

          {/* Simple Clean Geometry */}
          <div className="w-full h-[28px] flex items-center justify-center my-0.5">
            <svg className="w-full h-full" viewBox="0 0 130 28">
              <line x1="8" y1="14" x2="32" y2="14" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" strokeDasharray="2 2" />
              <circle cx="8" cy="14" r="2" fill="#FFFFFF" />
              <rect x="32" y="6" width="16" height="16" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" />
              <rect x="56" y="4" width="20" height="20" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
              <rect x="84" y="2" width="24" height="24" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.7)" strokeWidth="1" rx="1.5" />
              <circle cx="96" cy="14" r="1.5" fill="#FFFFFF" />
            </svg>
          </div>

          <div className="flex items-center justify-between text-[7.5px] font-mono text-white/40 pt-1 border-t border-white/[0.06]">
            <span>FRAMES <strong className="text-white font-medium">{totalFrames || 900}</strong></span>
            <span>RES <strong className="text-white font-medium">4K UHD</strong></span>
          </div>
        </div>

        {/* QUADRANT 2: CAMERA POSE & GPS */}
        <div className="flex flex-col justify-between min-h-[96px]">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1">
              <Crosshair className="w-3 h-3 text-white/80" />
              <span className="text-[9px] font-mono tracking-wider text-white/70 uppercase font-semibold">
                Pose / GPS
              </span>
            </div>
            <span className="text-[7.5px] font-mono text-white/80 bg-white/[0.08] px-1.5 py-0.2 rounded-full">
              FIXED
            </span>
          </div>

          <div className="text-[8.5px] font-mono text-white/90 truncate my-1">
            WGS84 • RTK-FIXED
          </div>

          {/* Simple Trajectory */}
          <div className="w-full h-[28px] flex items-center justify-center my-0.5">
            <svg className="w-full h-full" viewBox="0 0 130 28">
              <path
                d="M 10 20 C 35 20, 45 8, 80 12 S 110 16, 122 8"
                fill="none"
                stroke="rgba(255, 255, 255, 0.35)"
                strokeWidth="1.0"
              />
              <circle cx="10" cy="20" r="1.4" fill="rgba(255,255,255,0.4)" />
              <circle cx="45" cy="8" r="1.4" fill="rgba(255,255,255,0.4)" />
              <circle cx="122" cy="8" r="1.4" fill="rgba(255,255,255,0.4)" />
              <g transform="translate(80, 12)">
                <circle cx="0" cy="0" r="5" fill="rgba(255, 255, 255, 0.15)" stroke="#FFFFFF" strokeWidth="0.8" />
                <circle cx="0" cy="0" r="1.8" fill="#FFFFFF" />
              </g>
            </svg>
          </div>

          <div className="flex items-center justify-between text-[7.5px] font-mono text-white/40 pt-1 border-t border-white/[0.06]">
            <span>WAYPOINTS <strong className="text-white font-medium">30</strong></span>
            <span>ALT <strong className="text-white font-medium">{altitudeM || 14}m</strong></span>
          </div>
        </div>

        {/* QUADRANT 3: SFM SOLVER */}
        <div className="flex flex-col justify-between min-h-[96px] pt-2 border-t border-white/[0.06]">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1">
              <Box className="w-3 h-3 text-white/80" />
              <span className="text-[9px] font-mono tracking-wider text-white/70 uppercase font-semibold">
                SfM Solver
              </span>
            </div>
            <span className="text-[7.5px] font-mono text-white/80 bg-white/[0.08] px-1.5 py-0.2 rounded-full">
              SOLVED
            </span>
          </div>

          {/* Wireframe Mesh in Pure White/Silver */}
          <div className="w-full h-[28px] flex items-center justify-center my-0.5">
            <svg className="w-full h-full" viewBox="0 0 130 28">
              <path d="M 4 22 Q 35 14 68 18 T 126 20" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.7" />
              <g transform="translate(35, 4)">
                <polygon points="0,14 12,8 24,12 12,18" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.3)" strokeWidth="0.6" />
                <polygon points="0,4 12,0 24,4 12,8" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.8)" strokeWidth="0.8" />
                <line x1="0" y1="14" x2="0" y2="4" stroke="rgba(255,255,255,0.5)" strokeWidth="0.7" />
                <line x1="12" y1="18" x2="12" y2="8" stroke="rgba(255,255,255,0.6)" strokeWidth="0.7" />
                <line x1="24" y1="12" x2="24" y2="4" stroke="rgba(255,255,255,0.5)" strokeWidth="0.7" />
              </g>
              <g transform="translate(75, 2)">
                <polygon points="0,16 10,10 20,14 10,20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.25)" strokeWidth="0.6" />
                <polygon points="0,5 10,0 20,4 10,9" fill="rgba(255,255,255,0.1)" stroke="rgba(255,255,255,0.6)" strokeWidth="0.7" />
                <line x1="0" y1="16" x2="0" y2="5" stroke="rgba(255,255,255,0.4)" strokeWidth="0.7" />
                <line x1="10" y1="20" x2="10" y2="9" stroke="rgba(255,255,255,0.5)" strokeWidth="0.7" />
                <line x1="20" y1="14" x2="20" y2="4" stroke="rgba(255,255,255,0.4)" strokeWidth="0.7" />
              </g>
            </svg>
          </div>

          <div className="grid grid-cols-2 gap-x-2 text-[7.5px] font-mono text-white/40 pt-1 border-t border-white/[0.06]">
            <span>PTS <strong className="text-white font-medium">42.8K</strong></span>
            <span>MATCH <strong className="text-white font-medium">180/180</strong></span>
            <span>ERR <strong className="text-white font-medium">0.42px</strong></span>
            <span>GSD <strong className="text-white font-medium">2.4cm</strong></span>
          </div>
        </div>

        {/* QUADRANT 4: RECONSTRUCTION PIPELINE */}
        <div className="flex flex-col justify-between min-h-[96px] pt-2 border-t border-white/[0.06]">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1">
              <Cpu className="w-3 h-3 text-white/80" />
              <span className="text-[9px] font-mono tracking-wider text-white/70 uppercase font-semibold">
                Pipeline
              </span>
            </div>
            <span className="text-[7.5px] font-mono text-white/80 bg-white/[0.08] px-1.5 py-0.2 rounded-full">
              {isReady ? '100% READY' : isReconstructing ? 'PROCESSING' : 'STANDBY'}
            </span>
          </div>

          {/* 5 Clean Stages without boxes */}
          <div className="flex flex-col justify-center space-y-0.5 my-1">
            {[
              { name: 'VIDEO', status: 'COMPLETE', active: true },
              { name: 'POSE', status: isExtracting ? 'SOLVING' : 'COMPLETE', active: true },
              { name: 'DEPTH', status: 'COMPLETE', active: true },
              { name: 'MESH', status: isReady ? 'COMPLETE' : isReconstructing ? 'PROCESSING' : 'STANDBY', active: isReady || isReconstructing },
              { name: 'TEXTURE', status: isReady ? 'COMPLETE' : 'STANDBY', active: isReady },
            ].map((stage) => (
              <div key={stage.name} className="flex items-center justify-between text-[7px] font-mono">
                <div className="flex items-center space-x-1.5">
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{
                      backgroundColor: stage.active ? '#FFFFFF' : 'rgba(255,255,255,0.2)',
                      boxShadow: stage.active ? '0 0 4px rgba(255,255,255,0.8)' : 'none',
                    }}
                  />
                  <span className={stage.active ? 'text-white/90' : 'text-white/40'}>
                    {stage.name}
                  </span>
                </div>
                <span className={stage.active ? 'text-white/90 font-medium' : 'text-white/30'}>
                  {stage.status}
                </span>
              </div>
            ))}
          </div>

          {/* Subtle Progress Bar */}
          <div className="w-full bg-white/[0.08] h-1 rounded-full overflow-hidden mt-0.5">
            <div
              className="bg-white h-full rounded-full transition-all duration-500 shadow-[0_0_6px_#fff]"
              style={{ width: isReady ? '100%' : isReconstructing ? '75%' : '30%' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), droneUnitCode, 'utf8');
console.log('✓ Written DroneUnitCard.tsx (unified panel, no inner boxes, no green)');

// 5. ScheduleOffset.tsx (Metric Accuracy - NO INNER BOXES, NO INNER BORDERS, NO GREEN)
const scheduleOffsetCode = `import React from 'react';
import { Target } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const ScheduleOffset: React.FC = () => {
  const { altitudeM, rtkStatus } = useReconstruction();

  const parameters = [
    { name: 'GPS ACCURACY', value: '1.42 m', status: 'VALID' },
    { name: 'ALTITUDE (AGL)', value: \`\${altitudeM || '14.0'} m\`, status: 'VALID' },
    { name: 'CAMERA POSE', value: '0.18°', status: 'STABLE' },
    { name: 'GSD RESOLUTION', value: '2.4 cm/px', status: 'VALID' },
    { name: 'RTK POSITIONING', value: rtkStatus.includes('FIX') ? 'FIXED' : 'FIXED', status: 'VALID' },
  ];

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.72)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 12px 36px rgba(0, 0, 0, 0.55)',
  };

  return (
    <div
      className="rounded-2xl p-3.5 flex flex-col justify-between select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Header: Title + Neutral Calibrated Badge */}
      <div>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5">
            <Target className="w-3.5 h-3.5 text-white/80" />
            <span className="text-[9.5px] font-mono tracking-wider text-white/70 uppercase font-semibold">
              Metric Accuracy
            </span>
          </div>
          <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-white/[0.08]">
            <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_6px_#fff]" />
            <span className="text-[8px] font-mono text-white/90 font-semibold tracking-wider">
              CALIBRATED
            </span>
          </div>
        </div>

        <div className="mt-1 flex items-baseline space-x-2">
          <div className="flex items-baseline space-x-1">
            <span className="text-[24px] font-light tracking-tight text-white leading-none font-mono tabular-nums">
              ± 1.42
            </span>
            <span className="text-[12px] font-light text-white/70 font-mono">cm</span>
          </div>
          <span className="text-[9px] text-white/45 font-mono">
            Average Spatial Variance
          </span>
        </div>
      </div>

      {/* NO INNER BOX! NO INNER BORDER! Clean Table Flow */}
      <div className="my-1 space-y-0.5">
        <div className="grid grid-cols-3 gap-2 text-[7.5px] font-mono text-white/40 pb-0.5 border-b border-white/[0.06] uppercase tracking-wider">
          <div>Parameter</div>
          <div className="text-center">Value</div>
          <div className="text-right">Status</div>
        </div>

        <div className="space-y-0.5 pt-0.5">
          {parameters.map((p) => (
            <div
              key={p.name}
              className="grid grid-cols-3 gap-2 items-center text-[8px] font-mono py-0.5"
            >
              <div className="text-white/60 truncate">{p.name}</div>
              <div className="text-center text-white font-medium tabular-nums">{p.value}</div>
              <div className="flex items-center justify-end space-x-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-white/70 inline-block shrink-0" />
                <span className="text-white/80 font-medium text-[7.5px]">{p.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-white/[0.06] text-[8px] font-mono">
        <div className="flex items-center space-x-1.5">
          <span className="text-white/40">HORIZONTAL ERROR:</span>
          <span className="text-white font-medium">± 1.2 cm</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="text-white/40">VERTICAL ERROR:</span>
          <span className="text-white font-medium">± 2.1 cm</span>
        </div>
      </div>
    </div>
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), scheduleOffsetCode, 'utf8');
console.log('✓ Written ScheduleOffset.tsx (no inner box, no green)');

// 6. PassengerVolume.tsx (Reconstructed Model - NO INNER BOXES, NO GREEN)
const passengerVolumeCode = `import React, { useMemo } from 'react';
import { Layers3 } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';
import { useMission } from '../../state/missionStore';

interface DensitySample {
  index: number;
  height: number;
}

export const PassengerVolume: React.FC = () => {
  const { currentFrame, totalFrames, totalSeconds, reconstructedPointsStr } = useReconstruction();
  const { mission } = useMission();

  const NUM_BARS = 120;
  const SVG_WIDTH = 1000;
  const SVG_HEIGHT = 42;
  const BAR_WIDTH = 4.2;
  const TOTAL_PITCH = (SVG_WIDTH - BAR_WIDTH) / (NUM_BARS - 1);

  const samples: DensitySample[] = useMemo(() => {
    return Array.from({ length: NUM_BARS }).map((_, i) => {
      const pos = i / (NUM_BARS - 1);
      const baseSignal =
        38 +
        Math.sin(pos * Math.PI * 3.2) * 30 +
        Math.cos(pos * Math.PI * 6.5) * 16 +
        ((i % 4) * 2.5);
      const height = Math.max(18, Math.min(92, Math.round(baseSignal)));
      return { index: i, height };
    });
  }, [NUM_BARS]);

  const currentRatio = totalFrames > 0 ? Math.max(0, Math.min(1, currentFrame / totalFrames)) : 0.85;
  const playheadSvgX = currentRatio * SVG_WIDTH;

  const durationStr = \`\${Math.floor(totalSeconds / 60).toString().padStart(2, '0')}:\${(Math.floor(totalSeconds) % 60).toString().padStart(2, '0')}\`;
  const t1 = Math.round(totalSeconds * 0.2);
  const t2 = Math.round(totalSeconds * 0.4);
  const t3 = Math.round(totalSeconds * 0.6);
  const t4 = Math.round(totalSeconds * 0.8);
  const fmt = (s: number) => \`\${Math.floor(s / 60).toString().padStart(2, '0')}:\${(s % 60).toString().padStart(2, '0')}\`;

  const eventCheckpoints = [
    { label: 'INGESTION', time: '00:00' },
    { label: 'KEYFRAMES', time: fmt(t1) },
    { label: 'SFM POSE', time: fmt(t2) },
    { label: 'DEPTH MAPS', time: fmt(t3) },
    { label: '3D MESH', time: fmt(t4) },
    { label: 'DELIVERABLE', time: durationStr },
  ];

  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.72)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 12px 36px rgba(0, 0, 0, 0.55)',
  };

  return (
    <div
      className="rounded-2xl p-3.5 flex flex-col justify-between select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Header: Title + Big Points Number + 4 Clean Metrics (NO BOXES, NO BORDERS) */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center space-x-1.5">
            <Layers3 className="w-3.5 h-3.5 text-white/80" />
            <span className="text-[9.5px] font-mono tracking-wider text-white/70 uppercase font-semibold">
              Reconstructed Model
            </span>
          </div>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-[26px] font-light tracking-tight text-white leading-none font-mono tabular-nums">
              {reconstructedPointsStr || '1.46M'}
            </span>
            <span className="text-[9px] text-white/50 font-mono uppercase font-medium">
              Dense Points
            </span>
          </div>
        </div>

        {/* 4 Clean Metric Columns - NO INNER BOXES */}
        <div className="flex items-baseline space-x-5 text-[8.5px] font-mono pt-1">
          <div>
            <span className="text-white/40 text-[7.5px] uppercase font-semibold block">Cloud</span>
            <span className="text-white font-medium text-[11px] mt-0.5 block">{reconstructedPointsStr || '1.46M'}</span>
          </div>
          <div>
            <span className="text-white/40 text-[7.5px] uppercase font-semibold block">Mesh</span>
            <span className="text-white font-medium text-[11px] mt-0.5 block">
              {mission?.reconstruction?.modelUrl ? '1.18M TRIS' : 'SURFACE'}
            </span>
          </div>
          <div>
            <span className="text-white/40 text-[7.5px] uppercase font-semibold block">Texture</span>
            <span className="text-white font-medium text-[11px] mt-0.5 block">4K PBR</span>
          </div>
          <div>
            <span className="text-white/40 text-[7.5px] uppercase font-semibold block">Confidence</span>
            <span className="text-white font-medium text-[11px] mt-0.5 block tabular-nums">99.4%</span>
          </div>
        </div>
      </div>

      {/* Waveform Spectrum - NO INNER BOX, NO INNER BORDER, Pure Monochrome */}
      <div className="relative w-full h-[34px] my-1 flex items-center">
        <svg
          viewBox={\`0 0 \${SVG_WIDTH} \${SVG_HEIGHT}\`}
          preserveAspectRatio="none"
          className="w-full h-full overflow-visible"
        >
          <defs>
            <linearGradient id="spectrumBarGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FFFFFF" />
              <stop offset="100%" stopColor="rgba(255, 255, 255, 0.25)" />
            </linearGradient>
          </defs>

          {samples.map((sample) => {
            const x = sample.index * TOTAL_PITCH;
            const barHeight = (sample.height / 100) * (SVG_HEIGHT - 6);
            const y = SVG_HEIGHT - barHeight;
            const isPast = x <= playheadSvgX;

            return (
              <rect
                key={sample.index}
                x={x}
                y={y}
                width={BAR_WIDTH}
                height={barHeight}
                rx={BAR_WIDTH / 2}
                ry={BAR_WIDTH / 2}
                fill={isPast ? 'url(#spectrumBarGrad)' : 'rgba(255, 255, 255, 0.15)'}
                opacity={isPast ? 0.95 : 0.4}
              />
            );
          })}

          {/* Precision Playhead Line & Indicator */}
          <line
            x1={playheadSvgX}
            y1={0}
            x2={playheadSvgX}
            y2={SVG_HEIGHT}
            stroke="#FFFFFF"
            strokeWidth="1.5"
            filter="drop-shadow(0 0 4px rgba(255,255,255,0.8))"
          />
          <circle cx={playheadSvgX} cy="3" r="2.5" fill="#FFFFFF" />
        </svg>
      </div>

      {/* Reconstruction Timeline Row (6 checkpoints) in Pure White/Silver */}
      <div className="flex justify-between items-center text-[7.5px] font-mono border-t border-white/[0.06] pt-1.5 px-0.5">
        {eventCheckpoints.map((ev, idx) => (
          <div key={idx} className="flex items-center space-x-1.5 text-white/50">
            <span className="w-1.5 h-1.5 rounded-full inline-block shrink-0 bg-white/70 shadow-[0_0_4px_rgba(255,255,255,0.6)]" />
            <span className="font-medium text-white/80">
              {ev.time}
            </span>
            <span className="text-white/40">
              {ev.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), passengerVolumeCode, 'utf8');
console.log('✓ Written PassengerVolume.tsx (no inner boxes, no green)');

// 7. VideoUploadButton.tsx (Matching user reference media_1788705318865.png: NO GREEN, clean capsule)
const videoUploadButtonCode = `import React, { useRef } from 'react';
import { UploadCloud, Loader2, CheckCircle2, Box } from 'lucide-react';
import { useMission } from '../../state/missionStore';

export const VideoUploadButton: React.FC = () => {
  const { mission, missionState, uploadProgress, uploadVideo, openViewer } = useMission();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadVideo(file);
      e.target.value = '';
    }
  };

  const isUploading = missionState === 'UPLOADING';
  const isExtracting = missionState === 'EXTRACTING_GPS';
  const isReconstructing = missionState === 'RECONSTRUCTING';
  const isModelReady = missionState === 'MODEL_READY';

  const buttonStyle: React.CSSProperties = {
    background: 'rgba(8, 12, 18, 0.75)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="select-none pointer-events-auto flex items-center space-x-2 -webkit-app-region-no-drag">
      <input
        ref={fileInputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/x-matroska"
        className="hidden"
        onChange={onFileChange}
      />

      {isModelReady && (
        <button
          type="button"
          onClick={openViewer}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-full text-[11.5px] text-white hover:brightness-125 active:scale-[0.98] transition-all cursor-pointer font-mono font-medium shadow-md"
          style={buttonStyle}
          title="Inspect 3D Reconstructed Model"
        >
          <Box className="w-3.5 h-3.5 text-white/90" />
          <span>3D Model Ready</span>
        </button>
      )}

      <button
        type="button"
        onClick={() => {
          if (!isUploading && !isReconstructing) {
            fileInputRef.current?.click();
          }
        }}
        disabled={isUploading || isReconstructing}
        className="flex items-center space-x-2 px-3.5 py-1.5 rounded-full text-[11.5px] text-white hover:brightness-125 active:scale-[0.98] transition-all cursor-pointer disabled:cursor-not-allowed group shadow-md"
        style={buttonStyle}
        title={
          mission?.video?.filename
            ? \`Active Video: \${mission.video.filename}\`
            : 'Upload Drone Video Stream (MP4/MOV)'
        }
      >
        {isUploading ? (
          <>
            <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
            <span className="font-medium font-mono text-[11px]">
              Uploading {uploadProgress ? \`\${uploadProgress.percent}%\` : '...'}
            </span>
          </>
        ) : isExtracting ? (
          <>
            <Loader2 className="w-3.5 h-3.5 text-white/70 animate-spin" />
            <span className="font-medium font-mono text-[11px]">Extracting GPS...</span>
          </>
        ) : isReconstructing ? (
          <>
            <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
            <span className="font-medium font-mono text-[11px]">
              Processing {mission?.processing?.progress ? \`\${mission.processing.progress}%\` : '...'}
            </span>
          </>
        ) : isModelReady ? (
          <>
            <CheckCircle2 className="w-3.5 h-3.5 text-white/90" />
            <span className="font-medium">Upload New</span>
          </>
        ) : (
          <>
            <UploadCloud className="w-3.5 h-3.5 text-white/90" />
            <span className="font-medium">Upload Video</span>
          </>
        )}
      </button>
    </div>
  );
};

export default VideoUploadButton;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/VideoUploadButton.tsx'), videoUploadButtonCode, 'utf8');
console.log('✓ Written VideoUploadButton.tsx (capsule style matching user upload reference, no green)');

// 8. DashboardPanels.tsx (Zero Green, Crisp Monochrome Reticle, Native Apple Traffic Lights)
const dashboardPanelsCode = `import React from 'react';
import { FleetStatusCounters } from './FleetStatusCounters';
import { OperationalEfficiency } from './OperationalEfficiency';
import { DroneUnitCard } from './DroneUnitCard';
import { MapHeader } from './MapHeader';
import { VideoUploadButton } from './VideoUploadButton';
import { ScheduleOffset } from './ScheduleOffset';
import { PassengerVolume } from './PassengerVolume';
import { WindowControls } from '../common/WindowControls';
import { useReconstruction } from '../../context/ReconstructionContext';

export const DashboardPanels: React.FC = () => {
  const { altitudeM } = useReconstruction();

  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 flex flex-col justify-between p-4">
      {/* 1. CINEMATIC OPTICAL DEPTH-OF-FIELD */}
      <div
        className="absolute inset-0 w-full h-full pointer-events-none z-10"
        style={{
          backdropFilter: 'blur(3px)',
          WebkitBackdropFilter: 'blur(3px)',
          maskImage:
            'radial-gradient(circle 420px at 50% 50%, transparent 0%, transparent 40%, black 90%)',
          WebkitMaskImage:
            'radial-gradient(circle 420px at 50% 50%, transparent 0%, transparent 40%, black 90%)',
        }}
      />
      <div
        className="absolute inset-0 w-full h-full pointer-events-none z-10"
        style={{
          background:
            'radial-gradient(circle 950px at 50% 50%, rgba(2, 4, 8, 0.0) 30%, rgba(2, 4, 8, 0.35) 65%, rgba(1, 2, 4, 0.82) 100%)',
        }}
      />

      {/* 2. AEROSPACE TACTICAL HUD RETICLE (Pure White & Silver Hairlines, NO GREEN) */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-20 flex flex-col items-center justify-center">
        <svg
          width="130"
          height="130"
          viewBox="0 0 130 130"
          fill="none"
          className="overflow-visible"
        >
          {/* Hairline Reticle Ring */}
          <circle
            cx="65"
            cy="65"
            r="52"
            stroke="rgba(255, 255, 255, 0.22)"
            strokeWidth="0.8"
            strokeDasharray="5 4"
          />

          {/* 4 Cardinal Crosshairs in Crisp White */}
          <line x1="65" y1="6" x2="65" y2="16" stroke="rgba(255, 255, 255, 0.7)" strokeWidth="1.2" />
          <line x1="65" y1="114" x2="65" y2="124" stroke="rgba(255, 255, 255, 0.7)" strokeWidth="1.2" />
          <line x1="6" y1="65" x2="16" y2="65" stroke="rgba(255, 255, 255, 0.7)" strokeWidth="1.2" />
          <line x1="114" y1="65" x2="124" y2="65" stroke="rgba(255, 255, 255, 0.7)" strokeWidth="1.2" />

          {/* Precision Corner Brackets */}
          <path d="M 28 40 L 28 28 L 40 28" stroke="rgba(255, 255, 255, 0.4)" strokeWidth="0.8" fill="none" />
          <path d="M 102 40 L 102 28 L 90 28" stroke="rgba(255, 255, 255, 0.4)" strokeWidth="0.8" fill="none" />
          <path d="M 28 90 L 28 102 L 40 102" stroke="rgba(255, 255, 255, 0.4)" strokeWidth="0.8" fill="none" />
          <path d="M 102 90 L 102 102 L 90 102" stroke="rgba(255, 255, 255, 0.4)" strokeWidth="0.8" fill="none" />

          {/* Center Drone Marker in Pure White */}
          <g transform="translate(65, 65)">
            <circle
              cx="0"
              cy="0"
              r="14"
              fill="rgba(255, 255, 255, 0.08)"
              stroke="rgba(255, 255, 255, 0.6)"
              strokeWidth="1"
            />
            <path
              d="M 0 -8 L 6 7 L 0 4 L -6 7 Z"
              fill="#FFFFFF"
              filter="drop-shadow(0 1px 3px rgba(0,0,0,0.8))"
            />
            <circle cx="0" cy="0" r="1.5" fill="#FFFFFF" />
          </g>
        </svg>

        {/* Micro-Telemetry Badge (Monochrome) */}
        <div
          className="mt-1.5 px-3 py-0.5 rounded-full flex items-center space-x-2 text-[8.5px] font-mono text-white/80"
          style={{
            background: 'rgba(8, 12, 16, 0.75)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            boxShadow: '0 4px 14px rgba(0, 0, 0, 0.5)',
          }}
        >
          <span className="text-white font-medium">UAV-01</span>
          <span className="text-white/30">|</span>
          <span>37.7749° N</span>
          <span>122.4194° W</span>
          <span className="text-white/30">|</span>
          <span>ALT {altitudeM || '14.0'}m AGL</span>
        </div>
      </div>

      {/* 3. FLOATING TOP COMMAND REGION */}
      <div className="w-full flex items-start justify-between z-40 pointer-events-none mb-2">
        {/* Top-Left: Floating Title & Dropdowns */}
        <div className="pointer-events-auto">
          <MapHeader />
        </div>

        {/* Top-Right: Telemetry Status + Upload Video + Apple Window Controls */}
        <div className="pointer-events-auto flex items-center space-x-2.5">
          {/* RTK Telemetry Badge (Clean White/Silver, NO GREEN) */}
          <div
            className="hidden sm:flex items-center space-x-2 px-3.5 py-1.5 rounded-full text-[11px] font-mono text-white/90 shadow-md"
            style={{
              background: 'rgba(8, 12, 18, 0.75)',
              backdropFilter: 'blur(24px) saturate(180%)',
              WebkitBackdropFilter: 'blur(24px) saturate(180%)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
            }}
          >
            <span className="w-2 h-2 rounded-full bg-white shadow-[0_0_8px_#fff]" />
            <span className="font-semibold tracking-wide">GPS RTK LOCKED</span>
          </div>

          {/* Video Upload & 3D Model Inspection Button */}
          <VideoUploadButton />

          {/* Apple macOS Traffic Light Window Controls */}
          <div
            className="rounded-full px-2.5 py-1.5 flex items-center shadow-md ml-1"
            style={{
              background: 'rgba(8, 12, 18, 0.75)',
              backdropFilter: 'blur(24px) saturate(180%)',
              WebkitBackdropFilter: 'blur(24px) saturate(180%)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
            }}
          >
            <WindowControls />
          </div>
        </div>
      </div>

      {/* 4. MAIN SPATIAL WORKSPACE (Panels) */}
      <div className="relative z-30 flex-1 min-h-0 flex gap-3 overflow-hidden pointer-events-none">
        {/* Left Column Stack */}
        <aside className="w-[305px] lg:w-[315px] xl:w-[325px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto overflow-y-auto">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <DroneUnitCard />
        </aside>

        {/* Center & Right Area */}
        <section className="flex-1 h-full min-h-0 flex flex-col justify-end overflow-hidden relative">
          {/* Lower Stage: Dual-Panel Analytics Cards */}
          <div className="h-[180px] lg:h-[186px] xl:h-[192px] shrink-0 w-full pt-1 pointer-events-auto grid grid-cols-12 gap-3">
            <div className="col-span-5 h-full">
              <ScheduleOffset />
            </div>
            <div className="col-span-7 h-full">
              <PassengerVolume />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default DashboardPanels;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx'), dashboardPanelsCode, 'utf8');
console.log('✓ Written DashboardPanels.tsx (no green, clean monochrome HUD)');

console.log('All updates written successfully!');
