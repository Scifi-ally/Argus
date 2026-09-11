const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. FleetStatusCounters.tsx - fully transparent
const p1Code = `import React from 'react';

export const FleetStatusCounters: React.FC = () => {
  return (
    <div className="flex flex-col shrink-0 select-none overflow-hidden flex-1 min-h-[110px] bg-transparent border-0 shadow-none" />
  );
};

export default FleetStatusCounters;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/FleetStatusCounters.tsx'), p1Code, 'utf8');

// 2. OperationalEfficiency.tsx - fully transparent
const p2Code = `import React from 'react';

export const OperationalEfficiency: React.FC = () => {
  return (
    <div className="flex flex-col shrink-0 select-none overflow-hidden flex-1 min-h-[120px] bg-transparent border-0 shadow-none" />
  );
};

export default OperationalEfficiency;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/OperationalEfficiency.tsx'), p2Code, 'utf8');

// 3. DroneUnitCard.tsx - fully transparent 4 panels
const p3Code = `import React from 'react';

export const DroneUnitCard: React.FC = () => {
  return (
    <div className="flex flex-col gap-2.5 flex-[2] min-h-[240px] select-none bg-transparent border-0 shadow-none">
      {/* Row 1 */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        <div className="overflow-hidden h-full bg-transparent border-0 shadow-none" />
        <div className="overflow-hidden h-full bg-transparent border-0 shadow-none" />
      </div>

      {/* Row 2 */}
      <div className="grid grid-cols-2 gap-2.5 flex-1 min-h-0">
        <div className="overflow-hidden h-full bg-transparent border-0 shadow-none" />
        <div className="overflow-hidden h-full bg-transparent border-0 shadow-none" />
      </div>
    </div>
  );
};

export default DroneUnitCard;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/DroneUnitCard.tsx'), p3Code, 'utf8');

// 4. ScheduleOffset.tsx - fully transparent
const p4Code = `import React from 'react';

export const ScheduleOffset: React.FC = () => {
  return (
    <div className="select-none h-full overflow-hidden bg-transparent border-0 shadow-none" />
  );
};

export default ScheduleOffset;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/ScheduleOffset.tsx'), p4Code, 'utf8');

// 5. PassengerVolume.tsx - fully transparent
const p5Code = `import React from 'react';

export const PassengerVolume: React.FC = () => {
  return (
    <div className="select-none h-full overflow-hidden bg-transparent border-0 shadow-none" />
  );
};

export default PassengerVolume;
`;
fs.writeFileSync(path.join(frontendRoot, 'components/dashboard/PassengerVolume.tsx'), p5Code, 'utf8');

console.log('✓ All panels made fully transparent.');
