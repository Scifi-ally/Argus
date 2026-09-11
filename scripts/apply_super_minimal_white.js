const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

const panelStyleStr = `const panelStyle: React.CSSProperties = {
  background: 'rgba(8, 12, 18, 0.28)',
  backdropFilter: 'blur(16px)',
  WebkitBackdropFilter: 'blur(16px)',
  border: '1px solid rgba(255, 255, 255, 0.04)',
  borderRadius: '16px',
};`;

// 1. FleetStatusCounters.tsx
const p1Code = `import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const FleetStatusCounters: React.FC = () => {
  const { currentFrame, totalFrames, isCompleted } = useReconstruction();
  ${panelStyleStr}

  const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;
  const livePoints = Math.round(ratio * 1455200);

  return (
    <div
      className="flex flex-col justify-between select-none overflow-hidden flex-1 min-h-[105px] p-4 transition-all"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-widest text-white/35 uppercase font-mono">
        Reconstruction
      </div>

      <div className="grid grid-cols-2 gap-3 my-auto">
        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Points</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
            {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">GSD</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
            1.42 cm/px
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">RMSE</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
            0.38 px
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Accuracy</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
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

// 2. OperationalEfficiency.tsx
const p2Code = `import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';
import { useMission } from '../../state/missionStore';

export const OperationalEfficiency: React.FC = () => {
  const { currentFrame, totalFrames, isPlaying, altitudeM } = useReconstruction();
  const { mission } = useMission();
  ${panelStyleStr}

  const allPoints = mission?.flight?.points || [];
  const totalWaypoints = allPoints.length || 30;
  const ratio = totalFrames > 0 ? Math.min(1, currentFrame / totalFrames) : 0;
  const currentWaypoint = Math.min(totalWaypoints, Math.floor(ratio * totalWaypoints) + 1);

  return (
    <div
      className="flex flex-col justify-between select-none overflow-hidden flex-1 min-h-[105px] p-4 transition-all"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-widest text-white/35 uppercase font-mono">
        Telemetry
      </div>

      <div className="grid grid-cols-2 gap-3 my-auto">
        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Waypoint</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
            {currentWaypoint} / {totalWaypoints}
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Altitude</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
            {altitudeM.toFixed(1)} m
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Speed</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
            {isPlaying ? '4.8 m/s' : '0.0 m/s'}
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">GNSS</div>
          <div className="font-mono text-[13px] text-white font-light tracking-tight mt-0.5">
            RTK Fixed
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

// 3. DroneUnitCard.tsx
const p3Code = `import React from 'react';

export const DroneUnitCard: React.FC = () => {
  ${panelStyleStr}

  return (
    <div
      className="flex flex-col justify-between flex-[2] min-h-[220px] select-none overflow-hidden p-4 transition-all"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-widest text-white/35 uppercase font-mono">
        Sensor & Pipeline
      </div>

      <div className="flex flex-col justify-around flex-1 py-1 space-y-2.5 my-auto">
        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Sensor</div>
          <div className="font-mono text-[12px] text-white font-light mt-0.5">
            Sony 4K Aerial Gimbal
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Exposure</div>
          <div className="font-mono text-[12px] text-white/80 font-light mt-0.5">
            1/1200s · ISO 100 · f/2.8
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Overlap</div>
          <div className="font-mono text-[12px] text-white/80 font-light mt-0.5">
            82% Forward · 76% Side
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Core</div>
          <div className="font-mono text-[12px] text-white font-light mt-0.5">
            Instant-NGP Surface
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Compute</div>
          <div className="font-mono text-[12px] text-white/60 font-light mt-0.5">
            CUDA RTX Acceleration
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

// 4. ScheduleOffset.tsx
const p4Code = `import React from 'react';

export const ScheduleOffset: React.FC = () => {
  ${panelStyleStr}

  return (
    <div
      className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-4"
      style={panelStyle}
    >
      <div className="text-[10px] font-medium tracking-widest text-white/35 uppercase font-mono">
        Datum & Precision
      </div>

      <div className="grid grid-cols-2 gap-3 my-auto">
        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Datum</div>
          <div className="font-mono text-[12px] text-white font-light mt-0.5">
            WGS84
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Horizontal</div>
          <div className="font-mono text-[12px] text-white font-light mt-0.5">
            ± 1.8 cm
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Vertical</div>
          <div className="font-mono text-[12px] text-white font-light mt-0.5">
            ± 2.4 cm
          </div>
        </div>

        <div>
          <div className="text-[9px] text-white/35 uppercase tracking-wider font-mono">Format</div>
          <div className="font-mono text-[12px] text-white font-light mt-0.5">
            3D GLB
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

// 5. PassengerVolume.tsx (The Timeline Component - Pure Minimalist White)
const p5Code = `import React from 'react';
import { Play, Pause, RotateCcw, Box } from 'lucide-react';
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
  ${panelStyleStr}

  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = Math.floor(sec % 60);
    return \`\${mins.toString().padStart(2, '0')}:\${secs.toString().padStart(2, '0')}\`;
  };

  return (
    <div
      className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-4"
      style={panelStyle}
    >
      {/* 1. Header: Ultra-minimal label and status text (pure white only) */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium tracking-widest text-white/35 uppercase font-mono">
          Timeline
        </span>

        <span className="text-[10px] font-mono text-white/50 tracking-wider">
          {isCompleted
            ? 'MODEL COMPLETE'
            : isPlaying
            ? \`GENERATING MESH \${progressPercent}%\`
            : currentFrame > 0
            ? 'PAUSED'
            : 'READY'}
        </span>
      </div>

      {/* 2. Middle Row: Controls, Inspection Trigger, Time & Speed (pure white only) */}
      <div className="flex items-center justify-between my-auto">
        <div className="flex items-center space-x-3">
          {/* Main Play / Pause / Replay Button - Clean frosted white */}
          <button
            type="button"
            onClick={togglePlay}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-[11px] font-mono font-medium transition-all cursor-pointer active:scale-95 bg-white/10 hover:bg-white/20 text-white border border-white/10"
          >
            {isCompleted ? (
              <>
                <RotateCcw className="w-3 h-3 text-white" />
                <span>REPLAY</span>
              </>
            ) : isPlaying ? (
              <>
                <Pause className="w-3 h-3 fill-white text-white" />
                <span>PAUSE</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 fill-white text-white" />
                <span>START</span>
              </>
            )}
          </button>

          {/* Minimal Inspect 3D Model Button - Pure white pill */}
          {isCompleted && (
            <button
              type="button"
              onClick={openViewer}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-[11px] font-mono font-medium text-white transition-all cursor-pointer active:scale-95 bg-white/15 hover:bg-white/25 border border-white/20"
            >
              <Box className="w-3 h-3 text-white" />
              <span>INSPECT 3D MODEL</span>
            </button>
          )}

          {/* Minimal Time & Frame Counter */}
          <div className="flex items-center space-x-2 pl-0.5">
            <span className="font-mono text-[11px] text-white/90">
              {formatTime(currentSeconds)}
            </span>
            <span className="text-white/20 font-mono text-[11px]">/</span>
            <span className="font-mono text-[11px] text-white/40">
              {formatTime(totalSeconds)}
            </span>
            <span className="text-white/15 text-[11px]">·</span>
            <span className="font-mono text-[10px] text-white/40">
              FRAME {currentFrame} / {totalFrames}
            </span>
          </div>
        </div>

        {/* Speed Controls: 1x, 2x, 4x */}
        <div className="flex items-center space-x-1">
          {[1, 2, 4].map((speed) => (
            <button
              key={speed}
              type="button"
              onClick={() => setSpeed(speed)}
              className={\`px-1.5 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer \${
                playbackSpeed === speed
                  ? 'text-white bg-white/15 border border-white/15'
                  : 'text-white/35 hover:text-white/60 border border-transparent'
              }\`}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>

      {/* 3. Bottom Row: Ultra-minimal Pure White Scrub Line */}
      <div className="relative w-full h-1.5 flex items-center">
        {/* Track */}
        <div className="absolute inset-0 h-1 rounded-full bg-white/10 overflow-hidden">
          <div
            className="h-full rounded-full bg-white transition-all duration-75"
            style={{ width: \`\${progressPercent}%\` }}
          />
        </div>

        {/* Hidden Range Input for Scrubbing */}
        <input
          type="range"
          min={0}
          max={totalFrames || 100}
          value={currentFrame}
          onChange={(e) => seekToFrame(Number(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />

        {/* Minimal White Thumb */}
        <div
          className="absolute w-2.5 h-2.5 rounded-full bg-white shadow-sm pointer-events-none transition-all duration-75"
          style={{ left: \`calc(\${progressPercent}% - 5px)\` }}
        />
      </div>
    </div>
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), p5Code, 'utf8');
console.log('✓ Written PassengerVolume.tsx');

console.log('✓ All 5 panels updated to pure white minimal design!');
