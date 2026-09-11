const fs = require('fs');
const path = require('path');

const file = path.resolve(__dirname, '../../SIHFrontend/src/components/dashboard/DashboardPanels.tsx');

const code = `import React from 'react';
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

      {/* 5. MAIN SPATIAL WORKSPACE (Full height with left panels starting from top) */}
      <div className="relative z-30 w-full h-full flex gap-3 overflow-hidden pointer-events-none">
        {/* Left Column Stack: Starts at the very top */}
        <aside className="w-[280px] lg:w-[295px] xl:w-[310px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto overflow-y-auto">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <DroneUnitCard />
        </aside>

        {/* Center & Right Area */}
        <section className="flex-1 h-full min-h-0 flex flex-col justify-end overflow-hidden relative">
          {/* Bottom Stage: Metric Accuracy & Reconstructed Model */}
          <div className="h-[120px] lg:h-[125px] xl:h-[130px] shrink-0 w-full pointer-events-auto grid grid-cols-12 gap-3">
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

fs.writeFileSync(file, code, 'utf8');
console.log('Successfully updated DashboardPanels.tsx with title moved next to top-left panel');
