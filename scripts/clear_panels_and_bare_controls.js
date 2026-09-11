const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

const panelStyle = {
  background: 'rgba(8, 10, 14, 0.78)',
  backdropFilter: 'blur(24px) saturate(180%)',
  WebkitBackdropFilter: 'blur(24px) saturate(180%)',
  border: '1px solid rgba(255, 255, 255, 0.05)',
  boxShadow: '0 8px 28px rgba(0, 0, 0, 0.45)',
};

// 1. FleetStatusCounters.tsx - completely empty panel, no text
const p1Code = `import React from 'react';

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
      className="rounded-2xl flex flex-col shrink-0 select-none overflow-hidden flex-1 min-h-[110px] transition-all"
      style={panelStyle}
    />
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), p1Code, 'utf8');

// 2. OperationalEfficiency.tsx - completely empty panel, no text
const p2Code = `import React from 'react';

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
      className="rounded-2xl flex flex-col shrink-0 select-none overflow-hidden flex-1 min-h-[120px] transition-all"
      style={panelStyle}
    />
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), p2Code, 'utf8');

// 3. DroneUnitCard.tsx - completely empty 4 sub-panels, no text
const p3Code = `import React from 'react';

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
      {/* Row 1 */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        <div className="rounded-2xl overflow-hidden h-full" style={panelStyle} />
        <div className="rounded-2xl overflow-hidden h-full" style={panelStyle} />
      </div>

      {/* Row 2 */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        <div className="rounded-2xl overflow-hidden h-full" style={panelStyle} />
        <div className="rounded-2xl overflow-hidden h-full" style={panelStyle} />
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), p3Code, 'utf8');

// 4. ScheduleOffset.tsx - completely empty panel, no text
const p4Code = `import React from 'react';

export const ScheduleOffset: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.78)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 8px 28px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div
      className="rounded-2xl select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    />
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), p4Code, 'utf8');

// 5. PassengerVolume.tsx - bottom-right panel (will house the timeline), currently completely empty, no text
const p5Code = `import React from 'react';

export const PassengerVolume: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.78)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    boxShadow: '0 8px 28px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div
      className="rounded-2xl select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    />
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), p5Code, 'utf8');

// 6. DashboardPanels.tsx - remove background from Apple traffic lights button
const dashboardCode = `import React from 'react';
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

      {/* 3. FLOATING TITLE & DROPDOWNS: Positioned right next to top-left panel */}
      <div className="absolute top-4 left-[304px] lg:left-[320px] xl:left-[336px] z-40 pointer-events-auto">
        <MapHeader />
      </div>

      {/* 4. TOP-RIGHT ACTIONS: Upload Video + BARE Apple macOS Window Controls (NO BACKGROUND) */}
      <div className="absolute top-4 right-4 z-40 pointer-events-auto flex items-center space-x-3">
        <VideoUploadButton />

        {/* Bare traffic lights - background removed */}
        <div className="flex items-center pl-1">
          <WindowControls />
        </div>
      </div>

      {/* 5. MAIN SPATIAL WORKSPACE (Panels with zero text, ready for functional components) */}
      <div className="relative z-30 w-full h-full flex gap-3 overflow-hidden pointer-events-none">
        {/* Left Column Stack: Fills the entire vertical height from top to bottom */}
        <aside className="w-[280px] lg:w-[295px] xl:w-[310px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <DroneUnitCard />
        </aside>

        {/* Center & Right Area */}
        <section className="flex-1 h-full min-h-0 flex flex-col justify-end overflow-hidden relative">
          {/* Bottom Stage: Metric Accuracy & Reconstructed Model (Timeline) */}
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
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx'), dashboardCode, 'utf8');

console.log('✓ All text removed from panels and background removed from close button.');
