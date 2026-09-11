const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// Consistent panel background matching the reference image:
// Sleek dark obsidian glass, soft blur, subtle border
const panelStyle = {
  background: 'rgba(8, 10, 14, 0.78)',
  backdropFilter: 'blur(24px) saturate(180%)',
  WebkitBackdropFilter: 'blur(24px) saturate(180%)',
  border: '1px solid rgba(255, 255, 255, 0.05)',
  boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)',
};

// 1. MapHeader.tsx - Exact matching reference image
const mapHeaderCode = `import React, { useState } from 'react';
import { ChevronDown, Check, Crosshair, Box } from 'lucide-react';
import { useMission } from '../../state/missionStore';
import { formatMissionTitle } from '../../utils/formatters';

export const MapHeader: React.FC = () => {
  const { mission, availableMissions, selectMission } = useMission();
  const [isMissionDropdownOpen, setIsMissionDropdownOpen] = useState(false);
  const [isLayerDropdownOpen, setIsLayerDropdownOpen] = useState(false);
  const [activeLayer, setActiveLayer] = useState('OBJ');

  const rawTitle = mission?.name || (availableMissions.length > 0 ? availableMissions[0].name : 'UAV Pass 6023');
  const displayTitle = formatMissionTitle(rawTitle);

  const pillStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.65)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.06)',
  };

  const menuStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.95)',
    backdropFilter: 'blur(28px)',
    WebkitBackdropFilter: 'blur(28px)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    boxShadow: '0 16px 40px rgba(0,0,0,0.8)',
  };

  return (
    <div className="flex flex-col space-y-1.5 pointer-events-auto select-none">
      {/* Title */}
      <h1 className="text-[22px] font-extralight tracking-tight text-white leading-none">
        Single-Pass 3D Reconstruction
      </h1>

      {/* Sub-header dropdowns exactly matching reference image */}
      <div className="flex items-center space-x-2 pt-0.5">
        {/* Mission Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsMissionDropdownOpen(!isMissionDropdownOpen);
              setIsLayerDropdownOpen(false);
            }}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-[10.5px] text-white/80 hover:text-white transition-all cursor-pointer font-mono"
            style={pillStyle}
          >
            <Crosshair className="w-3 h-3 text-white/70" />
            <span className="font-medium max-w-[160px] truncate">{displayTitle}</span>
            <ChevronDown className="w-3 h-3 text-white/40" />
          </button>

          {isMissionDropdownOpen && (
            <div className="absolute top-8 left-0 w-64 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {availableMissions.map((m) => (
                <div
                  key={m.id}
                  onClick={() => {
                    selectMission(m.id);
                    setIsMissionDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white/90 flex justify-between items-center"
                >
                  <span className="truncate">{formatMissionTitle(m.name || m.id)}</span>
                  {mission?.id === m.id && <Check className="w-3 h-3 text-white" />}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Format Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsLayerDropdownOpen(!isLayerDropdownOpen);
              setIsMissionDropdownOpen(false);
            }}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-[10.5px] text-white/80 hover:text-white transition-all cursor-pointer font-mono"
            style={pillStyle}
          >
            <Box className="w-3 h-3 text-white/70" />
            <span className="font-medium">{activeLayer}</span>
            <ChevronDown className="w-3 h-3 text-white/40" />
          </button>

          {isLayerDropdownOpen && (
            <div className="absolute top-8 left-0 w-36 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {['OBJ', 'GLB 3D', 'Point Cloud', 'Mesh'].map((fmt) => (
                <div
                  key={fmt}
                  onClick={() => {
                    setActiveLayer(fmt);
                    setIsLayerDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white/90 flex justify-between items-center"
                >
                  <span>{fmt}</span>
                  {activeLayer === fmt && <Check className="w-3 h-3 text-white" />}
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
console.log('✓ Written MapHeader.tsx');

// 2. FleetStatusCounters.tsx - RECONSTRUCTION QUALITY (Panel shell only, cleared of content)
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
      className="rounded-2xl p-3 flex flex-col justify-between shrink-0 select-none overflow-hidden h-[105px] transition-all"
      style={panelStyle}
    >
      {/* Panel Title Header Only */}
      <div className="flex items-center justify-between">
        <span className="text-[9.5px] font-mono tracking-wider text-white/60 uppercase font-semibold">
          Reconstruction Quality
        </span>
      </div>

      {/* Cleared of content per user instruction */}
      <div className="flex-1" />
    </div>
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), fleetStatusCountersCode, 'utf8');
console.log('✓ Written FleetStatusCounters.tsx (panel only, content cleared)');

// 3. OperationalEfficiency.tsx - FLIGHT TELEMETRY (Panel shell only, cleared of content)
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
      className="rounded-2xl p-3 flex flex-col justify-between shrink-0 select-none overflow-hidden h-[120px] transition-all"
      style={panelStyle}
    >
      {/* Panel Title Header Only */}
      <div className="flex items-center justify-between">
        <span className="text-[9.5px] font-mono tracking-wider text-white/60 uppercase font-semibold">
          Flight Telemetry
        </span>
      </div>

      {/* Cleared of content per user instruction */}
      <div className="flex-1" />
    </div>
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), opEffCode, 'utf8');
console.log('✓ Written OperationalEfficiency.tsx (panel only, content cleared)');

// 4. DroneUnitCard.tsx - The 4 Sub-Panels: VIDEO CAPTURE, POSE / GPS, SCENE UNDERSTANDING, RECONSTRUCTION PIPELINE
// (Panels copied from reference image, cleared of content)
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
    <div className="flex flex-col gap-2.5 flex-1 min-h-0 select-none">
      {/* Row 1: VIDEO CAPTURE & POSE / GPS */}
      <div className="grid grid-cols-2 gap-2.5 h-[115px]">
        {/* Panel: Video Capture */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Video Capture
          </span>
          {/* Cleared of content */}
          <div className="flex-1" />
        </div>

        {/* Panel: Pose / GPS */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Pose / GPS
          </span>
          {/* Cleared of content */}
          <div className="flex-1" />
        </div>
      </div>

      {/* Row 2: SCENE UNDERSTANDING & RECONSTRUCTION PIPELINE */}
      <div className="grid grid-cols-2 gap-2.5 h-[115px]">
        {/* Panel: Scene Understanding */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Scene Understanding
          </span>
          {/* Cleared of content */}
          <div className="flex-1" />
        </div>

        {/* Panel: Reconstruction Pipeline */}
        <div className="rounded-2xl p-3 flex flex-col justify-between overflow-hidden" style={panelStyle}>
          <span className="text-[9px] font-mono tracking-wider text-white/60 uppercase font-semibold">
            Reconstruction Pipeline
          </span>
          {/* Cleared of content */}
          <div className="flex-1" />
        </div>
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), droneUnitCode, 'utf8');
console.log('✓ Written DroneUnitCard.tsx (4 panels, content cleared)');

// 5. ScheduleOffset.tsx - METRIC ACCURACY (Panel shell only, cleared of content)
const scheduleOffsetCode = `import React from 'react';

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
      className="rounded-2xl p-3.5 flex flex-col justify-between select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Panel Title Header Only */}
      <div className="flex items-center justify-between">
        <span className="text-[9.5px] font-mono tracking-wider text-white/60 uppercase font-semibold">
          Metric Accuracy
        </span>
      </div>

      {/* Cleared of content per user instruction */}
      <div className="flex-1" />
    </div>
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), scheduleOffsetCode, 'utf8');
console.log('✓ Written ScheduleOffset.tsx (panel only, content cleared)');

// 6. PassengerVolume.tsx - RECONSTRUCTED MODEL (Panel shell only, cleared of content)
const passengerVolumeCode = `import React from 'react';

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
      className="rounded-2xl p-3.5 flex flex-col justify-between select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    >
      {/* Panel Title Header Only */}
      <div className="flex items-center justify-between">
        <span className="text-[9.5px] font-mono tracking-wider text-white/60 uppercase font-semibold">
          Reconstructed Model
        </span>
      </div>

      {/* Cleared of content per user instruction */}
      <div className="flex-1" />
    </div>
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), passengerVolumeCode, 'utf8');
console.log('✓ Written PassengerVolume.tsx (panel only, content cleared)');

// 7. VideoUploadButton.tsx - Exact button matching reference image
const videoUploadButtonCode = `import React, { useRef } from 'react';
import { UploadCloud, Loader2 } from 'lucide-react';
import { useMission } from '../../state/missionStore';

export const VideoUploadButton: React.FC = () => {
  const { missionState, uploadProgress, uploadVideo } = useMission();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadVideo(file);
      e.target.value = '';
    }
  };

  const isUploading = missionState === 'UPLOADING';

  const buttonStyle: React.CSSProperties = {
    background: 'rgba(8, 10, 14, 0.75)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
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

      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading}
        className="flex items-center space-x-2 px-3.5 py-1.5 rounded-full text-[11px] text-white/90 hover:text-white active:scale-[0.98] transition-all cursor-pointer font-sans"
        style={buttonStyle}
      >
        {isUploading ? (
          <>
            <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
            <span className="font-mono text-[10px]">
              Uploading {uploadProgress ? \`\${uploadProgress.percent}%\` : '...'}
            </span>
          </>
        ) : (
          <>
            <UploadCloud className="w-3.5 h-3.5 text-white/80" />
            <span>Upload Video</span>
          </>
        )}
      </button>
    </div>
  );
};

export default VideoUploadButton;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/VideoUploadButton.tsx'), videoUploadButtonCode, 'utf8');
console.log('✓ Written VideoUploadButton.tsx');

// 8. DashboardPanels.tsx - Spatial layout matching reference image
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
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 flex flex-col justify-between p-4">
      {/* 1. CINEMATIC RADIAL BLUR FOCUSING ON SATELLITE CENTER (as in reference image) */}
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

      {/* 2. CENTRAL TACTICAL DISK RETICLE (from reference image) */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-20 flex items-center justify-center">
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center shadow-2xl"
          style={{
            background: 'rgba(10, 14, 20, 0.65)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          {/* Centered White Arrow Pointer */}
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M 9 2 L 15 15 L 9 12 L 3 15 Z"
              fill="#FFFFFF"
              filter="drop-shadow(0 1px 4px rgba(0,0,0,0.8))"
            />
          </svg>
        </div>
      </div>

      {/* 3. TOP REGION: Floating Title + Top-Right Upload & Apple Window Controls */}
      <div className="w-full flex items-start justify-between z-40 pointer-events-none mb-2">
        {/* Top-Center-Left Title & Dropdowns */}
        <div className="pointer-events-auto pl-2">
          <MapHeader />
        </div>

        {/* Top-Right: Upload Video Button + Apple macOS Controls */}
        <div className="pointer-events-auto flex items-center space-x-2.5">
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
      </div>

      {/* 4. MAIN SPATIAL WORKSPACE (Panels matching reference image) */}
      <div className="relative z-30 flex-1 min-h-0 flex gap-3 overflow-hidden pointer-events-none">
        {/* Left Column Stack (Cards copied from reference image, cleared of content) */}
        <aside className="w-[280px] lg:w-[295px] xl:w-[310px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto overflow-y-auto">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <DroneUnitCard />
        </aside>

        {/* Center & Right Area */}
        <section className="flex-1 h-full min-h-0 flex flex-col justify-end overflow-hidden relative">
          {/* Bottom Stage: Metric Accuracy & Reconstructed Model (cleared of content) */}
          <div className="h-[120px] lg:h-[125px] xl:h-[130px] shrink-0 w-full pt-1 pointer-events-auto grid grid-cols-12 gap-3">
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

console.log('Panels copied and cleared of content successfully!');
