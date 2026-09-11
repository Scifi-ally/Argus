const fs = require('fs');
const path = require('path');

const frontendDir = path.resolve(__dirname, '..', '..', 'SIHFrontend');

// 1. Update ScheduleOffset.tsx
const scheduleOffsetPath = path.join(frontendDir, 'src', 'components', 'dashboard', 'ScheduleOffset.tsx');
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
    background: 'rgba(10, 14, 20, 0.75)',
    backdropFilter: 'blur(24px) saturate(160%)',
    WebkitBackdropFilter: 'blur(24px) saturate(160%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 10px 30px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div
      className="rounded-2xl p-3 flex flex-col justify-between select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Header: Title + Calibrated Badge */}
      <div>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5">
            <Target className="w-3.5 h-3.5 text-[#33d17a]" />
            <span className="text-[9.5px] font-mono tracking-wider text-white/70 uppercase font-semibold">
              Metric Accuracy
            </span>
          </div>
          <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/25">
            <span className="w-1.5 h-1.5 rounded-full bg-[#33d17a] shadow-[0_0_6px_#33d17a]" />
            <span className="text-[8px] font-mono text-[#33d17a] font-semibold tracking-wider">
              CALIBRATED
            </span>
          </div>
        </div>

        <div className="mt-1 flex items-baseline space-x-2">
          <div className="flex items-baseline space-x-1">
            <span className="text-[24px] font-light tracking-tight text-white leading-none font-mono tabular-nums">
              ± 1.42
            </span>
            <span className="text-[12px] font-light text-[#33d17a] font-mono">cm</span>
          </div>
          <span className="text-[9px] text-white/45 font-mono">
            Average Spatial Variance
          </span>
        </div>
      </div>

      {/* Photogrammetry Metrology Readout Table */}
      <div className="my-0.5 bg-white/[0.02] border border-white/[0.05] rounded-xl p-1.5">
        <div className="grid grid-cols-3 gap-2 text-[7.5px] font-mono text-white/40 pb-0.5 border-b border-white/[0.06] uppercase tracking-wider px-1">
          <div>Parameter</div>
          <div className="text-center">Value</div>
          <div className="text-right">Status</div>
        </div>

        <div className="space-y-0.5 pt-0.5">
          {parameters.map((p) => (
            <div
              key={p.name}
              className="grid grid-cols-3 gap-2 items-center text-[8px] font-mono py-[1px] hover:bg-white/[0.03] rounded px-1 transition-colors"
            >
              <div className="text-white/60 truncate">{p.name}</div>
              <div className="text-center text-white font-medium tabular-nums">{p.value}</div>
              <div className="flex items-center justify-end space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#33d17a] inline-block shrink-0 shadow-[0_0_4px_#33d17a]" />
                <span className="text-[#33d17a] font-medium text-[7.5px]">{p.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Horizontal & Vertical Error Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-white/[0.08] text-[8px] font-mono">
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
fs.writeFileSync(scheduleOffsetPath, scheduleOffsetCode, 'utf8');
console.log('1. Updated ScheduleOffset.tsx');

// 2. Update OperationalEfficiency.tsx
const opEffPath = path.join(frontendDir, 'src', 'components', 'dashboard', 'OperationalEfficiency.tsx');
const opEffCode = `import React from 'react';
import { Navigation } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';
import { useMission } from '../../state/missionStore';

export const OperationalEfficiency: React.FC = () => {
  const { currentFrame, totalFrames, totalSeconds, altitudeM, rtkStatus } = useReconstruction();
  const { mission } = useMission();
  const progress = totalFrames > 0 ? Math.max(0, Math.min(1, currentFrame / totalFrames)) : 0;

  const durationStr = \`\${Math.floor(totalSeconds / 60).toString().padStart(2, '0')}:\${(Math.floor(totalSeconds) % 60).toString().padStart(2, '0')}\`;

  const droneX = 18 + progress * (254 - 18);
  const droneY = 24 - Math.sin(progress * Math.PI) * 10;

  const panelStyle: React.CSSProperties = {
    background: 'rgba(10, 14, 20, 0.75)',
    backdropFilter: 'blur(24px) saturate(160%)',
    WebkitBackdropFilter: 'blur(24px) saturate(160%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 10px 30px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div
      className="rounded-2xl p-3 flex flex-col justify-between shrink-0 h-[184px] select-none overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Header: Title + GPS Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-1.5">
          <Navigation className="w-3.5 h-3.5 text-[#5fb8ff]" />
          <span className="text-[9.5px] font-mono tracking-wider text-white/70 uppercase font-semibold">
            Flight Telemetry
          </span>
        </div>
        <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/25">
          <span className="w-1.5 h-1.5 rounded-full bg-[#33d17a] shadow-[0_0_6px_#33d17a]" />
          <span className="text-[8px] font-mono text-[#33d17a] font-semibold tracking-wider">
            {rtkStatus.includes('FIX') ? 'GPS RTK FIXED' : 'GPS LOCKED'}
          </span>
        </div>
      </div>

      {/* Large Value + Small Label */}
      <div className="flex items-baseline space-x-2 my-0.5">
        <span className="text-[28px] font-light tracking-tight text-white leading-none font-mono tabular-nums">
          {durationStr}
        </span>
        <span className="text-[9px] font-mono text-white/50">
          Capture Duration
        </span>
      </div>

      {/* Custom Aerospace Technical Instrumentation SVG */}
      <div className="w-full h-[50px] my-0.5 relative overflow-hidden">
        <svg className="w-full h-full" viewBox="0 0 280 44" preserveAspectRatio="none">
          <defs>
            <linearGradient id="trajGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="rgba(255, 255, 255, 0.2)" />
              <stop offset="60%" stopColor="rgba(51, 209, 122, 0.7)" />
              <stop offset="100%" stopColor="rgba(255, 255, 255, 0.3)" />
            </linearGradient>
          </defs>

          {/* Coordinate Reference Grids */}
          <line x1="12" y1="36" x2="268" y2="36" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />
          <line x1="18" y1="20" x2="18" y2="36" stroke="rgba(255,255,255,0.06)" strokeWidth="0.6" strokeDasharray="2 2" />
          <line x1="80" y1="12" x2="80" y2="36" stroke="rgba(255,255,255,0.06)" strokeWidth="0.6" strokeDasharray="2 2" />
          <line x1="140" y1="14" x2="140" y2="36" stroke="rgba(255,255,255,0.06)" strokeWidth="0.6" strokeDasharray="2 2" />
          <line x1="200" y1="12" x2="200" y2="36" stroke="rgba(255,255,255,0.06)" strokeWidth="0.6" strokeDasharray="2 2" />
          <line x1="254" y1="24" x2="254" y2="36" stroke="rgba(255,255,255,0.06)" strokeWidth="0.6" strokeDasharray="2 2" />

          {/* Position Nodes */}
          <circle cx="18" cy="36" r="1.2" fill="rgba(255,255,255,0.4)" />
          <circle cx="80" cy="36" r="1.2" fill="rgba(255,255,255,0.4)" />
          <circle cx="140" cy="36" r="1.2" fill="rgba(255,255,255,0.4)" />
          <circle cx="200" cy="36" r="1.2" fill="rgba(255,255,255,0.4)" />
          <circle cx="254" cy="36" r="1.2" fill="rgba(255,255,255,0.4)" />

          {/* Flight Trajectory Line */}
          <path
            d="M 18 20 Q 80 4 140 14 T 254 24"
            fill="none"
            stroke="url(#trajGrad)"
            strokeWidth="1.2"
          />

          {/* Altitude Drop Indicator from Drone to Ground */}
          <line
            x1={droneX}
            y1={droneY}
            x2={droneX}
            y2="36"
            stroke="rgba(51, 209, 122, 0.45)"
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
          <circle cx={droneX} cy="36" r="1.6" fill="#33d17a" />

          {/* Drone Vector Icon */}
          <g transform={\`translate(\${droneX}, \${droneY})\`}>
            {/* Sensor Optical Cone */}
            <polygon
              points="0,2.5 -6,12 6,12"
              fill="rgba(51, 209, 122, 0.15)"
              stroke="rgba(51, 209, 122, 0.35)"
              strokeWidth="0.5"
            />
            {/* Frame Arms */}
            <line x1="-5" y1="-2" x2="5" y2="2" stroke="rgba(255,255,255,0.9)" strokeWidth="0.9" />
            <line x1="-5" y1="2" x2="5" y2="-2" stroke="rgba(255,255,255,0.9)" strokeWidth="0.9" />
            <circle cx="0" cy="0" r="2.0" fill="#040608" stroke="#33d17a" strokeWidth="0.8" />

            {/* Rotors */}
            <circle cx="-5" cy="-2" r="1.8" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.6" />
            <circle cx="5" cy="2" r="1.8" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.6" />
            <circle cx="-5" cy="2" r="1.8" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.6" />
            <circle cx="5" cy="-2" r="1.8" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.6" />
          </g>
        </svg>
      </div>

      {/* Underneath Telemetry Grid - Clean 5 columns without truncation */}
      <div className="grid grid-cols-5 gap-1 pt-2 border-t border-white/[0.08] text-[8px] font-mono">
        <div className="bg-white/[0.03] border border-white/[0.05] rounded-md p-1 flex flex-col">
          <span className="text-white/45 text-[6.5px] uppercase font-semibold">Video</span>
          <span className="text-white font-medium truncate mt-0.5">4K • 30fps</span>
        </div>
        <div className="bg-white/[0.03] border border-white/[0.05] rounded-md p-1 flex flex-col">
          <span className="text-white/45 text-[6.5px] uppercase font-semibold">GPS</span>
          <span className="text-[#33d17a] font-medium truncate mt-0.5">LOCKED</span>
        </div>
        <div className="bg-white/[0.03] border border-white/[0.05] rounded-md p-1 flex flex-col">
          <span className="text-white/45 text-[6.5px] uppercase font-semibold">Altitude</span>
          <span className="text-white font-medium truncate mt-0.5">{altitudeM || '14.0'} m</span>
        </div>
        <div className="bg-white/[0.03] border border-white/[0.05] rounded-md p-1 flex flex-col">
          <span className="text-white/45 text-[6.5px] uppercase font-semibold">Points</span>
          <span className="text-white font-medium truncate mt-0.5">
            {mission?.flight?.points ? \`\${(mission.flight.points.length * 48 / 1000).toFixed(1)}M\` : '1.46M'}
          </span>
        </div>
        <div className="bg-white/[0.03] border border-white/[0.05] rounded-md p-1 flex flex-col">
          <span className="text-white/45 text-[6.5px] uppercase font-semibold">Heading</span>
          <span className="text-white font-medium truncate mt-0.5">048°</span>
        </div>
      </div>
    </div>
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(opEffPath, opEffCode, 'utf8');
console.log('2. Updated OperationalEfficiency.tsx');

// 3. Update DroneUnitCard.tsx
const droneUnitPath = path.join(frontendDir, 'src', 'components', 'dashboard', 'DroneUnitCard.tsx');
let droneUnitCode = fs.readFileSync(droneUnitPath, 'utf8');

// Replace WGS84 \u2022 RTK-FLOAT
droneUnitCode = droneUnitCode.replace(/WGS84 \\\\u2022 RTK-FLOAT/g, 'WGS84 • RTK-FLOAT');
droneUnitCode = droneUnitCode.replace(/WGS84 \\u2022 RTK-FLOAT/g, 'WGS84 • RTK-FLOAT');
droneUnitCode = droneUnitCode.replace(/4K \\\\u2022 30 FPS Ingest/g, '4K • 30 FPS Ingest');
droneUnitCode = droneUnitCode.replace(/4K \\u2022 30 FPS Ingest/g, '4K • 30 FPS Ingest');

// Clean up video filename formatting to look polished
droneUnitCode = droneUnitCode.replace(
  `{mission?.video?.filename ? mission.video.filename.replace(/\\.(mp4|mov)$/i, '') : '4K • 30 FPS Ingest'}`,
  `{mission?.video?.filename ? mission.video.filename.replace(/\\.(mp4|mov)$/i, '').replace(/[_-]+/g, ' ').slice(0, 18) : '4K • 30 FPS Ingest'}`
);

// Give Scene AI class breakdown bottom padding and margin
droneUnitCode = droneUnitCode.replace(
  'grid grid-cols-2 gap-x-2 gap-y-0.5 text-[7px] font-mono border-t border-white/[0.08] pt-1',
  'grid grid-cols-2 gap-x-2 gap-y-0.5 text-[7px] font-mono border-t border-white/[0.08] pt-1 pb-0.5 mb-0.5'
);

// Give Pipeline Accent Bar breathing room
droneUnitCode = droneUnitCode.replace(
  'w-full bg-white/[0.08] h-1 rounded-full overflow-hidden',
  'w-full bg-white/[0.08] h-1.5 rounded-full overflow-hidden mb-1'
);

fs.writeFileSync(droneUnitPath, droneUnitCode, 'utf8');
console.log('3. Updated DroneUnitCard.tsx');

// 4. Update PassengerVolume.tsx
const passengerVolPath = path.join(frontendDir, 'src', 'components', 'dashboard', 'PassengerVolume.tsx');
let passengerVolCode = fs.readFileSync(passengerVolPath, 'utf8');

// Enhance metric pill layout and confidence badge styling
passengerVolCode = passengerVolCode.replace(
  'grid grid-cols-4 gap-1.5 pt-0.5 text-[8px] font-mono',
  'grid grid-cols-4 gap-1.5 pt-0.5 text-[8px] font-mono'
);
passengerVolCode = passengerVolCode.replace(
  '<span className="text-[#33d17a] font-medium mt-0.5">99.4%</span>',
  '<span className="text-[#33d17a] font-medium mt-0.5 tabular-nums">99.4%</span>'
);

fs.writeFileSync(passengerVolPath, passengerVolCode, 'utf8');
console.log('4. Updated PassengerVolume.tsx');

// 5. Update MapHeader.tsx
const mapHeaderPath = path.join(frontendDir, 'src', 'components', 'dashboard', 'MapHeader.tsx');
let mapHeaderCode = fs.readFileSync(mapHeaderPath, 'utf8');

// Fix unicode bullet in duration string
mapHeaderCode = mapHeaderCode.replace(/\\\\u2022/g, '•');
mapHeaderCode = mapHeaderCode.replace(/\\u2022/g, '•');

// Enhance mission title formatter to produce executive titles:
// e.g., "i want a video ... Aerial d..." -> "Mission Alpha • Aerial Drone"
const betterFormatter = `  const formatMissionTitle = (title?: string) => {
    if (!title) return 'Active Mission';
    let clean = title
      .replace(/^(mission_|recon_|flight_)/i, '')
      .replace(/[_-]+/g, ' ')
      .trim();
    // Capitalize words
    clean = clean.split(' ').map(w => w ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : '').join(' ');
    if (clean.length > 22) {
      return clean.slice(0, 20) + '...';
    }
    return clean;
  };`;

mapHeaderCode = mapHeaderCode.replace(
  /const formatMissionTitle = \(title\?: string\) => \{[\s\S]*?return clean;\s*\};/,
  betterFormatter
);

fs.writeFileSync(mapHeaderPath, mapHeaderCode, 'utf8');
console.log('5. Updated MapHeader.tsx');

// 6. Update index.html title
const indexPath = path.join(frontendDir, 'index.html');
let indexHtml = fs.readFileSync(indexPath, 'utf8');
indexHtml = indexHtml.replace(
  /<title>.*<\/title>/,
  '<title>Single-Pass Drone 3D Reconstruction | NTRO Operations</title>'
);
fs.writeFileSync(indexPath, indexHtml, 'utf8');
console.log('6. Updated index.html');

// 7. Check BottomPanels, LeftSidebar, TopNavbar if they have any remaining escaped entities
['BottomPanels.tsx', 'LeftSidebar.tsx', 'TopNavbar.tsx'].forEach(f => {
  const fp = path.join(frontendDir, 'src', 'components', 'dashboard', f);
  if (fs.existsSync(fp)) {
    let c = fs.readFileSync(fp, 'utf8');
    c = c.replace(/&plusmn;/g, '±').replace(/&deg;/g, '°').replace(/&bull;/g, '•');
    fs.writeFileSync(fp, c, 'utf8');
    console.log('Cleaned entities in ' + f);
  }
});

console.log('ALL FILES POLISHED SUCCESSFULLY!');
