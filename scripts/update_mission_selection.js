const fs = require('fs');
const path = require('path');

const p = path.resolve(__dirname, '../../SIHFrontend/src/state/missionStore.tsx');
let content = fs.readFileSync(p, 'utf8');

const regex = /const savedId = localStorage\.getItem\(ACTIVE_MISSION_KEY\);[\r\n\s]+const targetId =[\r\n\s]+savedId && list\.some\(\(m\) => m\.id === savedId\)[\r\n\s]+\? savedId[\r\n\s]+: list\.length > 0[\r\n\s]+\? list\[list\.length - 1\]\.id[\r\n\s]+: null;/;

const replacement = `const savedId = localStorage.getItem(ACTIVE_MISSION_KEY);
        const withFlight = list.find((m) => m.flight && m.flight.path && m.flight.path.coordinates && m.flight.path.coordinates.length > 0);
        const savedMission = savedId ? list.find((m) => m.id === savedId) : null;
        const targetId =
          savedMission && savedMission.flight && savedMission.flight.path
            ? savedMission.id
            : withFlight
            ? withFlight.id
            : list.length > 0
            ? list[list.length - 1].id
            : null;`;

if (regex.test(content)) {
  content = content.replace(regex, replacement);
  fs.writeFileSync(p, content, 'utf8');
  console.log('✓ Successfully updated missionStore.tsx with regex replacement');
} else {
  console.log('Regex did not match');
}
