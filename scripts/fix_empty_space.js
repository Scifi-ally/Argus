const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. FleetStatusCounters.tsx - flex-1 to fill proportional height
const fleetStatusCountersCode = `import React from 'react';

export const FleetStatusCounters: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.78)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 8px 28px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div
      className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden flex-1 min-h-[110px] transition-all"
      style={panelStyle}
    >
      {/* Panel Title */}
      <div className="flex items-center justify-between">
        <span className="text-[9.5px] font-mono tracking-wider text-white/60 uppercase font-semibold">
          Reconstruction Quality
        </span>
      </div>

      {/* Cleared of content */}
      <div className="flex-1" />
    </div>
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), fleetStatusCountersCode, 'utf8');
console.log('✓ Written FleetStatusCounters.tsx');

// 2. OperationalEfficiency.tsx - flex-1 to fill proportional height
const opEffCode = `import React from 'react';

export const OperationalEfficiency: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.78)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 8px 28px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div
      className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden flex-1 min-h-[120px] transition-all"
      style={panelStyle}
    >
      {/* Panel Title */}
      <div className="flex items-center justify-between">
        <span className="text-[9.5px] font-mono tracking-wider text-white/60 uppercase font-semibold">
          Flight Telemetry
        </span>
      </div>

      {/* Cleared of content */}
      <div className="flex-1" />
    </div>
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), opEffCode, 'utf8');
console.log('✓ Written OperationalEfficiency.tsx');

// 3. DroneUnitCard.tsx - flex-[2] with two flex-1 rows, spanning the rest of the height
const droneUnitCode = `import React from 'react';

export const DroneUnitCard: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.78)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 8px 28px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="flex flex-col gap-2.5 flex-[2] min-h-[240px] select-none">
      {/* Row 1: VIDEO CAPTURE & POSE / GPS */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        {/* Panel: Video Capture */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden h-full" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Video Capture
          </span>
          <div className="flex-1" />
        </div>

        {/* Panel: Pose / GPS */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden h-full" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Pose / GPS
          </span>
          <div className="flex-1" />
        </div>
      </div>

      {/* Row 2: SCENE UNDERSTANDING & RECONSTRUCTION PIPELINE */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        {/* Panel: Scene Understanding */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden h-full" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Scene Understanding
          </span>
          <div className="flex-1" />
        </div>

        {/* Panel: Reconstruction Pipeline */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden h-full" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Reconstruction Pipeline
          </span>
          <div className="flex-1" />
        </div>
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), droneUnitCode, 'utf8');
console.log('✓ Written DroneUnitCard.tsx');

// 4. DashboardPanels.tsx - adjust left column and bottom stage to perfectly balance and eliminate all empty space
const dashboardPanelsCode = `import React from 'react';
import { FleetStatusCounters } from './FleetStatusCounters';
import { OperationalEfficiency } from './OperationalEfficiency';
import { DroneUnitCard } from './DroneUnitCard';
import { MapHeader } from './MapHeader';
import { VideoUploadButton } from './VideoUploadButton';
import { ScheduleOffset } from './ScheduleOffset';
import { PassengerVolume } from './PassengerVolume';
import { WindowControls } from '../common/WindowControls';

export const DashboardPanels: React.FC = () => {
  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 p-4 flex flex-col justify-between">
      {/* 1. CINEMATIC RADIAL BLUR FOCUSING ON SATELLITE CENTER */}
      <div
        className="absolute inset-0 w-full h-full pointer-events-none z-10"
        style={{
          backdropFilter: 'blur(3px)',
          WebkitBackdropFilter: 'blur(3px)',
          maskImage:
            'radial-gradient(circle 360px at 50% 50%, transparent 0%, transparent 35%, black 80%)',
          WebkitMaskImage:
            'radial-gradient(circle 360px at 50% 50%, transparent 0%, transparent 35%, black 80%)',
        }}
      />
      <div
        className="absolute inset-0 w-full h-full pointer-events-none z-10"
        style={{
          background:
            'radial-gradient(circle 800px at 50% 50%, rgba(2, 4, 8, 0.0) 25%, rgba(2, 4, 8, 0.3) 55%, rgba(1, 2, 4, 0.75) 100%)',
        }}
      />

      {/* 2. CENTRAL TACTICAL DISK RETICLE */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-20 flex items-center justify-center">
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center shadow-2xl"
          style={{
            background: 'rgba(10, 14, 20, 0.65)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M 9 2 L 15 15 L 9 12 L 3 15 Z"
              fill="#FFFFFF"
            />
          </svg>
        </div>
      </div>

      {/* 3. FLOATING TITLE & DROPDOWNS: Positioned right next to RECONSTRUCTION QUALITY */}
      <div className="absolute top-4 left-[304px] lg:left-[320px] xl:left-[336px] z-40 pointer-events-auto">
        <MapHeader />
      </div>

      {/* 4. TOP-RIGHT ACTIONS: Upload Video + Apple macOS Controls */}
      <div className="absolute top-4 right-4 z-40 pointer-events-auto flex items-center space-x-2.5">
        <VideoUploadButton />

        <div
          className="rounded-full px-2.5 py-1.5 flex items-center shadow-md ml-1"
          style={{
            background: 'rgba(8, 10, 14, 0.75)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <WindowControls />
        </div>
      </div>

      {/* 5. MAIN SPATIAL WORKSPACE (Zero empty space! Panels fill the full vertical height seamlessly) */}
      <div className="relative z-30 w-full h-full flex gap-3 overflow-hidden pointer-events-none">
        {/* Left Column Stack: Fills the entire vertical height from top to bottom */}
        <aside className="w-[280px] lg:w-[295px] xl:w-[310px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <DroneUnitCard />
        </aside>

        {/* Center & Right Area */}
        <section className="flex-1 h-full min-h-0 flex flex-col justify-end overflow-hidden relative">
          {/* Bottom Stage: Metric Accuracy & Reconstructed Model */}
          <div className="h-[140px] lg:h-[150px] xl:h-[160px] shrink-0 w-full pointer-events-auto grid grid-cols-12 gap-3">
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
console.log('✓ Written DashboardPanels.tsx');

console.log('All layout updates applied!');
