const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. FleetStatusCounters.tsx
const fleetCountersCode = `import React, { useState } from 'react';

export const FleetStatusCounters: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'bus' | 'taxi' | 'trains' | 'trams'>('bus');

  const tabs = [
    { id: 'bus', label: '24 Bus' },
    { id: 'taxi', label: '100 Taxi' },
    { id: 'trains', label: '12 Trains' },
    { id: 'trams', label: '13 Trams' },
  ] as const;

  const panelStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '16px',
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.45)',
  };

  const cardStyle: React.CSSProperties = {
    background: 'rgba(19, 24, 32, 0.75)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    borderRadius: '12px',
  };

  return (
    <div className="flex flex-col select-none p-3 transition-all space-y-2.5 shrink-0" style={panelStyle}>
      {/* 4 Category Pill Tabs */}
      <div className="flex items-center bg-black/45 p-1 rounded-full border border-white/[0.06] text-[11px]">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={\`flex-1 py-1 px-1.5 rounded-full font-medium transition-all text-center cursor-pointer \${
                isActive
                  ? 'bg-white/15 text-white shadow-sm font-semibold'
                  : 'text-white/45 hover:text-white/80'
              }\`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Two Stat Cards: Online 12 & Offline 4 */}
      <div className="grid grid-cols-2 gap-2.5">
        {/* Online Stat Card */}
        <div className="p-3 flex items-center justify-between" style={cardStyle}>
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#22c55e] shadow-[0_0_8px_#22c55e]" />
            <span className="text-[12px] text-white/90 font-medium">Online</span>
          </div>
          <span className="text-[28px] font-light tracking-tight text-white leading-none font-mono">
            12
          </span>
        </div>

        {/* Offline Stat Card */}
        <div className="p-3 flex items-center justify-between" style={cardStyle}>
          <div className="flex items-center space-x-2">
            <span className="text-[10px] text-[#ef4444] font-bold">▲</span>
            <span className="text-[12px] text-white/90 font-medium">Offline</span>
          </div>
          <span className="text-[28px] font-light tracking-tight text-white leading-none font-mono">
            4
          </span>
        </div>
      </div>
    </div>
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), fleetCountersCode, 'utf8');
console.log('✓ Written components/dashboard/FleetStatusCounters.tsx');

// 2. OperationalEfficiency.tsx
const opEffCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';

export const OperationalEfficiency: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '16px',
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden transition-all" style={panelStyle}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-white/90">
          Operational Efficiency
        </span>
        <ArrowUpRight className="w-4 h-4 text-white/50 hover:text-white transition-colors cursor-pointer" />
      </div>

      {/* Main Metric: 78.3 % + Target Label */}
      <div className="flex items-baseline space-x-1.5 my-1">
        <span className="text-[34px] font-light tracking-tight text-white leading-none font-mono">
          78.3
        </span>
        <span className="text-[16px] font-light text-white/80 font-mono">%</span>
      </div>
      <div className="text-[10px] font-mono text-white/40 -mt-1 mb-1">
        Target
      </div>

      {/* Spline Area Chart with Target Dashed Line */}
      <div className="relative w-full h-[95px] my-1">
        {/* Target threshold indicator */}
        <div className="absolute top-[20%] right-0 flex items-center space-x-1 z-10">
          <span className="text-[9px] font-mono text-white/50">&gt;80%</span>
        </div>

        <svg className="w-full h-full overflow-visible" viewBox="0 0 320 90" preserveAspectRatio="none">
          <defs>
            <linearGradient id="splineGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="barShading" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0.01" />
            </linearGradient>
          </defs>

          {/* Horizontal Target Line (>80%) */}
          <line
            x1="0"
            y1="22"
            x2="285"
            y2="22"
            stroke="rgba(255, 255, 255, 0.16)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />

          {/* Vertical highlight band at peak (18:00 - 21:00) */}
          <rect x="220" y="24" width="40" height="66" fill="url(#barShading)" rx="2" />

          {/* Spline Area Fill */}
          <path
            d="M 10 65 
               C 35 72, 45 76, 60 74 
               C 85 70, 110 50, 135 48 
               C 160 46, 185 64, 210 52 
               C 225 40, 235 24, 250 25 
               C 265 26, 280 50, 305 48 
               L 305 90 L 10 90 Z"
            fill="url(#splineGradient)"
          />

          {/* Spline Stroke Line */}
          <path
            d="M 10 65 
               C 35 72, 45 76, 60 74 
               C 85 70, 110 50, 135 48 
               C 160 46, 185 64, 210 52 
               C 225 40, 235 24, 250 25 
               C 265 26, 280 50, 305 48"
            fill="none"
            stroke="#f59e0b"
            strokeWidth="1.8"
          />

          {/* Orange dots on key peaks */}
          <circle cx="60" cy="74" r="2.5" fill="#f59e0b" stroke="#000" strokeWidth="1" />
          <circle cx="135" cy="48" r="2.5" fill="#f59e0b" stroke="#000" strokeWidth="1" />
          <circle cx="210" cy="52" r="2.5" fill="#ffffff" stroke="#f59e0b" strokeWidth="1.5" />
          <circle cx="250" cy="25" r="3" fill="#ffffff" stroke="#f59e0b" strokeWidth="1.5" />
        </svg>

        {/* Y Axis percentage markers on the right */}
        <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between text-[8px] font-mono text-white/35 pointer-events-none">
          <span>100%</span>
          <span>75%</span>
          <span>50%</span>
          <span>25%</span>
        </div>
      </div>

      {/* X Axis Time Labels */}
      <div className="flex justify-between items-center text-[9px] font-mono text-white/40 pt-1 border-t border-white/[0.06]">
        <span>06:00</span>
        <span>09:00</span>
        <span>12:00</span>
        <span>15:00</span>
        <span>18:00</span>
        <span>21:00</span>
      </div>
    </div>
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), opEffCode, 'utf8');
console.log('✓ Written components/dashboard/OperationalEfficiency.tsx');

// 3. DroneUnitCard.tsx (2x2 Grid of 4 cards)
const droneUnitCode = `import React from 'react';
import { ArrowUpRight, Wifi } from 'lucide-react';

export const DroneUnitCard: React.FC = () => {
  const cardStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '16px',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
  };

  return (
    <div className="grid grid-cols-2 gap-2.5 h-full min-h-[290px] select-none">
      {/* 1. Bus 6023 */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-medium text-white">Bus 6023</span>
            <ArrowUpRight className="w-3.5 h-3.5 text-white/45 hover:text-white cursor-pointer" />
          </div>
          <div className="text-[8px] font-mono text-white/40 mt-0.5">
            10.03.2025, 08:35:55 AM
          </div>
        </div>

        {/* Bus Blueprint Vector Wireframe */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[110px] h-[34px]" viewBox="0 0 140 44">
            {/* Bus Body */}
            <rect x="12" y="6" width="116" height="32" rx="6" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
            {/* Windshield */}
            <line x1="28" y1="6" x2="28" y2="38" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
            {/* Side Mirrors */}
            <rect x="6" y="8" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            <rect x="6" y="30" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            {/* Roof Vents / Units */}
            <rect x="36" y="11" width="34" height="22" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" />
            <rect x="76" y="11" width="44" height="22" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" />
            {/* Center Tag Pill */}
            <rect x="80" y="17" width="36" height="10" rx="3" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.3)" strokeWidth="0.6" />
            <text x="98" y="24.5" fill="#fff" fontSize="6.5" fontFamily="monospace" textAnchor="middle">6023</text>
            <circle cx="85" cy="22" r="2" fill="none" stroke="#fff" strokeWidth="0.6" />
            <text x="85" y="23.5" fill="#fff" fontSize="4.5" fontFamily="monospace" textAnchor="middle">L</text>
          </svg>
        </div>

        {/* Badges: Online, GPS, LTE */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/60 pt-1 border-t border-white/[0.06]">
          <span className="text-[#22c55e] font-semibold flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block mr-1" />
            Online
          </span>
          <span>1rd GPS</span>
          <span className="flex items-center"><Wifi className="w-2.5 h-2.5 mr-0.5" /> LTE</span>
        </div>

        {/* Mini route isometric graph */}
        <div className="relative pt-1">
          <svg className="w-full h-[22px]" viewBox="0 0 120 22">
            <path d="M 10 18 L 45 10 L 60 18 L 85 4" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
            <circle cx="10" cy="18" r="2" fill="#fff" />
            <circle cx="85" cy="4" r="2.5" fill="#22c55e" />
          </svg>
          <div className="flex justify-between text-[7px] font-mono text-white/35">
            <span>06AM</span>
            <span>11PM</span>
          </div>
        </div>
      </div>

      {/* 2. Bus 4120 */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-medium text-white">Bus 4120</span>
            <ArrowUpRight className="w-3.5 h-3.5 text-white/45 hover:text-white cursor-pointer" />
          </div>
          <div className="text-[8px] font-mono text-white/40 mt-0.5">
            10.03.2025, 10:22:18
          </div>
        </div>

        {/* Bus Blueprint Vector Wireframe */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[110px] h-[34px]" viewBox="0 0 140 44">
            <rect x="12" y="6" width="116" height="32" rx="6" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
            <line x1="28" y1="6" x2="28" y2="38" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
            <rect x="6" y="8" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            <rect x="6" y="30" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            <rect x="36" y="11" width="40" height="22" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" />
            <rect x="80" y="11" width="40" height="22" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" />
            <rect x="42" y="17" width="34" height="10" rx="3" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.3)" strokeWidth="0.6" />
            <text x="59" y="24.5" fill="#fff" fontSize="6.5" fontFamily="monospace" textAnchor="middle">4120</text>
            <circle cx="48" cy="22" r="2" fill="none" stroke="#fff" strokeWidth="0.6" />
            <text x="48" y="23.5" fill="#fff" fontSize="4.5" fontFamily="monospace" textAnchor="middle">L</text>
          </svg>
        </div>

        {/* Badges: Online, GPS, LTE */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/60 pt-1 border-t border-white/[0.06]">
          <span className="text-[#22c55e] font-semibold flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block mr-1" />
            Online
          </span>
          <span>1rd GPS</span>
          <span className="flex items-center"><Wifi className="w-2.5 h-2.5 mr-0.5" /> LTE</span>
        </div>

        {/* Mini route isometric graph */}
        <div className="relative pt-1">
          <svg className="w-full h-[22px]" viewBox="0 0 120 22">
            <path d="M 20 18 L 50 8 L 70 14 L 105 6" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
            <circle cx="20" cy="18" r="2" fill="#fff" />
            <circle cx="70" cy="14" r="2.5" fill="#22c55e" />
          </svg>
          <div className="flex justify-between text-[7px] font-mono text-white/35">
            <span>05AM</span>
            <span>09PM</span>
          </div>
        </div>
      </div>

      {/* 3. Bus 2209 */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-medium text-white">Bus 2209</span>
            <ArrowUpRight className="w-3.5 h-3.5 text-white/45 hover:text-white cursor-pointer" />
          </div>
          <div className="text-[8px] font-mono text-white/40 mt-0.5">
            10.03.2025, 11:26:40
          </div>
        </div>

        {/* Bus Blueprint Vector Wireframe */}
        <div className="w-full flex items-center justify-center my-1.5">
          <svg className="w-[110px] h-[34px]" viewBox="0 0 140 44">
            <rect x="12" y="6" width="116" height="32" rx="6" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
            <line x1="28" y1="6" x2="28" y2="38" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
            <rect x="6" y="8" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            <rect x="6" y="30" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            <rect x="36" y="11" width="34" height="22" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" />
            <rect x="76" y="11" width="44" height="22" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="0.8" />
            <rect x="52" y="17" width="36" height="10" rx="3" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.3)" strokeWidth="0.6" />
            <text x="70" y="24.5" fill="#fff" fontSize="6.5" fontFamily="monospace" textAnchor="middle">2209</text>
            <circle cx="58" cy="22" r="2" fill="none" stroke="#fff" strokeWidth="0.6" />
            <text x="58" y="23.5" fill="#fff" fontSize="4.5" fontFamily="monospace" textAnchor="middle">L</text>
          </svg>
        </div>

        {/* Badges: Online, GPS, LTE */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/60 pt-1 border-t border-white/[0.06]">
          <span className="text-[#22c55e] font-semibold flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block mr-1" />
            Online
          </span>
          <span>1rd GPS</span>
          <span className="flex items-center"><Wifi className="w-2.5 h-2.5 mr-0.5" /> LTE</span>
        </div>
      </div>

      {/* 4. E-Bus 07 */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-medium text-white">E-Bus 07</span>
            <ArrowUpRight className="w-3.5 h-3.5 text-white/45 hover:text-white cursor-pointer" />
          </div>
          <div className="text-[8px] font-mono text-white/40 mt-0.5">
            10.03.2025, 11:29:32
          </div>
        </div>

        {/* Bus Blueprint Vector Wireframe with highlighted orange doors */}
        <div className="w-full flex items-center justify-center my-1.5">
          <svg className="w-[110px] h-[34px]" viewBox="0 0 140 44">
            <rect x="12" y="6" width="116" height="32" rx="6" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
            <line x1="28" y1="6" x2="28" y2="38" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
            <rect x="6" y="8" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            <rect x="6" y="30" width="4" height="6" rx="1" fill="rgba(255,255,255,0.4)" />
            {/* Highlighted Orange Door Openings */}
            <rect x="36" y="34" width="14" height="4" fill="#f59e0b" rx="1" />
            <rect x="86" y="34" width="14" height="4" fill="#f59e0b" rx="1" />
            <text x="68" y="24.5" fill="#fff" fontSize="6.5" fontFamily="monospace" textAnchor="middle">07</text>
          </svg>
        </div>

        {/* Badges: Online, GPS, LTE */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/60 pt-1 border-t border-white/[0.06]">
          <span className="text-[#22c55e] font-semibold flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block mr-1" />
            Online
          </span>
          <span>1rd GPS</span>
          <span className="flex items-center"><Wifi className="w-2.5 h-2.5 mr-0.5" /> LTE</span>
        </div>
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), droneUnitCode, 'utf8');
console.log('✓ Written components/dashboard/DroneUnitCard.tsx');

// 4. ScheduleOffset.tsx
const schedOffsetCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';

export const ScheduleOffset: React.FC = () => {
  const panelStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '16px',
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-4" style={panelStyle}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-white/90">
          Schedule Offset
        </span>
        <ArrowUpRight className="w-4 h-4 text-white/50 hover:text-white cursor-pointer" />
      </div>

      {/* Main Metric */}
      <div className="flex items-baseline space-x-2 my-1">
        <span className="text-[32px] font-light tracking-tight text-white leading-none font-mono">
          &plusmn; 2.5
        </span>
        <span className="text-[14px] font-light text-white/70 font-mono">min</span>
        <span className="text-[10.5px] font-mono text-white/40 ml-2">Average Variance</span>
      </div>

      {/* Variance Table */}
      <div className="w-full flex flex-col text-[11px] font-mono mt-1">
        {/* Table Header Row */}
        <div className="grid grid-cols-6 gap-2 text-white/40 text-[9px] pb-1 border-b border-white/[0.06]">
          <span className="col-span-1">Route number</span>
          <span className="text-center">L1</span>
          <span className="text-center">L2</span>
          <span className="text-center">L3</span>
          <span className="text-center">L5</span>
          <span className="text-center">L24</span>
        </div>

        {/* Row 1: > 46023 */}
        <div className="grid grid-cols-6 gap-2 py-1.5 items-center text-white/80 border-b border-white/[0.04]">
          <span className="col-span-1 flex items-center space-x-1 text-white/90 font-medium">
            <span className="text-white/40 text-[9px]">&gt;</span>
            <span>46023</span>
          </span>
          <span className="text-center text-white/60 border-l border-white/[0.06]">-2min</span>
          <span className="text-center text-[#f59e0b] border-l border-white/[0.06]">+1min</span>
          <span className="text-center text-white/60 border-l border-white/[0.06]">+0min</span>
          <span className="text-center text-white/60 border-l border-white/[0.06]">-1.5min</span>
          <span className="text-center text-[#f59e0b] border-l border-white/[0.06]">+2min</span>
        </div>

        {/* Row 2: > 34654 */}
        <div className="grid grid-cols-6 gap-2 py-1.5 items-center text-white/80">
          <span className="col-span-1 flex items-center space-x-1 text-white/90 font-medium">
            <span className="text-white/40 text-[9px]">&gt;</span>
            <span>34654</span>
          </span>
          <span className="text-center text-white/60 border-l border-white/[0.06]">-3min</span>
          <span className="text-center text-white/60 border-l border-white/[0.06]">-2min</span>
          <span className="text-center text-[#f59e0b] border-l border-white/[0.06]">+1min</span>
          <span className="text-center text-white/60 border-l border-white/[0.06]">-2.5min</span>
          <span className="text-center text-[#f59e0b] border-l border-white/[0.06]">+2min</span>
        </div>
      </div>
    </div>
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), schedOffsetCode, 'utf8');
console.log('✓ Written components/dashboard/ScheduleOffset.tsx');

// 5. PassengerVolume.tsx (Replicating exact Live Passenger Volume + seamlessly integrated timeline playback controls)
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
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '16px',
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.45)',
  };

  const bars = [
    { height: 68, label: '55k', delta: '+8%', deltaColor: '#22c55e' },
    { height: 75, label: '57k', delta: '-3%', deltaColor: '#ef4444' },
    { height: 71, label: '56k', delta: '+6%', deltaColor: '#22c55e' },
    { height: 68, label: '55k', delta: '-1%', deltaColor: '#ef4444' },
    { height: 60, label: '52k', delta: '-10%', deltaColor: '#ef4444' },
    { height: 62, label: '52k', delta: '+2%', deltaColor: '#22c55e' },
    { height: 63, label: '52k', delta: '+4%', deltaColor: '#22c55e' },
  ];

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return \`\${m.toString().padStart(2, '0')}:\${s.toString().padStart(2, '0')}\`;
  };

  return (
    <div className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-4" style={panelStyle}>
      {/* Header with Live Passenger Volume and Playback Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span className="text-[13px] font-medium text-white/90">
            Live Passenger Volume
          </span>
          <ArrowUpRight className="w-4 h-4 text-white/50 hover:text-white cursor-pointer" />
        </div>

        {/* Functional Timeline Controls embedded cleanly */}
        <div className="flex items-center space-x-2">
          {/* Play/Pause Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/10 hover:bg-white/20 text-white text-[10px] font-mono cursor-pointer transition-all active:scale-95"
          >
            {isPlaying ? <Pause className="w-3 h-3 text-emerald-400 fill-emerald-400" /> : <Play className="w-3 h-3 text-white fill-white" />}
            <span>{isPlaying ? 'PAUSE' : 'START'}</span>
          </button>

          {/* Time indicator */}
          <span className="text-[10px] font-mono text-white/50">
            {formatTime(currentSeconds)} / {formatTime(totalSeconds || 30)}
          </span>

          {/* Speed Toggle */}
          <button
            type="button"
            onClick={() => setSpeed(playbackSpeed === 1 ? 2 : playbackSpeed === 2 ? 4 : 1)}
            className="px-1.5 py-0.5 rounded bg-white/[0.06] text-[9px] font-mono text-white/60 hover:text-white"
          >
            {playbackSpeed}x
          </button>
        </div>
      </div>

      {/* Main Metric */}
      <div className="flex items-baseline space-x-2 my-0.5">
        <span className="text-[32px] font-light tracking-tight text-white leading-none font-mono">
          142,580
        </span>
        <span className="text-[11px] font-mono text-white/45">today</span>
      </div>

      {/* Histogram Bar Chart */}
      <div className="relative w-full h-[52px] flex items-end justify-between px-2">
        {bars.map((b, i) => (
          <div key={i} className="flex flex-col items-center space-y-1 flex-1">
            {/* Percentage & value tag above bar */}
            <div className="flex items-center space-x-0.5 text-[8px] font-mono leading-none">
              <span className="text-white/60">{b.label}</span>
              <span style={{ color: b.deltaColor }}>{b.delta}</span>
            </div>
            {/* Bar */}
            <div
              className="w-[14px] lg:w-[18px] rounded-t-sm bg-white/15 hover:bg-white/25 transition-all"
              style={{ height: \`\${b.height * 0.45}px\` }}
            />
          </div>
        ))}

        {/* Right Y-axis markers */}
        <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between text-[7.5px] font-mono text-white/35 pointer-events-none">
          <span>60k</span>
          <span>0k</span>
        </div>
      </div>

      {/* Scrubbing Track & Time Axis */}
      <div className="relative w-full pt-1">
        {/* Scrubbing Line */}
        <div className="relative w-full h-1 bg-white/10 rounded-full cursor-pointer overflow-hidden">
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

        {/* X Axis Time Labels */}
        <div className="flex justify-between text-[8px] font-mono text-white/35 pt-1">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      </div>
    </div>
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), passVolCode, 'utf8');
console.log('✓ Written components/dashboard/PassengerVolume.tsx');

// 6. MapHeader.tsx (Matching reference image top-left "Traffic Management [ Bus 6023 ▾ ] [ Map 2 ▾ ]")
const mapHeaderCode = `import React, { useState } from 'react';
import { ChevronDown, Check, Bus, Map as MapIcon } from 'lucide-react';
import { useMission } from '../../state/missionStore';

export const MapHeader: React.FC = () => {
  const { availableMissions, selectMission } = useMission();
  const [selectedVehicle, setSelectedVehicle] = useState('Bus 6023');
  const [isBusDropdownOpen, setIsBusDropdownOpen] = useState(false);
  const [isMapDropdownOpen, setIsMapDropdownOpen] = useState(false);
  const [activeMapMode, setActiveMapMode] = useState('Map 2');

  const pillStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
  };

  const menuStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.95)',
    backdropFilter: 'blur(28px)',
    WebkitBackdropFilter: 'blur(28px)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    boxShadow: '0 16px 40px rgba(0,0,0,0.8)',
  };

  return (
    <div className="flex flex-col space-y-2 pointer-events-auto select-none">
      {/* Large Title: Traffic Management */}
      <h1 className="text-[26px] font-semibold tracking-tight text-white leading-none">
        Traffic Management
      </h1>

      {/* Two Dropdown Pills: [ Bus 6023 ▾ ] [ Map 2 ▾ ] */}
      <div className="flex items-center space-x-2 pt-0.5">
        {/* Bus / Vehicle Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsBusDropdownOpen(!isBusDropdownOpen);
              setIsMapDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white/90 hover:text-white hover:border-white/20 transition-all cursor-pointer shadow-md"
            style={pillStyle}
          >
            <Bus className="w-3.5 h-3.5 text-white/70" />
            <span className="font-medium">{selectedVehicle}</span>
            <ChevronDown className="w-3 h-3 text-white/40" />
          </button>

          {isBusDropdownOpen && (
            <div className="absolute top-9 left-0 w-60 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {['Bus 6023', 'Bus 4120', 'Bus 2209', 'E-Bus 07'].map((b, idx) => (
                <div
                  key={b}
                  onClick={() => {
                    setSelectedVehicle(b);
                    if (availableMissions[idx]) {
                      selectMission(availableMissions[idx].id);
                    }
                    setIsBusDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white/90 flex justify-between items-center"
                >
                  <span>{b}</span>
                  {selectedVehicle === b && <Check className="w-3 h-3 text-emerald-400" />}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Map / Layer Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsMapDropdownOpen(!isMapDropdownOpen);
              setIsBusDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white/90 hover:text-white hover:border-white/20 transition-all cursor-pointer shadow-md"
            style={pillStyle}
          >
            <MapIcon className="w-3.5 h-3.5 text-white/70" />
            <span className="font-medium">{activeMapMode}</span>
            <ChevronDown className="w-3 h-3 text-white/40" />
          </button>

          {isMapDropdownOpen && (
            <div className="absolute top-9 left-0 w-44 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {['Map 1 (Topo)', 'Map 2 (Satellite Relief)', 'Map 3 (Night Infrared)'].map((m) => (
                <div
                  key={m}
                  onClick={() => {
                    setActiveMapMode(m.split(' ')[0] + ' ' + m.split(' ')[1]);
                    setIsMapDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white/90 flex justify-between items-center"
                >
                  <span>{m}</span>
                  {activeMapMode.startsWith(m.split(' ')[0] + ' ' + m.split(' ')[1]) && (
                    <Check className="w-3 h-3 text-emerald-400" />
                  )}
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

// 7. DashboardPanels.tsx (Exact layout with floating elements on map: Passenger Load 87%, Reticle, Zoom Pill, Footer Bar)
const dashboardPanelsCode = `import React from 'react';
import { FleetStatusCounters } from './FleetStatusCounters';
import { OperationalEfficiency } from './OperationalEfficiency';
import { DroneUnitCard } from './DroneUnitCard';
import { MapHeader } from './MapHeader';
import { ScheduleOffset } from './ScheduleOffset';
import { PassengerVolume } from './PassengerVolume';
import { VideoUploadButton } from './VideoUploadButton';
import { ArrowUpRight, Play, Plus, Minus, Disc } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const DashboardPanels: React.FC = () => {
  const { togglePlay, isPlaying } = useReconstruction();

  const glassPillStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 24, 0.88)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '16px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
  };

  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 p-4 pb-2 flex flex-col justify-between">
      {/* 1. FLOATING TITLE & DROPDOWNS: Top-left of map next to left sidebar */}
      <div className="absolute top-5 left-[370px] lg:left-[395px] xl:left-[415px] z-40 pointer-events-auto">
        <MapHeader />
      </div>

      {/* 2. TOP-RIGHT ACTIONS: Discreet Video Upload Button (Navbar & Warnings removed) */}
      <div className="absolute top-5 right-5 z-40 pointer-events-auto flex items-center space-x-3">
        <VideoUploadButton />
      </div>

      {/* 3. CENTER MAP FLOATING RETICLE (Concentric dashed ring with central play icon) */}
      <div className="absolute top-[40%] left-[56%] -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-auto flex items-center justify-center">
        {/* Radar Circular Disc */}
        <div className="w-28 h-28 rounded-full border border-dashed border-white/40 bg-black/25 backdrop-blur-[2px] flex items-center justify-center shadow-[0_0_24px_rgba(0,0,0,0.6)]">
          {/* Inner Target Center Button */}
          <button
            type="button"
            onClick={togglePlay}
            className="w-10 h-10 rounded-full bg-white/20 hover:bg-white/35 active:scale-95 transition-all flex items-center justify-center cursor-pointer border border-white/40 shadow-lg"
            title={isPlaying ? 'Pause' : 'Start Reconstruction'}
          >
            <Play className="w-4 h-4 text-white fill-white ml-0.5" />
          </button>
        </div>
      </div>

      {/* 4. FLOATING PASSENGER LOAD 87% CARD HOVERING OVER MAP */}
      <div
        className="absolute top-[45%] left-[48%] z-30 pointer-events-auto p-3 flex flex-col space-y-1"
        style={glassPillStyle}
      >
        <div className="flex items-center justify-between space-x-3">
          <span className="text-[10.5px] font-medium text-white/80">Passenger Load</span>
          <ArrowUpRight className="w-3 h-3 text-white/50" />
        </div>
        <div className="text-[8px] font-mono text-white/40">
          Next: Central Station
        </div>
        <div className="text-[26px] font-light tracking-tight text-white font-mono leading-none pt-0.5">
          87%
        </div>
      </div>

      {/* 5. FLOATING ZOOM CONTROLS ON BOTTOM-LEFT OF MAP (Above bottom panels) */}
      <div className="absolute bottom-[205px] lg:bottom-[215px] xl:bottom-[230px] left-[370px] lg:left-[395px] xl:left-[415px] z-40 pointer-events-auto flex items-center space-x-1.5 p-1 rounded-full" style={glassPillStyle}>
        <button
          type="button"
          onClick={() => {
            const map = (window as any).gisMap;
            if (map) map.zoomIn();
          }}
          className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center cursor-pointer transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => {
            const map = (window as any).gisMap;
            if (map) map.panTo([-122.35, 37.80], { duration: 600 });
          }}
          className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center cursor-pointer transition-all"
        >
          <Disc className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => {
            const map = (window as any).gisMap;
            if (map) map.zoomOut();
          }}
          className="w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center cursor-pointer transition-all"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 6. MAIN SPATIAL WORKSPACE (Left Side Panels & Bottom Row Panels) */}
      <div className="relative z-30 w-full flex-1 flex gap-3.5 overflow-hidden pointer-events-none mb-1">
        {/* LEFT COLUMN STACK: Fleet Counters -> Operational Efficiency -> 2x2 Drone Unit Cards */}
        <aside className="w-[340px] lg:w-[365px] xl:w-[385px] shrink-0 h-full flex flex-col gap-2.5 pointer-events-auto overflow-hidden">
          <FleetStatusCounters />
          <OperationalEfficiency />
          <div className="flex-1 min-h-0 overflow-hidden">
            <DroneUnitCard />
          </div>
        </aside>

        {/* BOTTOM ROW: Schedule Offset (Left) & Live Passenger Volume / Timeline (Right) */}
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

      {/* 7. FOOTER STATUS BAR (At very bottom edge across screen) */}
      <div className="w-full flex items-center justify-between text-[10px] font-mono text-white/40 px-1 pt-1 pointer-events-none">
        <div className="flex items-center space-x-1.5">
          <span>Last updated: Today, 11:29:32 AM</span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block shadow-[0_0_6px_#22c55e]" />
        </div>
        <div className="flex items-center space-x-1.5">
          <span>Data sync: Real-time</span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] inline-block shadow-[0_0_6px_#22c55e]" />
        </div>
      </div>
    </div>
  );
};

export default DashboardPanels;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx'), dashboardPanelsCode, 'utf8');
console.log('✓ Written components/dashboard/DashboardPanels.tsx');
