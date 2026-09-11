const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '../../SIHFrontend/src');

// 1. mapConfig.ts - Always load Esri Clarity Summer tiles, high definition crispness, fixed zoom 11.2
const mapConfigPath = path.join(frontendRoot, 'config/mapConfig.ts');
let mapConfig = fs.readFileSync(mapConfigPath, 'utf8');

// Update ARCGIS_CONFIG to use official Esri Clarity leaf-on summer tiles
mapConfig = mapConfig.replace(
  `export const ARCGIS_CONFIG = {
  tiles: [
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  ],
  tileSize: 256,
  maxzoom: 19,
  attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, USDA, USGS, AeroGRID, IGN, and the GIS User Community',
};`,
  `// ArcGIS World Imagery (Clarity Archive: crystal-clear, cloud-free leaf-on summer tiles)
export const ARCGIS_CONFIG = {
  tiles: [
    'https://clarity.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  ],
  tileSize: 256,
  maxzoom: 19,
  attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
};`
);

// Update INITIAL_CAMERA_CONFIG with exact fixed zoom 11.2 centered on San Francisco
mapConfig = mapConfig.replace(
  `export const INITIAL_CAMERA_CONFIG = {
  center: [-122.35, 37.80] as [number, number],
  zoom: 10.8,
  pitch: 0,
  bearing: 0,
  maxPitch: 0,
  minPitch: 0,
  minZoom: 10.8,
  maxZoom: 10.8,
};`,
  `// Fixed Drone Mission Overview z = 11.2 (never zoom in or out)
export const INITIAL_CAMERA_CONFIG = {
  center: [-122.4194, 37.77508] as [number, number],
  zoom: 11.2,
  pitch: 0,
  bearing: 0,
  maxPitch: 0,
  minPitch: 0,
  minZoom: 11.2,
  maxZoom: 11.2,
};`
);

// Update VISUAL_CONFIG for razor-sharp high-definition summer building clarity
mapConfig = mapConfig.replace(
  `export const VISUAL_CONFIG = {
  canvasBackgroundColor: GIS_PALETTE.land.base,
  satellite: {
    rasterOpacity: 1.0 as PropertyValueSpecification<number>,
    rasterSaturation: 0.12 as PropertyValueSpecification<number>,
    rasterContrast: 0.16 as PropertyValueSpecification<number>,
    rasterBrightnessMax: 1.0 as PropertyValueSpecification<number>,
    rasterBrightnessMin: 0.02,
    rasterHueRotate: 0,
    rasterFadeDuration: 0,
  },`,
  `export const VISUAL_CONFIG = {
  canvasBackgroundColor: GIS_PALETTE.land.base,
  satellite: {
    rasterOpacity: 1.0 as PropertyValueSpecification<number>,
    rasterSaturation: 0.28 as PropertyValueSpecification<number>, // Rich, vibrant summer foliage & streets
    rasterContrast: 0.24 as PropertyValueSpecification<number>,   // High-definition clarity so buildings are crisp
    rasterBrightnessMax: 1.0 as PropertyValueSpecification<number>,
    rasterBrightnessMin: 0.0,
    rasterHueRotate: 0,
    rasterFadeDuration: 0,
  },`
);

fs.writeFileSync(mapConfigPath, mapConfig, 'utf8');
console.log('✓ Updated mapConfig.ts with Esri Clarity summer tiles, HD contrast & fixed zoom 11.2');

// 2. DashboardPanels.tsx - Remove the artificial blur overlay that made buildings blurry
const panelsPath = path.join(frontendRoot, 'components/dashboard/DashboardPanels.tsx');
let panels = fs.readFileSync(panelsPath, 'utf8');

// Strip out the backdropFilter blur overlay that was blurring the buildings
panels = panels.replace(
  `      {/* 1. CINEMATIC RADIAL BLUR FOCUSING ON SATELLITE CENTER */}
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
      />`,
  `      {/* 1. CRYSTAL-CLEAR UNBLURRED VIEWPORT (Blur removed so summer buildings are razor sharp) */}`
);

fs.writeFileSync(panelsPath, panels, 'utf8');
console.log('✓ Updated DashboardPanels.tsx removed artificial map blur');

// 3. MapView.tsx - Lock zoom strictly at 11.2, never zoom in, remove floating buttons from map
const mapPath = path.join(frontendRoot, 'components/MapView.tsx');
let mapView = fs.readFileSync(mapPath, 'utf8');

// Lock zoom at 11.2
mapView = mapView.replace(
  `      zoom: 10.8,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      minPitch: 0,
      minZoom: 2,
      maxZoom: 19,`,
  `      zoom: 11.2,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
      minPitch: 0,
      minZoom: 11.2,
      maxZoom: 11.2,`
);

// Pan only, NEVER zoom in!
mapView = mapView.replace(
  `  // 2. Pan and zoom to mission center when mission coordinates arrive so flight path is clearly visible
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mission?.location?.center) return;
    map.jumpTo({
      center: [mission.location.center.lng, mission.location.center.lat],
      zoom: 16.8,
    });
  }, [mission?.id, mission?.location?.center]);`,
  `  // 2. Pan to mission center at FIXED zoom 11.2 (never zoom in)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mission?.location?.center) return;
    map.panTo([mission.location.center.lng, mission.location.center.lat], { duration: 600 });
  }, [mission?.id, mission?.location?.center]);`
);

// Remove floating buttons on the map!
mapView = mapView.replace(
  `  return (
    <div ref={mapContainerRef} className="map-viewport relative">
      {/* Standby Start Button Prompt on Map */}
      {!isPlaying && currentFrame === 0 && mission?.flight && (
        <div className="absolute top-[48%] left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-auto flex flex-col items-center">
          <button
            type="button"
            onClick={startPlayback}
            className="flex items-center space-x-2 px-5 py-2.5 rounded-full text-xs font-semibold tracking-wide text-white transition-all shadow-[0_0_30px_rgba(29,161,242,0.4)] active:scale-95 cursor-pointer"
            style={{
              background: 'rgba(29, 161, 242, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
            }}
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>START FLIGHT & 3D RECONSTRUCTION</span>
          </button>
        </div>
      )}

      {/* Completion Notification Prompt on Map */}
      {isCompleted && (
        <div className="absolute top-[38%] left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-auto flex flex-col items-center">
          <div
            onClick={openViewer}
            className="flex items-center space-x-2.5 px-4 py-2 rounded-xl text-xs text-white transition-all shadow-[0_0_30px_rgba(29,161,242,0.35)] cursor-pointer hover:scale-105 active:scale-95"
            style={{
              background: 'rgba(10, 16, 26, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid #1DA1F2',
            }}
          >
            <CheckCircle2 className="w-4 h-4 text-[#1DA1F2]" />
            <span className="font-medium text-white/90">
              3D Model Ready • <span className="text-[#1DA1F2] font-semibold">Click Area to Inspect Model</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );`,
  `  return (
    <div ref={mapContainerRef} className="map-viewport relative">
      {/* Zero buttons floating on map per user requirement; controls are cleanly placed in the timeline component */}
    </div>
  );`
);

fs.writeFileSync(mapPath, mapView, 'utf8');
console.log('✓ Updated MapView.tsx locked at zoom 11.2 with zero floating map buttons');

// 4. DronePointsLayer.ts - Ensure drone marker is prominent and sharp at fixed zoom 11.2
const pointsPath = path.join(frontendRoot, 'layers/drone/DronePointsLayer.ts');
let pointsCode = fs.readFileSync(pointsPath, 'utf8');

pointsCode = pointsCode.replace(
  `          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 5, 8, 10, 11, 16, 14, 24],
          'circle-color': '#1DA1F2',
          'circle-opacity': 0.28,
          'circle-blur': 0.5,`,
  `          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 6, 8, 10, 11, 14, 14, 20],
          'circle-color': '#1DA1F2',
          'circle-opacity': 0.35,
          'circle-blur': 0.4,`
);

pointsCode = pointsCode.replace(
  `          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3.0, 8, 5.0, 11, 7.5, 14, 9.5],
          'circle-color': '#08111A',
          'circle-stroke-color': '#1DA1F2',
          'circle-stroke-width': 1.8,`,
  `          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3.5, 8, 5.5, 11, 7.0, 14, 9.0],
          'circle-color': '#08111A',
          'circle-stroke-color': '#1DA1F2',
          'circle-stroke-width': 2.2,`
);

pointsCode = pointsCode.replace(
  `          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 1.4, 8, 2.2, 11, 3.4, 14, 4.4],
          'circle-color': '#FFFFFF',`,
  `          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 1.6, 8, 2.4, 11, 3.2, 14, 4.0],
          'circle-color': '#FFFFFF',`
);

fs.writeFileSync(pointsPath, pointsCode, 'utf8');
console.log('✓ Updated DronePointsLayer.ts calibrated for zoom 11.2');

// 5. DronePathLayer.ts - Calibrate line width for zoom 11.2
const dronePathFile = path.join(frontendRoot, 'layers/drone/DronePathLayer.ts');
let pathCode = fs.readFileSync(dronePathFile, 'utf8');

pathCode = pathCode.replace(
  `          'line-color': '#1DA1F2',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1.2, 8, 2.0, 11, 2.8, 14, 4.0],
          'line-opacity': 1.0,`,
  `          'line-color': '#1DA1F2',
          'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1.5, 8, 2.4, 11, 3.6, 14, 4.8],
          'line-opacity': 1.0,`
);

fs.writeFileSync(dronePathFile, pathCode, 'utf8');
console.log('✓ Updated DronePathLayer.ts calibrated line width for zoom 11.2');

console.log('✓ All configurations successfully applied!');
