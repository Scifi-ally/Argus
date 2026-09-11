const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. FleetStatusCounters.tsx -> NO NAVBAR, NO NESTED BOXES!
// Two independent first-class glass cards side-by-side.
const fleetCountersCode = `import React from 'react';
import { useReconstruction } from '../../context/ReconstructionContext';

export const FleetStatusCounters: React.FC = () => {
  const { altitudeM, rtkStatus } = useReconstruction();

  const glassStyle: React.CSSProperties = {
    background: 'rgba(12, 16, 22, 0.28)',
    backdropFilter: 'blur(28px) saturate(180%)',
    WebkitBackdropFilter: 'blur(28px) saturate(180%)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '16px',
    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
  };

  return (
    <div className="grid grid-cols-2 gap-2.5 select-none shrink-0">
      {/* Left Card: RTK Status & Altitude (No nested box) */}
      <div className="p-3.5 flex items-center justify-between transition-all hover:border-white/20" style={glassStyle}>
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-white animate-pulse shadow-[0_0_8px_#ffffff]" />
          <span className="text-[12px] font-mono text-white/90 font-medium">
            {rtkStatus ? 'RTK' : 'ACTIVE'}
          </span>
        </div>
        <div className="text-right">
          <span className="text-[28px] font-light tracking-tight text-white leading-none font-mono">
            {altitudeM ? altitudeM.toFixed(1) : '14.0'}
          </span>
          <span className="text-[10px] font-mono text-white/45 ml-0.5">m</span>
        </div>
      </div>

      {/* Right Card: RMSE Precision (No nested box) */}
      <div className="p-3.5 flex items-center justify-between transition-all hover:border-white/20" style={glassStyle}>
        <div className="flex items-center space-x-2">
          <span className="text-[10px] text-white/80 font-mono">▲</span>
          <span className="text-[12px] font-mono text-white/90 font-medium">RMSE</span>
        </div>
        <div className="text-right">
          <span className="text-[28px] font-light tracking-tight text-white leading-none font-mono">
            0.38
          </span>
          <span className="text-[10px] font-mono text-white/45 ml-0.5">px</span>
        </div>
      </div>
    </div>
  );
};

export default FleetStatusCounters;
`;

fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), fleetCountersCode, 'utf8');
console.log('✓ Written FleetStatusCounters.tsx without navbar and without nested boxes');

// 2. DroneUnitCard.tsx -> Enhanced Animated SVGs with more vertical room
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
    <div className="grid grid-cols-2 gap-2.5 h-full min-h-[310px] select-none">
      {/* CARD 1 (Top-Left): UAV-01 with ANIMATED ROTATING PROPELLERS & PULSING OPTICAL CONE */}
      <div className="p-3.5 flex flex-col justify-between overflow-hidden transition-all hover:border-white/20" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-mono text-white font-medium">UAV-01</span>
          <ArrowUpRight className="w-3 h-3 text-white/40 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8.5px] font-mono text-white/40">
          4K · 30fps
        </div>

        {/* Animated SVG Drone Wireframe with Rotating Propellers */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[128px] h-[52px]" viewBox="0 0 140 56">
            <defs>
              <linearGradient id="opticalConeGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.28" />
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

            {/* 4 ANIMATED SPINNING ROTORS */}
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
      <div className="p-3.5 flex flex-col justify-between overflow-hidden transition-all hover:border-white/20" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-mono text-white font-medium">3D-MVS</span>
          <ArrowUpRight className="w-3 h-3 text-white/40 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8.5px] font-mono text-white/40">
          193.7k Polys
        </div>

        {/* Animated 3D Isometric Mesh Wireframe with Laser Sweep */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[128px] h-[52px]" viewBox="0 0 140 56">
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
              <line x1="0" y1="14" x2="50" y2="14" stroke="#ffffff" strokeWidth="1.6" filter="drop-shadow(0 0 4px #ffffff)">
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
      <div className="p-3.5 flex flex-col justify-between overflow-hidden transition-all hover:border-white/20" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-mono text-white font-medium">SfM-PT</span>
          <ArrowUpRight className="w-3 h-3 text-white/40 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8.5px] font-mono text-white/40">
          1.46M Points
        </div>

        {/* Animated Epipolar Tie-Point Ray Cast Graph */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[128px] h-[52px]" viewBox="0 0 140 56">
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
            <g stroke="rgba(255,255,255,0.6)" strokeWidth="0.8">
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
      <div className="p-3.5 flex flex-col justify-between overflow-hidden transition-all hover:border-white/20" style={cardStyle}>
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-mono text-white font-medium">AI-SEG</span>
          <ArrowUpRight className="w-3 h-3 text-white/40 hover:text-white cursor-pointer" />
        </div>
        <div className="text-[8.5px] font-mono text-white/40">
          99.8% Mask
        </div>

        {/* Animated Sonar Radar Wave Pulses */}
        <div className="w-full flex items-center justify-center my-1">
          <svg className="w-[128px] h-[52px]" viewBox="0 0 140 56">
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
console.log('✓ Written DroneUnitCard.tsx with enhanced SVGs');
