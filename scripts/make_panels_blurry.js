const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// Subtle transparent frosted glass blur style
const blurPanelStyle = `const panelStyle: React.CSSProperties = {
  background: 'rgba(8, 12, 18, 0.28)',
  backdropFilter: 'blur(16px)',
  WebkitBackdropFilter: 'blur(16px)',
  border: '1px solid rgba(255, 255, 255, 0.04)',
  borderRadius: '16px',
};`;

// 1. FleetStatusCounters.tsx
const p1Code = `import React from 'react';

export const FleetStatusCounters: React.FC = () => {
  ${blurPanelStyle}

  return (
    <div
      className="flex flex-col shrink-0 select-none overflow-hidden flex-1 min-h-[110px] transition-all"
      style={panelStyle}
    />
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), p1Code, 'utf8');

// 2. OperationalEfficiency.tsx
const p2Code = `import React from 'react';

export const OperationalEfficiency: React.FC = () => {
  ${blurPanelStyle}

  return (
    <div
      className="flex flex-col shrink-0 select-none overflow-hidden flex-1 min-h-[120px] transition-all"
      style={panelStyle}
    />
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), p2Code, 'utf8');

// 3. DroneUnitCard.tsx
const p3Code = `import React from 'react';

export const DroneUnitCard: React.FC = () => {
  ${blurPanelStyle}

  return (
    <div className="flex flex-col gap-2.5 flex-[2] min-h-[240px] select-none">
      {/* Row 1 */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        <div className="overflow-hidden h-full transition-all" style={panelStyle} />
        <div className="overflow-hidden h-full transition-all" style={panelStyle} />
      </div>

      {/* Row 2 */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        <div className="overflow-hidden h-full transition-all" style={panelStyle} />
        <div className="overflow-hidden h-full transition-all" style={panelStyle} />
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), p3Code, 'utf8');

// 4. ScheduleOffset.tsx
const p4Code = `import React from 'react';

export const ScheduleOffset: React.FC = () => {
  ${blurPanelStyle}

  return (
    <div
      className="select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    />
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), p4Code, 'utf8');

// 5. PassengerVolume.tsx
const p5Code = `import React from 'react';

export const PassengerVolume: React.FC = () => {
  ${blurPanelStyle}

  return (
    <div
      className="select-none h-full overflow-hidden transition-all"
      style={panelStyle}
    />
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), p5Code, 'utf8');

console.log('✓ All panels updated with subtle frosted blur.');
