const fs = require('fs');
const path = require('path');

const targetFile = path.resolve(__dirname, '../../SIHFrontend/src/components/dashboard/PassengerVolume.tsx');

const code = `import React from 'react';
import { Play, Pause } from 'lucide-react';
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

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;
  const livePoints = Math.round(ratio * 1455200);

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return \`\${m.toString().padStart(2, '0')}:\${s.toString().padStart(2, '0')}\`;
  };

  // 52 fine timeline keyframe ticks with an organic drone flight density profile
  const tickHeights = [
    22, 28, 35, 42, 48, 55, 62, 58, 64, 70, 
    75, 82, 80, 85, 90, 88, 82, 76, 72, 68, 
    62, 58, 65, 72, 80, 84, 88, 92, 90, 85, 
    78, 70, 65, 60, 56, 52, 60, 68, 75, 80, 
    86, 82, 76, 70, 64, 58, 50, 44, 38, 32, 26, 20
  ];

  return (
    <div className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-4" style={glassStyle}>
      {/* Top Row: Playback Controls & Frame Status (Super Minimal) */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {/* Circular Minimal Play/Pause Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="w-7 h-7 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-[0_0_12px_rgba(255,255,255,0.4)] cursor-pointer shrink-0"
            title={isPlaying ? 'Pause' : 'Start'}
          >
            {isPlaying ? (
              <Pause className="w-3.5 h-3.5 fill-black stroke-black" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-black stroke-black translate-x-0.5" />
            )}
          </button>

          {/* Time & Frame Code */}
          <div className="flex items-baseline space-x-2 font-mono">
            <span className="text-[13px] text-white font-medium tracking-tight">
              {formatTime(currentSeconds)}
            </span>
            <span className="text-[11px] text-white/40">/</span>
            <span className="text-[11px] text-white/50">
              {formatTime(totalSeconds || 45)}
            </span>
            <span className="text-[9.5px] text-white/35 ml-1">
              F:{currentFrame}/{totalFrames || 1350}
            </span>
          </div>

          {/* Minimal Speed Pill */}
          <button
            type="button"
            onClick={() => setSpeed(playbackSpeed === 1 ? 2 : playbackSpeed === 2 ? 4 : 1)}
            className="px-2 py-0.5 rounded-md bg-white/[0.08] hover:bg-white/15 text-[9.5px] font-mono text-white/70 hover:text-white transition-all cursor-pointer border border-white/[0.08]"
          >
            {playbackSpeed}x
          </button>
        </div>

        {/* Right side: Points metric */}
        <div className="flex items-baseline space-x-1.5 font-mono">
          <span className="text-[18px] font-light text-white tracking-tight leading-none">
            {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}
          </span>
          <span className="text-[9px] text-white/40 uppercase">pts</span>
        </div>
      </div>

      {/* Middle: Fine-grain interactive waveform scrubber */}
      <div className="relative w-full my-2 flex flex-col justify-center h-[52px]">
        {/* Fine vertical histogram ticks */}
        <div className="w-full h-full flex items-end justify-between gap-[2px] px-0.5">
          {tickHeights.map((h, idx) => {
            const barProgress = (idx / tickHeights.length) * 100;
            const isTraversed = barProgress <= progressPercent;
            return (
              <div
                key={idx}
                className={\`flex-1 rounded-t-sm transition-colors duration-150 \${
                  isTraversed
                    ? 'bg-white shadow-[0_0_6px_rgba(255,255,255,0.4)]'
                    : 'bg-white/15 hover:bg-white/30'
                }\`}
                style={{ height: \`\${(h / 100) * 44}px\` }}
              />
            );
          })}
        </div>

        {/* Needle Scrubber Line */}
        <div
          className="absolute top-0 bottom-0 pointer-events-none transition-all duration-75 flex flex-col items-center"
          style={{ left: \`\${Math.max(0, Math.min(100, progressPercent))}%\` }}
        >
          <div className="w-2 h-2 rounded-full bg-white shadow-[0_0_8px_#ffffff] -translate-y-1" />
          <div className="w-[1.5px] h-full bg-white shadow-[0_0_6px_#ffffff]" />
        </div>

        {/* Invisible Range Input for Smooth Drag/Scrub */}
        <input
          type="range"
          min={0}
          max={totalFrames || 1350}
          value={currentFrame}
          onChange={(e) => seekToFrame(Number(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-20"
        />
      </div>

      {/* Bottom Row: Subtle Time Markers */}
      <div className="flex justify-between text-[8px] font-mono text-white/30 pt-1 border-t border-white/[0.06]">
        <span>00:00</span>
        <span>00:15</span>
        <span>00:30</span>
        <span>00:45</span>
      </div>
    </div>
  );
};

export default PassengerVolume;
`;

fs.writeFileSync(targetFile, code, 'utf8');
console.log('✓ Successfully wrote minimal PassengerVolume.tsx');
