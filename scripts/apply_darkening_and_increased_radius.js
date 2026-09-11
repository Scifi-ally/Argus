const fs = require('fs');
const path = require('path');

const targetFile = path.resolve(__dirname, '../../SIHFrontend/src/components/dashboard/DashboardPanels.tsx');
let content = fs.readFileSync(targetFile, 'utf8');

// Replace the blur layer with the updated larger unblurred radius AND the outward darkening vignette
const oldBlurRegex = /\{\/\* 1\. OVAL OUTWARD BLUR EFFECT OVER MAP[\s\S]*?<\div[\s\S]*?style=\{\{[\s\S]*?\}\}\s*\/>/m;

const newEffectsCode = `{/* 1. CINEMATIC OUTWARD BLUR & DARKENING VIGNETTE
          - Center circle has an increased unblurred and brightly lit radius.
          - As it moves outwards, blur gets smoothly stronger (up to 18px).
          - Darkening effect gets progressively stronger as it moves outward toward the screen edges and panels.
      */}
      {/* Outward Progressive Blur Layer */}
      <div
        className="absolute inset-0 pointer-events-none z-10 overflow-hidden"
        style={{
          backdropFilter: 'blur(18px)',
          WebkitBackdropFilter: 'blur(18px)',
          maskImage: 'radial-gradient(circle at 56% 46%, transparent 42%, rgba(0,0,0,0.35) 66%, black 92%)',
          WebkitMaskImage: 'radial-gradient(circle at 56% 46%, transparent 42%, rgba(0,0,0,0.35) 66%, black 92%)',
        }}
      />

      {/* Outward Progressive Darkening Vignette Layer */}
      <div
        className="absolute inset-0 pointer-events-none z-10 overflow-hidden"
        style={{
          background: 'radial-gradient(circle at 56% 46%, transparent 38%, rgba(4, 7, 12, 0.35) 62%, rgba(4, 7, 12, 0.78) 85%, rgba(2, 4, 8, 0.94) 100%)',
        }}
      />`;

if (oldBlurRegex.test(content)) {
  content = content.replace(oldBlurRegex, newEffectsCode);
  fs.writeFileSync(targetFile, content, 'utf8');
  console.log('✓ Successfully replaced blur and added outward darkening vignette');
} else {
  console.log('Regex did not match directly, trying alternative replacement...');
  const searchStr = 'backdropFilter: \'blur(16px)\',';
  if (content.includes(searchStr)) {
    // Write full clean file
    const fullCode = `import React from 'react';
import { FleetStatusCounters } from './FleetStatusCounters';
import { OperationalEfficiency } from './OperationalEfficiency';
import { DroneUnitCard } from './DroneUnitCard';
import { MapHeader } from './MapHeader';
import { ScheduleOffset } from './ScheduleOffset';
import { TimelinePanel } from './TimelinePanel';
import { VideoUploadButton } from './VideoUploadButton';

export const DashboardPanels: React.FC = () => {
  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 p-4 pb-2 flex flex-col justify-between">
      {/* 1. CINEMATIC OUTWARD BLUR & DARKENING VIGNETTE
          - Center circle has an increased unblurred and brightly lit radius.
          - As it moves outwards, blur gets smoothly stronger (up to 18px).
          - Darkening effect gets progressively stronger as it moves outward toward the screen edges and panels.
      */}
      {/* Outward Progressive Blur Layer */}
      <div
        className="absolute inset-0 pointer-events-none z-10 overflow-hidden"
        style={{
          backdropFilter: 'blur(18px)',
          WebkitBackdropFilter: 'blur(18px)',
          maskImage: 'radial-gradient(circle at 56% 46%, transparent 42%, rgba(0,0,0,0.35) 66%, black 92%)',
          WebkitMaskImage: 'radial-gradient(circle at 56% 46%, transparent 42%, rgba(0,0,0,0.35) 66%, black 92%)',
        }}
      />

      {/* Outward Progressive Darkening Vignette Layer */}
      <div
        className="absolute inset-0 pointer-events-none z-10 overflow-hidden"
        style={{
          background: 'radial-gradient(circle at 56% 46%, transparent 38%, rgba(4, 7, 12, 0.35) 62%, rgba(4, 7, 12, 0.78) 85%, rgba(2, 4, 8, 0.94) 100%)',
        }}
      />

      {/* 2. FLOATING TITLE & DROPDOWNS: Top-left of map next to left sidebar */}
      <div className="absolute top-5 left-[370px] lg:left-[395px] xl:left-[415px] z-40 pointer-events-auto">
        <MapHeader />
      </div>

      {/* 3. TOP-RIGHT ACTIONS: Discreet Video Upload Button */}
      <div className="absolute top-5 right-5 z-40 pointer-events-auto flex items-center space-x-3">
        <VideoUploadButton />
      </div>

      {/* 4. MAIN SPATIAL WORKSPACE (Exact Reference Panel Layout & Shapes!) */}
      <div className="relative z-30 w-full flex-1 flex gap-3.5 overflow-hidden pointer-events-none mb-1">
        {/* LEFT COLUMN STACK:
            1. FleetStatusCounters (Two independent glass cards side-by-side)
            2. OperationalEfficiency (Spline chart card)
            3. DroneUnitCard (Exact 2x2 Grid of 4 cards with animated SVGs)
        */}
        <aside className="w-[340px] lg:w-[365px] xl:w-[385px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto overflow-hidden">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <div className="flex-1 min-h-0 overflow-hidden">
            <DroneUnitCard />
          </div>
        </aside>

        {/* BOTTOM ROW:
            1. ScheduleOffset (col-span-5)
            2. TimelinePanel (col-span-7)
        */}
        <section className="flex-1 h-full min-h-0 flex flex-col justify-end overflow-hidden relative">
          <div className="h-[175px] lg:h-[185px] xl:h-[195px] shrink-0 w-full pointer-events-auto grid grid-cols-12 gap-3.5">
            <div className="col-span-5 h-full">
              <ScheduleOffset />
            </div>
            <div className="col-span-7 h-full">
              <TimelinePanel />
            </div>
          </div>
        </section>
      </div>

      {/* 5. FOOTER STATUS BAR (At very bottom edge across screen) */}
      <div className="w-full flex items-center justify-between text-[9.5px] font-mono text-white/40 px-1 pt-1 pointer-events-none">
        <div className="flex items-center space-x-2">
          <span>NTRO Tactical UAS Reconnaissance</span>
          <span className="text-white/20">•</span>
          <span>4K Exmor Stream</span>
          <span className="text-white/20">•</span>
          <span>GPS RTK FIXED</span>
        </div>
        <div className="flex items-center space-x-2">
          <span>WGS84</span>
          <span className="text-white/20">•</span>
          <span>Single-Pass Collinearity: Valid</span>
          <span className="w-1.5 h-1.5 rounded-full bg-white inline-block shadow-[0_0_6px_#ffffff]" />
        </div>
      </div>
    </div>
  );
};

export default DashboardPanels;
`;
    fs.writeFileSync(targetFile, fullCode, 'utf8');
    console.log('✓ Successfully wrote updated DashboardPanels.tsx with full code');
  }
}
