const fs = require('fs');
const path = require('path');

const p = path.resolve(__dirname, '../../SIHFrontend/src/context/ReconstructionContext.tsx');
let content = fs.readFileSync(p, 'utf8');

// Update useState for isPlaying and currentFrame
content = content.replace(
  `  // Playback state: starts paused until user clicks START
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentFrame, setCurrentFrame] = useState<number>(0);`,
  `  // Playback state: starts paused until user clicks START (supports ?frame= and ?play= URL params)
  const [isPlaying, setIsPlaying] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('play') === 'true';
    }
    return false;
  });
  const [currentFrame, setCurrentFrame] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      const f = new URLSearchParams(window.location.search).get('frame');
      if (f !== null) return Number(f);
    }
    return 0;
  });`
);

// Expose reconstruction controls to window
content = content.replace(
  `  return (
    <ReconstructionContext.Provider`,
  `  useEffect(() => {
    (window as any).reconstruction = {
      togglePlay,
      startPlayback,
      resetPlayback,
      seekToFrame,
      open3DViewer,
    };
  }, [togglePlay, startPlayback, resetPlayback, seekToFrame, open3DViewer]);

  return (
    <ReconstructionContext.Provider`
);

fs.writeFileSync(p, content, 'utf8');
console.log('✓ Updated ReconstructionContext.tsx with URL param support and window.reconstruction');

// Also update missionStore.tsx for ?viewer= URL param
const pStore = path.resolve(__dirname, '../../SIHFrontend/src/state/missionStore.tsx');
let storeContent = fs.readFileSync(pStore, 'utf8');
storeContent = storeContent.replace(
  `const [isViewerOpen, setIsViewerOpen] = useState<boolean>(false);`,
  `const [isViewerOpen, setIsViewerOpen] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search).get('viewer') === 'true';
    }
    return false;
  });`
);
fs.writeFileSync(pStore, storeContent, 'utf8');
console.log('✓ Updated missionStore.tsx with ?viewer= URL param');
