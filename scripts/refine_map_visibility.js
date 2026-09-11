const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. Update MapView.tsx to zoom 16.8 when mission flight coordinates arrive
const mapPath = path.join(frontendRoot, 'components/MapView.tsx');
let mapContent = fs.readFileSync(mapPath, 'utf8');

mapContent = mapContent.replace(
  `  // 2. Pan to mission center when mission coordinates arrive
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mission?.location?.center) return;
    map.panTo([mission.location.center.lng, mission.location.center.lat], { duration: 1200 });
  }, [mission?.id, mission?.location?.center]);`,
  `  // 2. Pan and zoom to mission center when mission coordinates arrive so flight path is clearly visible
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mission?.location?.center) return;
    map.jumpTo({
      center: [mission.location.center.lng, mission.location.center.lat],
      zoom: 16.8,
    });
  }, [mission?.id, mission?.location?.center]);`
);

fs.writeFileSync(mapPath, mapContent, 'utf8');
console.log('✓ Updated MapView.tsx zoom to 16.8');

// 2. Update DashboardPanels.tsx to remove the obscuring central black reticle disk
const panelsPath = path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx');
let panelsContent = fs.readFileSync(panelsPath, 'utf8');

panelsContent = panelsContent.replace(
  `      {/* 2. CENTRAL TACTICAL DISK RETICLE */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-20 flex items-center justify-center">
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center shadow-2xl"
          style={{
            background: 'rgba(10, 14, 20, 0.65)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M 9 2 L 15 15 L 9 12 L 3 15 Z"
              fill="#FFFFFF"
            />
          </svg>
        </div>
      </div>`,
  `      {/* 2. UNCLUTTERED MAP VIEWPORT (Obscuring center disk removed for clear flight & footprint visibility) */}`
);

fs.writeFileSync(panelsPath, panelsContent, 'utf8');
console.log('✓ Updated DashboardPanels.tsx removed obscuring center disk');
