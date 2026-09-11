const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// Common glass style: White, transparent, blurry
const panelStyle = `
  background: 'rgba(12, 16, 22, 0.28)',
  backdropFilter: 'blur(28px) saturate(180%)',
  WebkitBackdropFilter: 'blur(28px) saturate(180%)',
  border: '1px solid rgba(255, 255, 255, 0.12)',
  borderRadius: '16px',
  boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
`;

// 1. FleetStatusCounters.tsx -> UAV Sensor & Flight Telemetry (No nested boxes, only white)
const fleetCountersCode = `import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const FleetStatusCounters: React.FC = () => {
  const { altitudeM, rtkStatus } = useReconstruction();

  const panelStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="flex flex-col select-none p-3.5 transition-all space-y-2.5 shrink-0" style={panelStyle}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
        <div>
          <span className="text-[11.5px] font-medium text-white tracking-tight">
            UAV SENSOR & FLIGHT TELEMETRY
          </span>
          <p className="text-[8.5px] font-mono text-white/50 tracking-wider uppercase mt-0.5">
            Single-Pass Monocular Orbit • 4K 30fps Stream
          </p>
        </div>
        <div className="flex items-center space-x-1">
          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
          <span className="text-[8.5px] font-mono text-white/80 font-medium tracking-wider">
            {rtkStatus.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Primary Telemetry Grid (Open layout, ZERO nested boxes, Pure White) */}
      <div className="grid grid-cols-3 gap-y-2 gap-x-3 pt-0.5">
        <div>
          <div className="text-[8.5px] font-mono text-white/45 uppercase tracking-wider">Altitude AGL</div>
          <div className="text-[15px] font-light text-white font-mono mt-0.5 tabular-nums">
            {altitudeM ? altitudeM.toFixed(1) : '14.2'} <span className="text-[10px] text-white/60">m</span>
          </div>
        </div>

        <div>
          <div className="text-[8.5px] font-mono text-white/45 uppercase tracking-wider">Ground Speed</div>
          <div className="text-[15px] font-light text-white font-mono mt-0.5 tabular-nums">
            4.8 <span className="text-[10px] text-white/60">m/s</span>
          </div>
        </div>

        <div>
          <div className="text-[8.5px] font-mono text-white/45 uppercase tracking-wider">Resolution</div>
          <div className="text-[15px] font-light text-white font-mono mt-0.5 tabular-nums">
            3840×2160
          </div>
        </div>

        <div>
          <div className="text-[8.5px] font-mono text-white/45 uppercase tracking-wider">Focal Optics</div>
          <div className="text-[15px] font-light text-white font-mono mt-0.5 tabular-nums">
            24mm <span className="text-[10px] text-white/60">f/2.8</span>
          </div>
        </div>

        <div>
          <div className="text-[8.5px] font-mono text-white/45 uppercase tracking-wider">Forward Overlap</div>
          <div className="text-[15px] font-light text-white font-mono mt-0.5 tabular-nums">
            82%
          </div>
        </div>

        <div>
          <div className="text-[8.5px] font-mono text-white/45 uppercase tracking-wider">Lateral Overlap</div>
          <div className="text-[15px] font-light text-white font-mono mt-0.5 tabular-nums">
            74%
          </div>
        </div>
      </div>
    </div>
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), fleetCountersCode, 'utf8');
console.log('✓ Written components/dashboard/FleetStatusCounters.tsx');

// 2. OperationalEfficiency.tsx -> Photogrammetric Metric Accuracy (Pure White Spline, No boxes)
const opEffCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const OperationalEfficiency: React.FC = () => {
  const { metricAccuracy, gsdCmPx } = useReconstruction();

  const panelStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden transition-all" style={panelStyle}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
        <div>
          <span className="text-[11.5px] font-medium text-white tracking-tight">
            PHOTOGRAMMETRIC METRIC ACCURACY
          </span>
          <p className="text-[8.5px] font-mono text-white/50 tracking-wider uppercase mt-0.5">
            Single-Pass Convergence • Without GCPs
          </p>
        </div>
        <ArrowUpRight className="w-4 h-4 text-white/60 hover:text-white transition-colors cursor-pointer" />
      </div>

      {/* Main Metric: 99.4 % / 78.3 % + Reprojection RMSE */}
      <div className="flex items-baseline justify-between my-1">
        <div className="flex items-baseline space-x-1.5">
          <span className="text-[34px] font-light tracking-tight text-white leading-none font-mono">
            {metricAccuracy ? metricAccuracy.toFixed(1) : '99.4'}
          </span>
          <span className="text-[16px] font-light text-white/80 font-mono">%</span>
          <span className="text-[10px] font-mono text-white/50 ml-2">Accuracy Metric</span>
        </div>

        <div className="text-right">
          <div className="text-[9px] font-mono text-white/45 uppercase tracking-wider">Reprojection RMSE</div>
          <div className="text-[13px] font-mono text-white font-light">0.38 px</div>
        </div>
      </div>

      {/* Pure White Convergence Spline Chart */}
      <div className="relative w-full h-[88px] my-1">
        {/* Target threshold indicator */}
        <div className="absolute top-[18%] right-0 flex items-center space-x-1 z-10">
          <span className="text-[8.5px] font-mono text-white/50">&lt;0.50 px RMSE</span>
        </div>

        <svg className="w-full h-full overflow-visible" viewBox="0 0 320 85" preserveAspectRatio="none">
          <defs>
            <linearGradient id="whiteSplineGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Target Dashed Line */}
          <line
            x1="0"
            y1="20"
            x2="270"
            y2="20"
            stroke="rgba(255, 255, 255, 0.25)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />

          {/* Spline Area Fill */}
          <path
            d="M 10 60 
               C 35 68, 45 72, 60 70 
               C 85 66, 110 46, 135 44 
               C 160 42, 185 60, 210 48 
               C 225 36, 235 22, 250 23 
               C 265 24, 280 46, 305 44 
               L 305 85 L 10 85 Z"
            fill="url(#whiteSplineGradient)"
          />

          {/* Spline Line */}
          <path
            d="M 10 60 
               C 35 68, 45 72, 60 70 
               C 85 66, 110 46, 135 44 
               C 160 42, 185 60, 210 48 
               C 225 36, 235 22, 250 23 
               C 265 24, 280 46, 305 44"
            fill="none"
            stroke="#ffffff"
            strokeWidth="1.6"
          />

          {/* Pure White Vertex Dots */}
          <circle cx="60" cy="70" r="2.5" fill="#ffffff" />
          <circle cx="135" cy="44" r="2.5" fill="#ffffff" />
          <circle cx="210" cy="48" r="2.5" fill="#ffffff" />
          <circle cx="250" cy="23" r="3" fill="#ffffff" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
        </svg>

        {/* Y Axis percentage markers on the right */}
        <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between text-[7.5px] font-mono text-white/35 pointer-events-none">
          <span>100%</span>
          <span>75%</span>
          <span>50%</span>
          <span>25%</span>
        </div>
      </div>

      {/* Bottom Metadata: Ground Sampling Distance & Collinearity */}
      <div className="flex justify-between items-center text-[8.5px] font-mono text-white/50 pt-1.5 border-t border-white/[0.08]">
        <span>GSD: {gsdCmPx ? gsdCmPx.toFixed(2) : '1.42'} cm/px</span>
        <span>Bundle Adjustment: Converged</span>
        <span>Collinearity: Valid</span>
      </div>
    </div>
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), opEffCode, 'utf8');
console.log('✓ Written components/dashboard/OperationalEfficiency.tsx');

// 3. DroneUnitCard.tsx -> NTRO 3D Model Generation Pipeline (5 PS 26158 Stages, No boxes, Pure White)
const ntroPipelineCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const DroneUnitCard: React.FC = () => {
  const { currentFrame, totalFrames, isCompleted } = useReconstruction();
  const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;
  const livePoints = Math.round(ratio * 1455200);

  const panelStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  const stages = [
    {
      title: '(i) 3D Terrain & Structures',
      desc: 'Epipolar Sparse Tie-Point Geometry',
      metric: \`\${Math.round(ratio * 84200).toLocaleString()} pts\`,
      status: 'CONVERGED',
    },
    {
      title: '(ii) Building Facades & Rooftops',
      desc: 'Multi-View Surface Normal Extraction',
      metric: 'Active Ray Marching',
      status: ratio > 0.3 ? 'TEXTURED' : 'PENDING',
    },
    {
      title: '(iii) Roads & Infrastructure',
      desc: 'Planar Geometry & Coordinate Mesh',
      metric: 'Ground Class OK',
      status: ratio > 0.5 ? 'SOLVED' : 'QUEUED',
    },
    {
      title: '(iv) Dynamic Object Filtering',
      desc: 'AI Semantic Mask (Moving Vehicles/Humans Removed)',
      metric: 'Occlusion Inpainted',
      status: 'FILTERED',
    },
    {
      title: '(v) Textured 3D Mesh & LAS Cloud',
      desc: 'Instant-NGP Radiance Surface Priors',
      metric: '193,748 Polygons',
      status: isCompleted ? 'DELIVERABLE READY' : 'PROCESSING',
    },
  ];

  return (
    <div className="h-full min-h-[290px] select-none p-3.5 flex flex-col justify-between overflow-hidden" style={panelStyle}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
        <div>
          <span className="text-[11.5px] font-medium text-white tracking-tight">
            NTRO 3D MODEL GENERATION PIPELINE
          </span>
          <p className="text-[8.5px] font-mono text-white/50 tracking-wider uppercase mt-0.5">
            Problem Statement 26158 • Single-Pass Architecture
          </p>
        </div>
        <ArrowUpRight className="w-4 h-4 text-white/60 hover:text-white cursor-pointer" />
      </div>

      {/* 5 Problem Statement Stages (Clean vertical list, NO nested boxes, Pure White) */}
      <div className="flex flex-col space-y-2 py-1 my-auto">
        {stages.map((stage, i) => (
          <div key={i} className="flex items-center justify-between py-1 border-b border-white/[0.04]">
            <div className="flex flex-col">
              <span className="text-[10.5px] font-medium text-white tracking-tight">
                {stage.title}
              </span>
              <span className="text-[8.5px] font-mono text-white/50">
                {stage.desc}
              </span>
            </div>

            <div className="text-right flex flex-col items-end">
              <span className="text-[9.5px] font-mono text-white font-light">
                {stage.metric}
              </span>
              <span className="text-[7.5px] font-mono text-white/40 tracking-wider uppercase">
                {stage.status}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom Live Tie-Points Summary */}
      <div className="flex justify-between items-center text-[9px] font-mono text-white/50 pt-1.5 border-t border-white/[0.08]">
        <span>Dense Tie-Points: {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}</span>
        <span>Format: GLB 3D · LAS</span>
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), ntroPipelineCode, 'utf8');
console.log('✓ Written components/dashboard/DroneUnitCard.tsx');

// 4. ScheduleOffset.tsx -> Geodetic Datum & Spatial Precision Matrix (No boxes, pure white)
const schedOffsetCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';

export const ScheduleOffset: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-4" style={panelStyle}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1.5">
        <div>
          <span className="text-[12px] font-medium text-white tracking-tight">
            GEODETIC DATUM & SPATIAL PRECISION
          </span>
          <p className="text-[8.5px] font-mono text-white/50 tracking-wider uppercase mt-0.5">
            WGS84 Georeferenced Metric Matrix
          </p>
        </div>
        <ArrowUpRight className="w-4 h-4 text-white/60 hover:text-white cursor-pointer" />
      </div>

      {/* Main Metric: Horizontal & Vertical Error */}
      <div className="flex items-baseline justify-between my-0.5">
        <div className="flex items-baseline space-x-2">
          <span className="text-[32px] font-light tracking-tight text-white leading-none font-mono">
            &plusmn; 1.8
          </span>
          <span className="text-[14px] font-light text-white/70 font-mono">cm</span>
          <span className="text-[10px] font-mono text-white/45 ml-2">Horizontal Error (XY)</span>
        </div>

        <div className="text-right">
          <span className="text-[9px] font-mono text-white/45 uppercase tracking-wider block">Vertical Error (Z)</span>
          <span className="text-[13px] font-mono text-white font-light">&plusmn; 2.4 cm</span>
        </div>
      </div>

      {/* Precision Calibration Matrix Table (Pure White, Haired dividers, NO boxes) */}
      <div className="w-full flex flex-col text-[11px] font-mono mt-1">
        {/* Table Header Row */}
        <div className="grid grid-cols-6 gap-2 text-white/45 text-[8.5px] pb-1 border-b border-white/[0.08] uppercase tracking-wider">
          <span className="col-span-1">Parameter</span>
          <span className="text-center">Lat (X)</span>
          <span className="text-center">Lon (Y)</span>
          <span className="text-center">Alt (Z)</span>
          <span className="text-center">Pitch</span>
          <span className="text-center">Roll</span>
        </div>

        {/* Row 1: Estimated Variance */}
        <div className="grid grid-cols-6 gap-2 py-1.5 items-center text-white/85 border-b border-white/[0.04]">
          <span className="col-span-1 text-white font-medium">Estimated</span>
          <span className="text-center text-white/70 border-l border-white/[0.08]">&plusmn;1.8cm</span>
          <span className="text-center text-white border-l border-white/[0.08] font-medium">&plusmn;1.6cm</span>
          <span className="text-center text-white/70 border-l border-white/[0.08]">&plusmn;2.4cm</span>
          <span className="text-center text-white/70 border-l border-white/[0.08]">0.04&deg;</span>
          <span className="text-center text-white border-l border-white/[0.08] font-medium">0.03&deg;</span>
        </div>

        {/* Row 2: Defense Specification Tolerance */}
        <div className="grid grid-cols-6 gap-2 py-1.5 items-center text-white/60">
          <span className="col-span-1 text-white/50">Tolerance</span>
          <span className="text-center border-l border-white/[0.08]">&lt;3.0cm</span>
          <span className="text-center border-l border-white/[0.08]">&lt;3.0cm</span>
          <span className="text-center border-l border-white/[0.08]">&lt;5.0cm</span>
          <span className="text-center border-l border-white/[0.08]">&lt;0.10&deg;</span>
          <span className="text-center border-l border-white/[0.08]">&lt;0.10&deg;</span>
        </div>
      </div>
    </div>
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), schedOffsetCode, 'utf8');
console.log('✓ Written components/dashboard/ScheduleOffset.tsx');

// 5. PassengerVolume.tsx -> Single-Pass 3D Reconstruction Timeline (Timeline Component, Pure White)
const passVolCode = `import React from 'react';
import { ArrowUpRight, Play, Pause } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const PassengerVolume: React.FC = () => {
  const {
    isPlaying,
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

  const panelStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;
  const livePoints = Math.round(ratio * 1455200);

  const bars = [
    { height: 68, label: '55k', delta: '+8%' },
    { height: 75, label: '57k', delta: '+12%' },
    { height: 71, label: '56k', delta: '+6%' },
    { height: 68, label: '55k', delta: '+4%' },
    { height: 60, label: '52k', delta: '+2%' },
    { height: 62, label: '52k', delta: '+5%' },
    { height: 63, label: '52k', delta: '+7%' },
  ];

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return \`\${m.toString().padStart(2, '0')}:\${s.toString().padStart(2, '0')}\`;
  };

  return (
    <div className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-3" style={panelStyle}>
      {/* Header with Timeline Title & Operational Playback Controls */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1">
        <div className="flex items-center space-x-2">
          <div>
            <span className="text-[11.5px] font-medium text-white tracking-tight">
              SINGLE-PASS 3D RECONSTRUCTION TIMELINE
            </span>
            <p className="text-[8px] font-mono text-white/50 tracking-wider uppercase mt-0.5">
              Live Monocular Frame Ingestion & Point Cloud Generation
            </p>
          </div>
          <ArrowUpRight className="w-3.5 h-3.5 text-white/50 hover:text-white cursor-pointer" />
        </div>

        {/* Pure White Timeline Controls */}
        <div className="flex items-center space-x-2">
          {/* Play/Pause Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/15 hover:bg-white/25 text-white text-[9.5px] font-mono cursor-pointer transition-all active:scale-95 border border-white/20"
          >
            {isPlaying ? <Pause className="w-2.5 h-2.5 text-white fill-white" /> : <Play className="w-2.5 h-2.5 text-white fill-white" />}
            <span>{isPlaying ? 'PAUSE' : 'START'}</span>
          </button>

          {/* Frame & Time indicator */}
          <span className="text-[9.5px] font-mono text-white/70">
            F:{currentFrame}/{totalFrames || 1350} · {formatTime(currentSeconds)}/{formatTime(totalSeconds || 45)}
          </span>

          {/* Speed Toggle */}
          <button
            type="button"
            onClick={() => setSpeed(playbackSpeed === 1 ? 2 : playbackSpeed === 2 ? 4 : 1)}
            className="px-1.5 py-0.5 rounded bg-white/10 text-[8.5px] font-mono text-white hover:bg-white/20 border border-white/10"
          >
            {playbackSpeed}x
          </button>
        </div>
      </div>

      {/* Main Metric: Live Reconstructed 3D Points */}
      <div className="flex items-baseline justify-between my-0.5">
        <div className="flex items-baseline space-x-1.5">
          <span className="text-[26px] font-light tracking-tight text-white leading-none font-mono">
            {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}
          </span>
          <span className="text-[10px] font-mono text-white/50">Reconstructed 3D Points</span>
        </div>

        <span className="text-[8.5px] font-mono text-white/40">
          Matched Features / Sector
        </span>
      </div>

      {/* Matched Feature Density Histogram (Pure White Bars & Pure White Labels) */}
      <div className="relative w-full h-[40px] flex items-end justify-between px-2">
        {bars.map((b, i) => (
          <div key={i} className="flex flex-col items-center space-y-0.5 flex-1">
            <div className="flex items-center space-x-0.5 text-[7.5px] font-mono leading-none text-white/70">
              <span>{b.label}</span>
              <span className="text-white/40 font-light">{b.delta}</span>
            </div>
            <div
              className="w-[14px] lg:w-[18px] rounded-t-sm bg-white/25 hover:bg-white/40 transition-all"
              style={{ height: \`\${b.height * 0.32}px\` }}
            />
          </div>
        ))}

        {/* Right Y-axis markers */}
        <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between text-[7px] font-mono text-white/35 pointer-events-none">
          <span>60k</span>
          <span>0k</span>
        </div>
      </div>

      {/* Pure White Interactive Scrubbing Line & Frame Axis */}
      <div className="relative w-full pt-0.5">
        <div className="relative w-full h-1.5 bg-white/10 rounded-full cursor-pointer overflow-hidden">
          <div
            className="h-full bg-white transition-all duration-75"
            style={{ width: \`\${progressPercent}%\` }}
          />
          <input
            type="range"
            min={0}
            max={totalFrames || 100}
            value={currentFrame}
            onChange={(e) => seekToFrame(Number(e.target.value))}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
        </div>

        {/* Frame Markers */}
        <div className="flex justify-between text-[7.5px] font-mono text-white/35 pt-0.5">
          <span>F:000</span>
          <span>F:300</span>
          <span>F:600</span>
          <span>F:900</span>
          <span>F:1200</span>
          <span>F:1350</span>
        </div>
      </div>
    </div>
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), passVolCode, 'utf8');
console.log('✓ Written components/dashboard/PassengerVolume.tsx');

// 6. MapHeader.tsx -> Single-Pass 3D Reconstruction Header (NTRO PS 26158)
const mapHeaderCode = `import React, { useState } from 'react';
import { ChevronDown, Check, Crosshair, Box } from 'lucide-react';
import { useMission } from '../../state/missionStore';

export const MapHeader: React.FC = () => {
  const { availableMissions, selectMission } = useMission();
  const [selectedMissionName, setSelectedMissionName] = useState('Zurich Grossmünster');
  const [isMissionDropdownOpen, setIsMissionDropdownOpen] = useState(false);
  const [isFormatDropdownOpen, setIsFormatDropdownOpen] = useState(false);
  const [activeFormat, setActiveFormat] = useState('3D GLB Mesh');

  const pillStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.35)',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
  };

  const menuStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.95)',
    backdropFilter: 'blur(28px)',
    WebkitBackdropFilter: 'blur(28px)',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    boxShadow: '0 16px 40px rgba(0,0,0,0.8)',
  };

  const missions = [
    'Zurich Grossmünster',
    'Aerial Drone Reconnaissance',
    'Tactical UAS Validation',
  ];

  return (
    <div className="flex flex-col space-y-1.5 pointer-events-auto select-none">
      {/* Title */}
      <h1 className="text-[24px] font-light tracking-tight text-white leading-none">
        Single-Pass 3D Reconstruction
      </h1>
      <p className="text-[9px] font-mono text-white/50 tracking-wider uppercase">
        NTRO Defense Geospatial Division • PS ID: 26158
      </p>

      {/* Two Clean Dropdown Pills */}
      <div className="flex items-center space-x-2 pt-1">
        {/* Mission Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsMissionDropdownOpen(!isMissionDropdownOpen);
              setIsFormatDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white hover:bg-white/10 transition-all cursor-pointer shadow-md"
            style={pillStyle}
          >
            <Crosshair className="w-3.5 h-3.5 text-white/80" />
            <span className="font-medium">{selectedMissionName}</span>
            <ChevronDown className="w-3 h-3 text-white/50" />
          </button>

          {isMissionDropdownOpen && (
            <div className="absolute top-9 left-0 w-64 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {missions.map((m, idx) => (
                <div
                  key={m}
                  onClick={() => {
                    setSelectedMissionName(m);
                    if (availableMissions[idx]) {
                      selectMission(availableMissions[idx].id);
                    }
                    setIsMissionDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white flex justify-between items-center"
                >
                  <span>{m}</span>
                  {selectedMissionName === m && <Check className="w-3.5 h-3.5 text-white" />}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Deliverable Format Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsFormatDropdownOpen(!isFormatDropdownOpen);
              setIsMissionDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white hover:bg-white/10 transition-all cursor-pointer shadow-md"
            style={pillStyle}
          >
            <Box className="w-3.5 h-3.5 text-white/80" />
            <span className="font-medium">{activeFormat}</span>
            <ChevronDown className="w-3 h-3 text-white/50" />
          </button>

          {isFormatDropdownOpen && (
            <div className="absolute top-9 left-0 w-44 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {['3D GLB Mesh', 'Dense LAS Cloud', 'Digital Surface DSM', 'Wavefront OBJ'].map((fmt) => (
                <div
                  key={fmt}
                  onClick={() => {
                    setActiveFormat(fmt);
                    setIsFormatDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white flex justify-between items-center"
                >
                  <span>{fmt}</span>
                  {activeFormat === fmt && <Check className="w-3.5 h-3.5 text-white" />}
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
console.log('✓ Written components/dashboard/MapHeader.tsx');

// 7. DashboardPanels.tsx:
// - Added Oval Blur Effect over map (stronger blur as it expands outward)
// - Removed Zoom Control Pill
// - Removed Floating Passenger Load card
// - Removed Center Radar Reticle
// - Maintained crisp left sidebar & bottom row panels
const dashboardPanelsCode = `import React from 'react';
import { FleetStatusCounters } from './FleetStatusCounters';
import { OperationalEfficiency } from './OperationalEfficiency';
import { DroneUnitCard } from './DroneUnitCard';
import { MapHeader } from './MapHeader';
import { ScheduleOffset } from './ScheduleOffset';
import { PassengerVolume } from './PassengerVolume';
import { VideoUploadButton } from './VideoUploadButton';

export const DashboardPanels: React.FC = () => {
  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 p-4 pb-2 flex flex-col justify-between">
      {/* 1. OVAL OUTWARD BLUR EFFECT OVER MAP
          The center of the oval (where the flight route and model are located) is crystal-clear (transparent),
          and the blur effect becomes progressively stronger as it moves outward toward the screen edges & panels.
      */}
      <div
        className="absolute inset-0 pointer-events-none z-10 overflow-hidden"
        style={{
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          maskImage: 'radial-gradient(ellipse 62% 52% at 58% 46%, transparent 22%, rgba(0,0,0,0.4) 52%, black 88%)',
          WebkitMaskImage: 'radial-gradient(ellipse 62% 52% at 58% 46%, transparent 22%, rgba(0,0,0,0.4) 52%, black 88%)',
        }}
      />

      {/* 2. FLOATING TITLE & DROPDOWNS: Top-left of map next to left sidebar */}
      <div className="absolute top-5 left-[370px] lg:left-[395px] xl:left-[415px] z-40 pointer-events-auto">
        <MapHeader />
      </div>

      {/* 3. TOP-RIGHT ACTIONS: Video Upload Button */}
      <div className="absolute top-5 right-5 z-40 pointer-events-auto flex items-center space-x-3">
        <VideoUploadButton />
      </div>

      {/* 4. MAIN SPATIAL WORKSPACE (Left Side Panels & Bottom Row Panels) */}
      <div className="relative z-30 w-full flex-1 flex gap-3.5 overflow-hidden pointer-events-none mb-1">
        {/* LEFT COLUMN STACK: Sensor State -> Photogrammetry Accuracy -> NTRO 5-Stage Pipeline */}
        <aside className="w-[340px] lg:w-[365px] xl:w-[385px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto overflow-hidden">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <div className="flex-1 min-h-0 overflow-hidden">
            <DroneUnitCard />
          </div>
        </aside>

        {/* BOTTOM ROW: Geodetic Datum & Precision (Left) & Single-Pass Timeline (Right) */}
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

      {/* 5. FOOTER STATUS BAR (At very bottom edge across screen) */}
      <div className="w-full flex items-center justify-between text-[9.5px] font-mono text-white/40 px-1 pt-1 pointer-events-none">
        <div className="flex items-center space-x-2">
          <span>NTRO Tactical UAS Reconnaissance</span>
          <span className="text-white/20">•</span>
          <span>Sensor: Sony 4K Exmor</span>
          <span className="text-white/20">•</span>
          <span>GPS RTK FIXED (Centimeter Precision)</span>
        </div>
        <div className="flex items-center space-x-2">
          <span>Datum: WGS84 / UTM 10N</span>
          <span className="text-white/20">•</span>
          <span>Single-Pass Collinearity: Converged</span>
          <span className="w-1.5 h-1.5 rounded-full bg-white inline-block shadow-[0_0_6px_#ffffff]" />
        </div>
      </div>
    </div>
  );
};

export default DashboardPanels;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx'), dashboardPanelsCode, 'utf8');
console.log('✓ Written components/dashboard/DashboardPanels.tsx');
