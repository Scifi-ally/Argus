const fs = require('fs');
const path = require('path');

const p = path.resolve(__dirname, '../../SIHFrontend/src/components/MapView.tsx');
let content = fs.readFileSync(p, 'utf8');

content = content.replace(/import\s*\{\s*Play,\s*CheckCircle2\s*\}\s*from\s*'lucide-react';\r?\n?/, '');
content = content.replace(
  /const\s*\{\s*currentFrame,\s*totalFrames,\s*isPlaying,\s*isCompleted,\s*startPlayback\s*\}\s*=\s*useReconstruction\(\);/,
  'const { currentFrame, totalFrames, isCompleted } = useReconstruction();'
);

fs.writeFileSync(p, content, 'utf8');
console.log('✓ Cleaned up MapView.tsx');
