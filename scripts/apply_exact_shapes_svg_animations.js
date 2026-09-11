const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. FleetStatusCounters.tsx
// Exact shape from reference: 4 minimal tabs on top + TWO separate side-by-side cards below!
const fleetCountersCode = `import React, { useState } from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const FleetStatusCounters: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'uav' | 'mvs' | 'sfm' | 'seg'>('uav');
  const { altitudeM, rtkStatus } = useReconstruction();

  const tabs = [
    { id: 'uav', label: 'UAV-01' },
    { id: 'mvs', label: '3D-MVS' },
    { id: 'sfm', label: 'SfM-PT' },
    { id: 'seg', label: 'AI-SEG' },
  ] as const;

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  const cardStyle: React.CSSProperties = {
    background: 'rgba(14, 18, 26, 0.35)',
    border: '1px solid rgba(255, 255, 255, 0.10)',
    borderRadius: '12px',
    backdropFilter: 'blur(20px)',
  };

  return (
    <div className="flex flex-col select-none p-3 transition-all space-y-2.5 shrink-0" style={glassStyle}>
      {/* 4 Minimal Category Tabs (No verbose text) */}
      <div className="flex items-center bg-black/40 p-1 rounded-full border border-white/[0.08] text-[11px]">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={\`flex-1 py-1 px-1.5 rounded-full font-mono text-[10.5px] transition-all text-center cursor-pointer \${
                isActive
                  ? 'bg-white/20 text-white shadow-sm font-semibold'
                  : 'text-white/45 hover:text-white/80'
              }\`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Two Side-by-Side Cards (Matching reference image shape 1:1) */}
      <div className="grid grid-cols-2 gap-2.5">
        {/* Left Card: Active / Altitude */}
        <div className="p-3 flex items-center justify-between" style={cardStyle}>
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-white animate-pulse shadow-[0_0_8px_#ffffff]" />
            <span className="text-[11.5px] font-mono text-white/90">{rtkStatus ? 'RTK' : 'ACTIVE'}</span>
          </div>
          <div className="text-right">
            <span className="text-[26px] font-light tracking-tight text-white leading-none font-mono">
              {altitudeM ? altitudeM.toFixed(1) : '14.2'}
            </span>
            <span className="text-[9px] font-mono text-white/45 ml-0.5">m</span>
          </div>
        </div>

        {/* Right Card: Reprojection RMSE */}
        <div className="p-3 flex items-center justify-between" style={cardStyle}>
          <div className="flex items-center space-x-2">
            <span className="text-[9.5px] text-white/80 font-mono">▲</span>
            <span className="text-[11.5px] font-mono text-white/90">RMSE</span>
          </div>
          <div className="text-right">
            <span className="text-[26px] font-light tracking-tight text-white leading-none font-mono">
              0.38
            </span>
            <span className="text-[9px] font-mono text-white/45 ml-0.5">px</span>
          </div>
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
// Exact shape from reference: Spline chart with big metric, animated scan wave, super less text!
const opEffCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const OperationalEfficiency: React.FC = () => {
  const { metricAccuracy } = useReconstruction();

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="rounded-2xl p-3.5 flex flex-col justify-between shrink-0 select-none overflow-hidden transition-all" style={glassStyle}>
      {/* Minimal Header with arrow */}
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-mono text-white/80 tracking-wider">
          CONVERGENCE
        </span>
        <ArrowUpRight className="w-3.5 h-3.5 text-white/50 hover:text-white cursor-pointer" />
      </div>

      {/* Main Metric */}
      <div className="flex items-baseline space-x-1.5 my-0.5">
        <span className="text-[34px] font-light tracking-tight text-white leading-none font-mono">
          {metricAccuracy ? metricAccuracy.toFixed(1) : '99.4'}
        </span>
        <span className="text-[16px] font-light text-white/80 font-mono">%</span>
      </div>

      {/* Animated SVG Spline Area Chart */}
      <div className="relative w-full h-[95px] my-1">
        {/* Target threshold indicator */}
        <div className="absolute top-[20%] right-0 flex items-center space-x-1 z-10">
          <span className="text-[8.5px] font-mono text-white/45">&lt;0.50px</span>
        </div>

        <svg className="w-full h-full overflow-visible" viewBox="0 0 320 90" preserveAspectRatio="none">
          <defs>
            <linearGradient id="whiteSplineGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0.0" />
            </linearGradient>
            {/* Shimmer / Scan animation across graph */}
            <linearGradient id="sweepShimmer" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
              <stop offset="50%" stopColor="#ffffff" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
              <animate attributeName="x1" from="-1" to="1" dur="3s" repeatCount="indefinite" />
              <animate attributeName="x2" from="0" to="2" dur="3s" repeatCount="indefinite" />
            </linearGradient>
          </defs>

          {/* Horizontal Target Dashed Line */}
          <line
            x1="0"
            y1="22"
            x2="275"
            y2="22"
            stroke="rgba(255, 255, 255, 0.2)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />

          {/* Animated Sweeping Light Column */}
          <rect x="0" y="0" width="320" height="90" fill="url(#sweepShimmer)" />

          {/* Spline Area Fill */}
          <path
            d="M 10 65 
               C 35 72, 45 76, 60 74 
               C 85 70, 110 50, 135 48 
               C 160 46, 185 64, 210 52 
               C 225 40, 235 24, 250 25 
               C 265 26, 280 50, 305 48 
               L 305 90 L 10 90 Z"
            fill="url(#whiteSplineGrad)"
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
            stroke="#ffffff"
            strokeWidth="1.8"
          />

          {/* Pure White Dots on Peaks */}
          <circle cx="60" cy="74" r="2.5" fill="#ffffff" />
          <circle cx="135" cy="48" r="2.5" fill="#ffffff" />
          <circle cx="210" cy="52" r="2.5" fill="#ffffff" />
          <circle cx="250" cy="25" r="3" fill="#ffffff" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
        </svg>

        {/* Right Y Axis */}
        <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between text-[7.5px] font-mono text-white/35 pointer-events-none">
          <span>100%</span>
          <span>75%</span>
          <span>50%</span>
          <span>25%</span>
        </div>
      </div>

      {/* Bottom Time Axis */}
      <div className="flex justify-between items-center text-[8.5px] font-mono text-white/35 pt-1 border-t border-white/[0.08]">
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

// 3. DroneUnitCard.tsx -> The EXACT 2x2 Grid of 4 Cards with Rich SVG Animations & Super Less Text!
const droneUnitCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';

export const DroneUnitCard: React.FC = () => {
  const cardStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 12px 32px rgba(0, 0, 0, 0.4)',
  };

  return (
    <div className="grid grid-cols-2 gap-2.5 h-full min-h-[290px] select-none">
      {/* CARD 1 (Top-Left): UAV-01 with ANIMATED ROTATING PROPELLERS & PULSING OPTICAL CONE */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[11.5px] font-mono text-white font-medium">UAV-01</span>
          <ArrowUpRight className="w-3 h-3 text-white/45 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8px] font-mono text-white/40">
          4K · 30fps
        </div>

        {/* Animated SVG Drone Wireframe with Rotating Propellers */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[120px] h-[48px]" viewBox="0 0 140 56">
            <defs>
              {/* Scan Wave Ray Animation */}
              <linearGradient id="opticalConeGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#ffffff" stopOpacity="0.02" />
              </linearGradient>
            </defs>

            {/* Forward Optical Camera Frustum Cone */}
            <polygon points="90,28 135,10 135,46" fill="url(#opticalConeGrad)" />
            <line x1="90" y1="28" x2="135" y2="10" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" strokeDasharray="2 2" />
            <line x1="90" y1="28" x2="135" y2="46" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" strokeDasharray="2 2" />

            {/* Drone Fuselage Body */}
            <rect x="50" y="20" width="40" height="16" rx="8" fill="rgba(255,255,255,0.06)" stroke="#ffffff" strokeWidth="1" />
            {/* Center Gimbal Lens */}
            <circle cx="86" cy="28" r="3.5" fill="#ffffff" />
            <circle cx="86" cy="28" r="6" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />

            {/* 4 Motor Arms */}
            <line x1="60" y1="20" x2="42" y2="10" stroke="#ffffff" strokeWidth="1.2" />
            <line x1="80" y1="20" x2="98" y2="10" stroke="#ffffff" strokeWidth="1.2" />
            <line x1="60" y1="36" x2="42" y2="46" stroke="#ffffff" strokeWidth="1.2" />
            <line x1="80" y1="36" x2="98" y2="46" stroke="#ffffff" strokeWidth="1.2" />

            {/* 4 ANIMATED SPINNING ROTORS (CSS rotation) */}
            <g transform="translate(42, 10)">
              <circle cx="0" cy="0" r="1.5" fill="#ffffff" />
              <ellipse cx="0" cy="0" rx="9" ry="2.5" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="0.8">
                <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="0.35s" repeatCount="indefinite" />
              </ellipse>
            </g>

            <g transform="translate(98, 10)">
              <circle cx="0" cy="0" r="1.5" fill="#ffffff" />
              <ellipse cx="0" cy="0" rx="9" ry="2.5" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="0.8">
                <animateTransform attributeName="transform" type="rotate" from="360" to="0" dur="0.35s" repeatCount="indefinite" />
              </ellipse>
            </g>

            <g transform="translate(42, 46)">
              <circle cx="0" cy="0" r="1.5" fill="#ffffff" />
              <ellipse cx="0" cy="0" rx="9" ry="2.5" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="0.8">
                <animateTransform attributeName="transform" type="rotate" from="360" to="0" dur="0.35s" repeatCount="indefinite" />
              </ellipse>
            </g>

            <g transform="translate(98, 46)">
              <circle cx="0" cy="0" r="1.5" fill="#ffffff" />
              <ellipse cx="0" cy="0" rx="9" ry="2.5" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="0.8">
                <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="0.35s" repeatCount="indefinite" />
              </ellipse>
            </g>
          </svg>
        </div>

        {/* Minimal Status Row (Pure White) */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/70 pt-1 border-t border-white/[0.08]">
          <span className="flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            <span>ACTIVE</span>
          </span>
          <span>RTK</span>
          <span>LTE</span>
        </div>

        {/* Mini isometric route track with pulsing waypoint */}
        <div className="relative pt-0.5">
          <svg className="w-full h-[18px]" viewBox="0 0 120 18">
            <path d="M 10 14 L 45 6 L 60 14 L 85 4" fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="1" />
            <circle cx="10" cy="14" r="1.5" fill="#fff" />
            <circle cx="85" cy="4" r="2" fill="#fff" />
            <circle cx="85" cy="4" r="4" fill="none" stroke="#fff" strokeWidth="0.6">
              <animate attributeName="r" from="2" to="7" dur="1.5s" repeatCount="indefinite" />
              <animate attributeName="opacity" from="0.8" to="0" dur="1.5s" repeatCount="indefinite" />
            </circle>
          </svg>
        </div>
      </div>

      {/* CARD 2 (Top-Right): 3D-MVS with ANIMATED VERTICAL LASER SCANNING WIREFRAME */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[11.5px] font-mono text-white font-medium">3D-MVS</span>
          <ArrowUpRight className="w-3 h-3 text-white/45 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8px] font-mono text-white/40">
          193.7k Polys
        </div>

        {/* Animated 3D Isometric Mesh Wireframe with Laser Sweep */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[120px] h-[48px]" viewBox="0 0 140 56">
            {/* Isometric 3D Polygon Cube / Facets */}
            <g transform="translate(45, 6)">
              {/* Top Face */}
              <polygon points="25,4 45,14 25,24 5,14" fill="rgba(255,255,255,0.08)" stroke="#ffffff" strokeWidth="1" />
              {/* Left Face */}
              <polygon points="5,14 25,24 25,44 5,34" fill="rgba(255,255,255,0.04)" stroke="#ffffff" strokeWidth="1" />
              {/* Right Face */}
              <polygon points="25,24 45,14 45,34 25,44" fill="rgba(255,255,255,0.12)" stroke="#ffffff" strokeWidth="1" />
              {/* Triangulation Internal Mesh Lines */}
              <line x1="25" y1="4" x2="25" y2="24" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
              <line x1="5" y1="14" x2="45" y2="14" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
              <line x1="5" y1="34" x2="25" y2="24" stroke="rgba(255,255,255,0.3)" strokeWidth="0.6" strokeDasharray="2 2" />
              <line x1="45" y1="34" x2="25" y2="24" stroke="rgba(255,255,255,0.3)" strokeWidth="0.6" strokeDasharray="2 2" />

              {/* Laser Scanning Line Sweeping Vertically */}
              <line x1="0" y1="14" x2="50" y2="14" stroke="#ffffff" strokeWidth="1.5">
                <animateTransform attributeName="transform" type="translate" values="0, -8; 0, 26; 0, -8" dur="2.4s" repeatCount="indefinite" />
              </line>
            </g>
          </svg>
        </div>

        {/* Minimal Status Row (Pure White) */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/70 pt-1 border-t border-white/[0.08]">
          <span className="flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-white" />
            <span>MESH</span>
          </span>
          <span>GLB</span>
          <span>CUDA</span>
        </div>

        {/* Mini convergence track */}
        <div className="relative pt-0.5">
          <svg className="w-full h-[18px]" viewBox="0 0 120 18">
            <path d="M 20 14 L 50 6 L 70 10 L 105 4" fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="1" />
            <circle cx="20" cy="14" r="1.5" fill="#fff" />
            <circle cx="70" cy="10" r="2" fill="#fff" />
          </svg>
        </div>
      </div>

      {/* CARD 3 (Bottom-Left): SfM-PT with ANIMATED PULSING EPIPOLAR CONSTELLATION */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[11.5px] font-mono text-white font-medium">SfM-PT</span>
          <ArrowUpRight className="w-3 h-3 text-white/45 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8px] font-mono text-white/40">
          1.46M Points
        </div>

        {/* Animated Epipolar Tie-Point Ray Cast Graph */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[120px] h-[48px]" viewBox="0 0 140 56">
            {/* Camera Optical Centers */}
            <rect x="12" y="22" width="12" height="12" fill="rgba(255,255,255,0.15)" stroke="#fff" strokeWidth="0.8" rx="1.5" />
            <circle cx="18" cy="28" r="2" fill="#fff" />

            <rect x="116" y="22" width="12" height="12" fill="rgba(255,255,255,0.15)" stroke="#fff" strokeWidth="0.8" rx="1.5" />
            <circle cx="122" cy="28" r="2" fill="#fff" />

            {/* Tie-Point Constellation Nodes */}
            <circle cx="50" cy="14" r="2.5" fill="#fff" />
            <circle cx="68" cy="22" r="2.5" fill="#fff" />
            <circle cx="85" cy="12" r="2.5" fill="#fff" />
            <circle cx="60" cy="38" r="2.5" fill="#fff" />
            <circle cx="82" cy="34" r="2.5" fill="#fff" />

            {/* Epipolar Ray Lines with Pulsing Opacity */}
            <g stroke="rgba(255,255,255,0.5)" strokeWidth="0.8">
              <line x1="18" y1="28" x2="50" y2="14">
                <animate attributeName="opacity" values="0.2;1;0.2" dur="1.8s" repeatCount="indefinite" />
              </line>
              <line x1="18" y1="28" x2="68" y2="22">
                <animate attributeName="opacity" values="0.4;1;0.4" dur="2.1s" repeatCount="indefinite" />
              </line>
              <line x1="18" y1="28" x2="60" y2="38">
                <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" />
              </line>

              <line x1="122" y1="28" x2="85" y2="12">
                <animate attributeName="opacity" values="0.2;1;0.2" dur="1.8s" repeatCount="indefinite" />
              </line>
              <line x1="122" y1="28" x2="68" y2="22">
                <animate attributeName="opacity" values="0.5;1;0.5" dur="2.1s" repeatCount="indefinite" />
              </line>
              <line x1="122" y1="28" x2="82" y2="34">
                <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" />
              </line>
            </g>
          </svg>
        </div>

        {/* Minimal Status Row (Pure White) */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/70 pt-1 border-t border-white/[0.08]">
          <span className="flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-white" />
            <span>SOLVED</span>
          </span>
          <span>0.38px</span>
          <span>SIFT</span>
        </div>
      </div>

      {/* CARD 4 (Bottom-Right): AI-SEG with ANIMATED RADAR/SONAR EXPANDING WAVE */}
      <div className="p-3 flex flex-col justify-between overflow-hidden" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[11.5px] font-mono text-white font-medium">AI-SEG</span>
          <ArrowUpRight className="w-3 h-3 text-white/45 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8px] font-mono text-white/40">
          99.8% Mask
        </div>

        {/* Animated Sonar Radar Wave Pulses */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[120px] h-[48px]" viewBox="0 0 140 56">
            {/* Center Origin Dot */}
            <circle cx="70" cy="28" r="2.5" fill="#ffffff" />

            {/* Expanding Concentric Sonar Waves */}
            <circle cx="70" cy="28" r="6" fill="none" stroke="#ffffff" strokeWidth="0.8">
              <animate attributeName="r" from="4" to="24" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" from="0.9" to="0" dur="2s" repeatCount="indefinite" />
            </circle>
            <circle cx="70" cy="28" r="12" fill="none" stroke="#ffffff" strokeWidth="0.8">
              <animate attributeName="r" from="4" to="24" dur="2s" begin="0.6s" repeatCount="indefinite" />
              <animate attributeName="opacity" from="0.9" to="0" dur="2s" begin="0.6s" repeatCount="indefinite" />
            </circle>
            <circle cx="70" cy="28" r="18" fill="none" stroke="#ffffff" strokeWidth="0.8">
              <animate attributeName="r" from="4" to="24" dur="2s" begin="1.2s" repeatCount="indefinite" />
              <animate attributeName="opacity" from="0.9" to="0" dur="2s" begin="1.2s" repeatCount="indefinite" />
            </circle>

            {/* Bounding Obstacle Segmented Brackets */}
            <path d="M 40 18 L 34 18 L 34 24" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="1" />
            <path d="M 100 18 L 106 18 L 106 24" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="1" />
            <path d="M 40 38 L 34 38 L 34 32" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="1" />
            <path d="M 100 38 L 106 38 L 106 32" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="1" />
          </svg>
        </div>

        {/* Minimal Status Row (Pure White) */}
        <div className="flex items-center justify-between text-[8px] font-mono text-white/70 pt-1 border-t border-white/[0.08]">
          <span className="flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-white" />
            <span>INPAINT</span>
          </span>
          <span>NEURAL</span>
          <span>RT</span>
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
// Exact shape from reference: Table with ± 1.8 cm, variance columns, pure white, super less text!
const schedOffsetCode = `import React from 'react';
import { ArrowUpRight } from 'lucide-react';

export const ScheduleOffset: React.FC = () => {
  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-3.5" style={glassStyle}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-mono text-white/80 tracking-wider">
          PRECISION
        </span>
        <ArrowUpRight className="w-3.5 h-3.5 text-white/50 hover:text-white cursor-pointer" />
      </div>

      {/* Main Metric */}
      <div className="flex items-baseline space-x-2 my-0.5">
        <span className="text-[32px] font-light tracking-tight text-white leading-none font-mono">
          &plusmn; 1.8
        </span>
        <span className="text-[14px] font-light text-white/70 font-mono">cm</span>
        <span className="text-[10px] font-mono text-white/40 ml-2">Variance</span>
      </div>

      {/* Structured Matrix Table with Vertical Divider Bars (Pure White) */}
      <div className="w-full flex flex-col text-[11px] font-mono mt-0.5">
        {/* Table Header Row */}
        <div className="grid grid-cols-6 gap-2 text-white/40 text-[8.5px] pb-1 border-b border-white/[0.08] uppercase tracking-wider">
          <span className="col-span-1">Axis</span>
          <span className="text-center">X</span>
          <span className="text-center">Y</span>
          <span className="text-center">Z</span>
          <span className="text-center">Pitch</span>
          <span className="text-center">Roll</span>
        </div>

        {/* Row 1: > RTK */}
        <div className="grid grid-cols-6 gap-2 py-1.5 items-center text-white/85 border-b border-white/[0.04]">
          <span className="col-span-1 flex items-center space-x-1 text-white font-medium">
            <span className="text-white/40 text-[8.5px]">&gt;</span>
            <span>RTK</span>
          </span>
          <span className="text-center text-white/60 border-l border-white/[0.08]">-2mm</span>
          <span className="text-center text-white border-l border-white/[0.08] font-medium">+1mm</span>
          <span className="text-center text-white/60 border-l border-white/[0.08]">+0mm</span>
          <span className="text-center text-white/60 border-l border-white/[0.08]">-1.5mm</span>
          <span className="text-center text-white border-l border-white/[0.08] font-medium">+2mm</span>
        </div>

        {/* Row 2: > PPK */}
        <div className="grid grid-cols-6 gap-2 py-1.5 items-center text-white/80">
          <span className="col-span-1 flex items-center space-x-1 text-white font-medium">
            <span className="text-white/40 text-[8.5px]">&gt;</span>
            <span>PPK</span>
          </span>
          <span className="text-center text-white/60 border-l border-white/[0.08]">-3mm</span>
          <span className="text-center text-white/60 border-l border-white/[0.08]">-2mm</span>
          <span className="text-center text-white border-l border-white/[0.08] font-medium">+1mm</span>
          <span className="text-center text-white/60 border-l border-white/[0.08]">-2.5mm</span>
          <span className="text-center text-white border-l border-white/[0.08] font-medium">+2mm</span>
        </div>
      </div>
    </div>
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), schedOffsetCode, 'utf8');
console.log('✓ Written components/dashboard/ScheduleOffset.tsx');

// 5. PassengerVolume.tsx -> Timeline Component (Super less text, exact shape from reference!)
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

  const bars = [
    { height: 68, label: '55k', delta: '+8%' },
    { height: 75, label: '57k', delta: '-3%' },
    { height: 71, label: '56k', delta: '+6%' },
    { height: 68, label: '55k', delta: '-1%' },
    { height: 60, label: '52k', delta: '-10%' },
    { height: 62, label: '52k', delta: '+2%' },
    { height: 63, label: '52k', delta: '+4%' },
  ];

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return \`\${m.toString().padStart(2, '0')}:\${s.toString().padStart(2, '0')}\`;
  };

  return (
    <div className="select-none h-full overflow-hidden transition-all flex flex-col justify-between p-3.5" style={glassStyle}>
      {/* Header with Playback Controls and Arrow */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-1">
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={togglePlay}
            className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-white/15 hover:bg-white/25 text-white text-[9.5px] font-mono cursor-pointer transition-all active:scale-95 border border-white/20"
          >
            {isPlaying ? <Pause className="w-2.5 h-2.5 text-white fill-white" /> : <Play className="w-2.5 h-2.5 text-white fill-white" />}
            <span>{isPlaying ? 'PAUSE' : 'START'}</span>
          </button>

          <span className="text-[9.5px] font-mono text-white/60">
            F:{currentFrame}/{totalFrames || 1350} · {formatTime(currentSeconds)}/{formatTime(totalSeconds || 45)}
          </span>

          <button
            type="button"
            onClick={() => setSpeed(playbackSpeed === 1 ? 2 : playbackSpeed === 2 ? 4 : 1)}
            className="px-1.5 py-0.5 rounded bg-white/10 text-[8.5px] font-mono text-white hover:bg-white/20 border border-white/10"
          >
            {playbackSpeed}x
          </button>
        </div>

        <ArrowUpRight className="w-3.5 h-3.5 text-white/50 hover:text-white cursor-pointer" />
      </div>

      {/* Main Metric: Live Points */}
      <div className="flex items-baseline space-x-2 my-0.5">
        <span className="text-[30px] font-light tracking-tight text-white leading-none font-mono">
          {livePoints > 0 ? livePoints.toLocaleString() : '1,455,200'}
        </span>
        <span className="text-[10px] font-mono text-white/45">points</span>
      </div>

      {/* Pure White Vertical Bars */}
      <div className="relative w-full h-[42px] flex items-end justify-between px-2">
        {bars.map((b, i) => (
          <div key={i} className="flex flex-col items-center space-y-0.5 flex-1">
            <div className="flex items-center space-x-0.5 text-[7.5px] font-mono leading-none text-white/70">
              <span>{b.label}</span>
              <span className="text-white/40 font-light">{b.delta}</span>
            </div>
            <div
              className="w-[14px] lg:w-[18px] rounded-t-sm bg-white/25 hover:bg-white/40 transition-all"
              style={{ height: \`\${b.height * 0.35}px\` }}
            />
          </div>
        ))}

        <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between text-[7px] font-mono text-white/35 pointer-events-none">
          <span>60k</span>
          <span>0k</span>
        </div>
      </div>

      {/* Pure White Scrubbing Track & Time Axis */}
      <div className="relative w-full pt-0.5">
        <div className="relative w-full h-1.5 bg-white/10 rounded-full cursor-pointer overflow-hidden">
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

        <div className="flex justify-between text-[7.5px] font-mono text-white/35 pt-0.5">
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

// 6. MapHeader.tsx -> Super clean, minimal, only white, no verbose title
const mapHeaderCode = `import React, { useState } from 'react';
import { ChevronDown, Check, Crosshair, Box } from 'lucide-react';
import { useMission } from '../../state/missionStore';

export const MapHeader: React.FC = () => {
  const { availableMissions, selectMission } = useMission();
  const [selectedUnit, setSelectedUnit] = useState('UAV-01');
  const [selectedFormat, setSelectedFormat] = useState('3D GLB');
  const [isUnitDropdownOpen, setIsUnitDropdownOpen] = useState(false);
  const [isFormatDropdownOpen, setIsFormatDropdownOpen] = useState(false);

  const pillStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.35)',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
  };

  const menuStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.95)',
    backdropFilter: 'blur(28px)',
    WebkitBackdropFilter: 'blur(28px)',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    boxShadow: '0 16px 40px rgba(0,0,0,0.8)',
  };

  return (
    <div className="flex flex-col space-y-1.5 pointer-events-auto select-none">
      {/* Title */}
      <h1 className="text-[24px] font-light tracking-tight text-white leading-none">
        Single-Pass 3D Reconstruction
      </h1>

      {/* Two Dropdown Pills */}
      <div className="flex items-center space-x-2 pt-0.5">
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsUnitDropdownOpen(!isUnitDropdownOpen);
              setIsFormatDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white hover:bg-white/10 transition-all cursor-pointer shadow-md font-mono"
            style={pillStyle}
          >
            <Crosshair className="w-3 h-3 text-white/80" />
            <span className="font-medium">{selectedUnit}</span>
            <ChevronDown className="w-3 h-3 text-white/50" />
          </button>

          {isUnitDropdownOpen && (
            <div className="absolute top-9 left-0 w-44 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {['UAV-01', 'UAV-02', 'UAV-03'].map((u, idx) => (
                <div
                  key={u}
                  onClick={() => {
                    setSelectedUnit(u);
                    if (availableMissions[idx]) selectMission(availableMissions[idx].id);
                    setIsUnitDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white flex justify-between items-center font-mono"
                >
                  <span>{u}</span>
                  {selectedUnit === u && <Check className="w-3 h-3 text-white" />}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setIsFormatDropdownOpen(!isFormatDropdownOpen);
              setIsUnitDropdownOpen(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl text-[11px] text-white hover:bg-white/10 transition-all cursor-pointer shadow-md font-mono"
            style={pillStyle}
          >
            <Box className="w-3 h-3 text-white/80" />
            <span className="font-medium">{selectedFormat}</span>
            <ChevronDown className="w-3 h-3 text-white/50" />
          </button>

          {isFormatDropdownOpen && (
            <div className="absolute top-9 left-0 w-36 rounded-xl p-1.5 z-50 flex flex-col space-y-0.5" style={menuStyle}>
              {['3D GLB', 'LAS Cloud', 'OBJ Mesh'].map((fmt) => (
                <div
                  key={fmt}
                  onClick={() => {
                    setSelectedFormat(fmt);
                    setIsFormatDropdownOpen(false);
                  }}
                  className="p-2 rounded-lg cursor-pointer hover:bg-white/[0.08] text-[11px] text-white flex justify-between items-center font-mono"
                >
                  <span>{fmt}</span>
                  {selectedFormat === fmt && <Check className="w-3 h-3 text-white" />}
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

// 7. DashboardPanels.tsx
// Preserves exact panel shapes & layout!
// - Left stack: FleetStatusCounters (pills + 2 cards) -> OperationalEfficiency (spline card) -> DroneUnitCard (2x2 grid of 4 cards)
// - Bottom row: ScheduleOffset (left) & PassengerVolume (right)
// - Oval outward blur effect on map
// - Zero zoom controls, zero passenger load card
const dashboardPanelsCode = `import React from 'react';
import { FleetStatusCounters } from './FleetStatusCounters';
import { OperationalEfficiency } from './OperationalEfficiency';
import { DroneUnitCard } from './DroneUnitCard';
import { MapHeader } from './MapHeader';
import { ScheduleOffset } from './ScheduleOffset';
import { PassengerVolume } from './PassengerVolume';
import { VideoUploadButton } from './VideoUploadButton';

export const DashboardPanels: React.FC = () => {
  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none pointer-events-none z-20 p-4 pb-2 flex flex-col justify-between">
      {/* 1. OVAL OUTWARD BLUR EFFECT OVER MAP
          The center oval focus zone is crystal-clear (unblurred),
          and the blur effect gets smoothly and progressively stronger as it moves outward toward the screen edges & panels.
      */}
      <div
        className="absolute inset-0 pointer-events-none z-10 overflow-hidden"
        style={{
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          maskImage: 'radial-gradient(ellipse 62% 52% at 58% 46%, transparent 22%, rgba(0,0,0,0.4) 52%, black 88%)',
          WebkitMaskImage: 'radial-gradient(ellipse 62% 52% at 58% 46%, transparent 22%, rgba(0,0,0,0.4) 52%, black 88%)',
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
            1. FleetStatusCounters (Pills + 2 side-by-side cards)
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
            2. PassengerVolume / Timeline (col-span-7)
        */}
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
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx'), dashboardPanelsCode, 'utf8');
console.log('✓ Written components/dashboard/DashboardPanels.tsx');
