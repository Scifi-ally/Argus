const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. Create TimelinePanel.tsx from scratch!
const timelineCode = `import React, { useState, useRef } from 'react';
import { Play, Pause, RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react';
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
    stepFrames,
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
    const ms = Math.floor((sec % 1) * 10);
    return \`\${m.toString().padStart(2, '0')}:\${s.toString().padStart(2, '0')}.\${ms}\`;
  };

  const formatRulerTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return \`\${m.toString().padStart(2, '0')}:\${s.toString().padStart(2, '0')}\`;
  };

  // Interactive scrubbing handler
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const update = (clientX: number) => {
      const x = Math.max(0, Math.min(rect.width, clientX - rect.left));
      const pct = x / rect.width;
      const targetFrame = Math.round(pct * frames);
      seekToFrame(targetFrame);
    };
    update(e.clientX);

    const onPointerMove = (moveEvent: PointerEvent) => {
      update(moveEvent.clientX);
    };
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

  const handlePointerLeave = () => {
    setHoverPercent(null);
  };

  // Calibration time markers along duration (every 5 seconds)
  const timeMarkers = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45];

  // Keyframe ticks (1 per second of video capture)
  const keyframes = Array.from({ length: 46 }, (_, i) => i);

  return (
    <div
      className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-4"
      style={glassStyle}
    >
      {/* 1. TOP BAR: Tactile Play Controls, Timecodes, Frame Count & Live Points */}
      <div className="flex items-center justify-between pb-1">
        {/* Left: Controls Cluster */}
        <div className="flex items-center space-x-2.5">
          {/* Circular Play/Pause Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="w-8 h-8 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-[0_0_14px_rgba(255,255,255,0.45)] cursor-pointer shrink-0"
            title={isPlaying ? 'Pause' : 'Start Single-Pass Reconstruction'}
          >
            {isPlaying ? (
              <Pause className="w-3.5 h-3.5 fill-black stroke-black" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-black stroke-black translate-x-0.5" />
            )}
          </button>

          {/* Reset button */}
          <button
            type="button"
            onClick={resetPlayback}
            className="w-6 h-6 rounded-full bg-white/[0.08] hover:bg-white/[0.18] text-white/70 hover:text-white flex items-center justify-center transition-all cursor-pointer"
            title="Reset to 00:00"
          >
            <RotateCcw className="w-3 h-3" />
          </button>

          {/* Step Back / Step Forward Frame Buttons */}
          <div className="flex items-center space-x-0.5">
            <button
              type="button"
              onClick={() => stepFrames(-1)}
              className="w-5 h-5 rounded hover:bg-white/10 text-white/50 hover:text-white flex items-center justify-center transition-all cursor-pointer"
              title="Step Backward 1 Frame"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => stepFrames(1)}
              className="w-5 h-5 rounded hover:bg-white/10 text-white/50 hover:text-white flex items-center justify-center transition-all cursor-pointer"
              title="Step Forward 1 Frame"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Precision Timecode */}
          <div className="flex items-baseline space-x-1.5 font-mono pl-1">
            <span className="text-[14px] text-white font-medium tracking-tight">
              {formatTime(currentSeconds)}
            </span>
            <span className="text-[11px] text-white/30">/</span>
            <span className="text-[11px] text-white/50">
              {formatTime(duration)}
            </span>
          </div>

          {/* Frame Counter */}
          <div className="flex items-center space-x-1 font-mono text-[9.5px] text-white/45 pl-1 border-l border-white/[0.08]">
            <span className="text-white/30">F:</span>
            <span className="text-white/90 font-medium">{currentFrame}</span>
            <span className="text-white/30">/</span>
            <span>{frames}</span>
          </div>

          {/* Speed Selector */}
          <div className="flex items-center bg-white/[0.06] rounded-md p-0.5 border border-white/[0.08] text-[9.5px] font-mono">
            {[1, 2, 4].map((spd) => (
              <button
                key={spd}
                type="button"
                onClick={() => setSpeed(spd)}
                className={\`px-1.5 py-0.5 rounded transition-all cursor-pointer \${
                  playbackSpeed === spd
                    ? 'bg-white text-black font-semibold shadow-xs'
                    : 'text-white/50 hover:text-white'
                }\`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* Right: Live Points Counter & Status */}
        <div className="flex items-center space-x-3 font-mono">
          <div className="flex items-baseline space-x-1">
            <span className="text-[20px] font-light text-white tracking-tight leading-none">
              {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}
            </span>
            <span className="text-[9px] text-white/40 uppercase">pts</span>
          </div>

          <div className="flex items-center space-x-1.5 text-[9px] text-white/70">
            <span
              className={\`w-1.5 h-1.5 rounded-full \${
                isCompleted
                  ? 'bg-white shadow-[0_0_8px_#ffffff]'
                  : isPlaying
                  ? 'bg-white animate-pulse shadow-[0_0_8px_#ffffff]'
                  : 'bg-white/40'
              }\`}
            />
            <span>{isCompleted ? 'SOLVED' : isPlaying ? 'MAPPING' : 'READY'}</span>
          </div>
        </div>
      </div>

      {/* 2. THE TIMELINE TRACK (Interactive Drone Video & 3D Point Density Track) */}
      <div
        ref={trackRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        className="relative w-full my-1 flex flex-col justify-center cursor-pointer select-none py-1 group"
      >
        {/* Ruler Calibration Scale (Ticks & Labels) */}
        <div className="relative w-full h-[14px] flex items-center mb-0.5">
          {timeMarkers.map((sec) => {
            const pct = (sec / duration) * 100;
            return (
              <div
                key={sec}
                className="absolute flex flex-col items-center pointer-events-none -translate-x-1/2"
                style={{ left: \`\${pct}%\` }}
              >
                <span className="text-[7.5px] font-mono text-white/35 leading-none mb-0.5">
                  {formatRulerTime(sec)}
                </span>
                <div className="w-[1px] h-[3px] bg-white/25" />
              </div>
            );
          })}
        </div>

        {/* Main Ribbon Track */}
        <div className="relative w-full h-[36px] bg-white/[0.05] rounded-lg border border-white/[0.10] overflow-hidden group-hover:border-white/20 transition-all flex items-center">
          {/* Subtle Photogrammetric Density Background Silhouette */}
          <svg
            className="absolute inset-0 w-full h-full opacity-30 pointer-events-none"
            viewBox="0 0 400 36"
            preserveAspectRatio="none"
          >
            <path
              d="M 0 36 
                 C 30 30, 60 22, 90 24 
                 C 120 26, 150 14, 180 12 
                 C 210 10, 240 18, 270 16 
                 C 300 14, 340 8, 370 10 
                 L 400 6 L 400 36 Z"
              fill="rgba(255,255,255,0.18)"
            />
          </svg>

          {/* Progress Filled Area */}
          <div
            className="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-white/10 via-white/20 to-white/30 border-r border-white/60 transition-all duration-75"
            style={{ width: \`\${Math.max(0, Math.min(100, progressPercent))}%\` }}
          />

          {/* 45 Aerial Photo Keyframe Ticks Spaced Along Ribbon */}
          <div className="absolute inset-0 flex items-center justify-between px-1 pointer-events-none">
            {keyframes.map((k) => {
              const kPct = (k / duration) * 100;
              const isPast = kPct <= progressPercent;
              return (
                <div
                  key={k}
                  className={\`w-[1.5px] rounded-full transition-all duration-150 \${
                    isPast
                      ? 'h-3.5 bg-white shadow-[0_0_4px_#ffffff]'
                      : 'h-2 bg-white/15'
                  }\`}
                />
              );
            })}
          </div>

          {/* Hover Ghost Scrubber Line */}
          {hoverPercent !== null && (
            <div
              className="absolute top-0 bottom-0 w-[1px] bg-white/40 pointer-events-none transition-opacity"
              style={{ left: \`\${hoverPercent}%\` }}
            />
          )}

          {/* Active Playhead Scrubber (Solid White Glowing Needle) */}
          <div
            className="absolute top-0 bottom-0 pointer-events-none transition-all duration-75 flex flex-col items-center z-20"
            style={{ left: \`\${Math.max(0, Math.min(100, progressPercent))}%\` }}
          >
            {/* Scrubber Knob Head */}
            <div className="w-3 h-3 rounded-full bg-white shadow-[0_0_10px_#ffffff] -translate-y-2 border border-black/20 shrink-0" />
            {/* Vertical Needle */}
            <div className="w-[2px] flex-1 bg-white shadow-[0_0_8px_#ffffff]" />
            {/* Scrubber Bottom Base */}
            <div className="w-2 h-1 bg-white rounded-b-sm shadow-[0_0_6px_#ffffff] translate-y-1 shrink-0" />
          </div>
        </div>
      </div>

      {/* 3. FOOTER TELEMETRY STREAM (Synchronized Flight Metrics) */}
      <div className="flex items-center justify-between text-[9px] font-mono text-white/50 pt-1 border-t border-white/[0.08]">
        <div className="flex items-center space-x-3">
          <span>ALT: <strong className="text-white font-normal">{altitudeM ? altitudeM.toFixed(1) : '14.0'}m</strong></span>
          <span className="text-white/20">•</span>
          <span>SPEED: <strong className="text-white font-normal">12.4 m/s</strong></span>
          <span className="text-white/20">•</span>
          <span>GSD: <strong className="text-white font-normal">{gsdCmPx ? gsdCmPx.toFixed(2) : '1.42'} cm/px</strong></span>
        </div>

        <div className="flex items-center space-x-3">
          <span>PROGRESS: <strong className="text-white font-normal">{progressPercent.toFixed(0)}%</strong></span>
          <span className="text-white/20">•</span>
          <span>GNSS: <strong className="text-white font-normal">{rtkStatus ? 'RTK FIXED' : 'CARRIER LOCK'}</strong></span>
        </div>
      </div>
    </div>
  );
};

export default TimelinePanel;
`;

fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/TimelinePanel.tsx'), timelineCode, 'utf8');
console.log('✓ Written components/dashboard/TimelinePanel.tsx from scratch');

// 2. Also update PassengerVolume.tsx to re-export TimelinePanel so any existing references work seamlessly
const passVolProxy = `export { TimelinePanel as PassengerVolume, TimelinePanel } from './TimelinePanel';
export default TimelinePanel;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), passVolProxy, 'utf8');
console.log('✓ Updated PassengerVolume.tsx to proxy TimelinePanel');

// 3. Update DashboardPanels.tsx to import TimelinePanel directly
const dashboardPath = path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx');
let dashboardCode = fs.readFileSync(dashboardPath, 'utf8');
dashboardCode = dashboardCode.replace(
  "import { PassengerVolume } from './PassengerVolume';",
  "import { TimelinePanel } from './TimelinePanel';"
);
dashboardCode = dashboardCode.replace(
  '<PassengerVolume />',
  '<TimelinePanel />'
);
fs.writeFileSync(dashboardPath, dashboardCode, 'utf8');
console.log('✓ Updated DashboardPanels.tsx to use TimelinePanel directly');
