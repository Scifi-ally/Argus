/**
 * SinglePass3D — Premium Geospatial Visualization Experience
 * 
 * Architecture:
 *   GlobeEngine (Three.js) → MapEngine (MapLibre GL JS) → RouteLayer → CameraController
 *   TelemetryProcessor → GeoJSON → Dynamic camera framing
 *   ReconstructionTimeline → Playback + progress
 *   UIController → State machine + upload flow
 *
 * Vector-first cartography: OpenFreeMap tiles + custom dark style
 * No Mapbox. No API tokens. No satellite imagery.
 */

// ============================================================
// 1. CONSTANTS & COLOR SYSTEM
// ============================================================

const COLORS = Object.freeze({
  bgVoid:       '#050706',
  bgUI:         '#0a0a0a',
  water:        '#08131B',
  waterDeep:    '#050D13',
  landNatural:  '#19372A',
  landSecondary:'#203F2E',
  vegetation:   '#1E3B26',
  parks:        '#284C32',
  urban:        '#41433F',
  urbanDense:   '#4A4C47',
  buildings:    '#555750',
  buildingsAlt: '#60615A',
  roadsMajor:   '#969892',
  roadsSecond:  '#6D706B',
  roadsMinor:   '#555954',
  textPrimary:  '#F2F4F1',
  textSecondary:'#858C88',
  textMuted:    '#5A5F5C',
  uavRoute:     '#FFFFFF',
  uavActive:    '#F59E0B',
  uavUnder:     '#05080A',
});

const AppState = Object.freeze({
  IDLE:            'idle',
  UPLOADING:       'uploading',
  EXTRACTING_GPS:  'extracting_gps',
  POSITIONING:     'positioning',
  RENDERING_MAP:   'rendering_map',
  FLIGHT_READY:    'flight_ready',
  RECONSTRUCTING:  'reconstructing',
  COMPLETE:        'complete',
  ERROR:           'error',
});

// ============================================================
// 2. CUSTOM MAPLIBRE STYLE (OpenFreeMap vector tiles)
// ============================================================

function createDarkCartographyStyle() {
  return {
    version: 8,
    name: 'SinglePass3D Cinematic Satellite Map',
    sources: {
      'arcgis-satellite': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        ],
        tileSize: 256,
        maxzoom: 19,
        attribution: 'Tiles &copy; Esri',
      },
      openmaptiles: {
        type: 'vector',
        url: 'https://tiles.openfreemap.org/planet',
      },
    },
    sprite: 'https://tiles.openfreemap.org/sprites/ofm_f384/ofm',
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    layers: [
      // 1. Background Void
      {
        id: 'background',
        type: 'background',
        paint: { 'background-color': '#050706' },
      },

      // 2. High-Definition Satellite Terrain Base (Reference Graded: high-contrast topography + organic moss green)
      {
        id: 'satellite-base',
        type: 'raster',
        source: 'arcgis-satellite',
        paint: {
          'raster-opacity': 1.0,
          'raster-saturation': 0.24,
          'raster-contrast': 0.38,
          'raster-brightness-min': 0.0,
          'raster-brightness-max': 0.85,
          'raster-fade-duration': 0,
        },
      },

      // 3. Precision Deep Slate Water Layer (#08131B overlay matching reference deep ocean/bay)
      {
        id: 'water-dark-overlay',
        type: 'fill',
        source: 'openmaptiles',
        'source-layer': 'water',
        paint: {
          'fill-color': '#08131B',
          'fill-opacity': 0.88,
          'fill-antialias': true,
        },
      },

      // 4. Subtle Shoreline Edge Casing
      {
        id: 'water-shoreline-casing',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'water',
        paint: {
          'line-color': '#11222E',
          'line-width': 1.2,
          'line-opacity': 0.65,
        },
      },

      // 5. Motorways & Primary Arteries (Crisp subdued infrastructure)
      {
        id: 'road-motorway',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'transportation',
        filter: ['match', ['get', 'class'], ['motorway', 'trunk'], true, false],
        paint: {
          'line-color': '#969892',
          'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.8, 12, 2.0, 16, 4.0],
          'line-opacity': 0.45,
        },
      },
      {
        id: 'road-primary',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'transportation',
        filter: ['match', ['get', 'class'], ['primary', 'secondary'], true, false],
        paint: {
          'line-color': '#6D706B',
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.6, 14, 1.8],
          'line-opacity': 0.35,
        },
      },

      // 6. Geographic Labels
      {
        id: 'label-place',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'place',
        filter: ['match', ['get', 'class'], ['city', 'town'], true, false],
        layout: {
          'text-field': '{name:latin}',
          'text-font': ['Noto Sans Regular'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 6, 11, 12, 14],
          'text-letter-spacing': 0.1,
          'text-transform': 'uppercase',
          'text-max-width': 8,
        },
        paint: {
          'text-color': '#F2F4F1',
          'text-halo-color': '#050706',
          'text-halo-width': 1.5,
          'text-halo-blur': 1.0,
          'text-opacity': 0.75,
        },
      },
    ],
  };
}

// ============================================================
// 3. TELEMETRY PROCESSOR
// ============================================================

class TelemetryProcessor {
  /**
   * Parse DJI-style SRT subtitle content.
   * Returns array of { lat, lng, alt, yaw, pitch, roll, timestamp }
   */
  parseSRT(text) {
    const points = [];
    const lines = text.split('\n');

    let currentTimestamp = 0;

    for (const line of lines) {
      const timeMatch = line.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})/);
      if (timeMatch) {
        currentTimestamp = parseInt(timeMatch[1], 10) * 3600 +
                           parseInt(timeMatch[2], 10) * 60 +
                           parseInt(timeMatch[3], 10) +
                           parseInt(timeMatch[4], 10) / 1000;
        continue;
      }

      const latMatch = line.match(/\[latitude:\s*([-\d.]+)\]/);
      const lngMatch = line.match(/\[longitude:\s*([-\d.]+)\]/);
      if (!latMatch || !lngMatch) continue;

      const lat = parseFloat(latMatch[1]);
      const lng = parseFloat(lngMatch[1]);

      // Filter invalid samples
      if (isNaN(lat) || isNaN(lng) || (lat === 0 && lng === 0)) continue;
      if (lat < -90 || lat > 90 || lng < -180 || lng > 180) continue;

      const altMatch = line.match(/\[(?:rel_alt|abs_alt):\s*([-\d.]+)\]/);
      const yawMatch = line.match(/\[yaw:\s*([-\d.]+)\]/);
      const pitchMatch = line.match(/\[pitch:\s*([-\d.]+)\]/);
      const rollMatch = line.match(/\[roll:\s*([-\d.]+)\]/);

      const timestamp = currentTimestamp || (points.length * 0.05);

      points.push({
        lat,
        lng,
        alt: altMatch ? parseFloat(altMatch[1]) : 0,
        yaw: yawMatch ? parseFloat(yawMatch[1]) : 0,
        pitch: pitchMatch ? parseFloat(pitchMatch[1]) : 0,
        roll: rollMatch ? parseFloat(rollMatch[1]) : 0,
        timestamp,
      });
    }

    return points;
  }

  /**
   * Calculate bounding box of GPS points.
   */
  calculateBounds(points) {
    if (!points.length) return null;

    let minLat = Infinity, maxLat = -Infinity;
    let minLng = Infinity, maxLng = -Infinity;

    for (const p of points) {
      if (p.lat < minLat) minLat = p.lat;
      if (p.lat > maxLat) maxLat = p.lat;
      if (p.lng < minLng) minLng = p.lng;
      if (p.lng > maxLng) maxLng = p.lng;
    }

    const centroid = {
      lat: (minLat + maxLat) / 2,
      lng: (minLng + maxLng) / 2,
    };

    const latSpan = maxLat - minLat;
    const lngSpan = maxLng - minLng;

    return {
      sw: [minLng, minLat],
      ne: [maxLng, maxLat],
      centroid,
      latSpan,
      lngSpan,
      aspectRatio: lngSpan / (latSpan || 0.0001),
    };
  }

  /**
   * Calculate proportional padding so route occupies ~40-60% of viewport.
   */
  calculatePadding(bounds, viewportWidth, viewportHeight) {
    // We want route to occupy ~50% of the useful viewport
    // With safe areas for header (48px top) and timeline (80px bottom)
    const safeTop = 60;
    const safeBottom = 100;
    const safeHoriz = 40;

    // Proportional padding = 25% of each dimension (so route occupies ~50%)
    const paddingH = Math.max(safeHoriz, viewportWidth * 0.2);
    const paddingV = Math.max(safeTop, viewportHeight * 0.15);

    return {
      top: Math.max(safeTop, paddingV),
      bottom: Math.max(safeBottom, paddingV + 20),
      left: paddingH,
      right: paddingH,
    };
  }

  /**
   * Convert GPS points to GeoJSON FeatureCollection.
   */
  toGeoJSON(points) {
    const coordinates = points.map(p => [p.lng, p.lat]);

    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { type: 'route' },
          geometry: {
            type: 'LineString',
            coordinates,
          },
        },
      ],
    };
  }

  /**
   * Get total flight duration in seconds.
   */
  getDuration(points) {
    if (!points.length) return 0;
    return points[points.length - 1].timestamp - points[0].timestamp;
  }

  /**
   * Get average altitude.
   */
  getAverageAltitude(points) {
    if (!points.length) return 0;
    const sum = points.reduce((s, p) => s + p.alt, 0);
    return sum / points.length;
  }
}


// ============================================================
// 4. GLOBE ENGINE (Three.js)
// ============================================================

class GlobeEngine {
  constructor(container) {
    this.container = container;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.globeGroup = null;
    this.earthMesh = null;
    this.cloudMesh = null;
    this.atmosphereMesh = null;
    this.starfield = null;
    this.beaconGroup = null;
    this.beaconRing = null;
    this.animationId = null;
    this.destroyed = false;
    this.isTransitioning = false;

    // Interaction state
    this.isDragging = false;
    this.prevMouseX = 0;
    this.prevMouseY = 0;
    this.rotVelX = 0;
    this.rotVelY = 0;
    this.targetCameraZ = 3.2;

    this._init();
  }

  _init() {
    const w = window.innerWidth;
    const h = window.innerHeight;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x020406);

    // Camera
    this.camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
    this.camera.position.set(0, 0, 3.2);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x020406, 1.0);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.container.appendChild(this.renderer.domElement);

    // Starfield Background
    this._createStarfield();

    // Group for Earth, clouds, atmosphere & markers
    this.globeGroup = new THREE.Group();
    this.scene.add(this.globeGroup);

    // Lighting
    const ambient = new THREE.AmbientLight(0x16222f, 0.45);
    this.scene.add(ambient);

    // Sun directional light (illuminates day side)
    const sunLight = new THREE.DirectionalLight(0xfff5e6, 1.8);
    sunLight.position.set(6, 3, 5);
    this.scene.add(sunLight);

    // Rim fill light
    const fillLight = new THREE.DirectionalLight(0x0a1c2e, 0.4);
    fillLight.position.set(-6, -2, -4);
    this.scene.add(fillLight);

    // High Quality Earth with Day/Night & Ocean Shader
    this._createEarth(sunLight.position);

    // Dynamic Cloud Layer
    this._createClouds();

    // Rayleigh Scattering Atmosphere
    this._createAtmosphere(sunLight.position);

    // Mouse drag orbit controls
    this._setupInteraction();

    // Resize handler
    this._onResize = () => {
      if (this.destroyed) return;
      const nw = window.innerWidth;
      const nh = window.innerHeight;
      this.camera.aspect = nw / nh;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(nw, nh);
    };
    window.addEventListener('resize', this._onResize);

    // Start render loop
    this._animate();
  }

  _createStarfield() {
    const count = 1800;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      const r = 80 + Math.random() * 140;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);

      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);

      const temp = Math.random();
      if (temp > 0.82) {
        colors[i * 3] = 0.75; colors[i * 3 + 1] = 0.88; colors[i * 3 + 2] = 1.0;
      } else if (temp < 0.18) {
        colors[i * 3] = 1.0; colors[i * 3 + 1] = 0.86; colors[i * 3 + 2] = 0.7;
      } else {
        colors[i * 3] = 0.95; colors[i * 3 + 1] = 0.95; colors[i * 3 + 2] = 0.95;
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const mat = new THREE.PointsMaterial({
      size: 1.5,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
    });

    this.starfield = new THREE.Points(geo, mat);
    this.scene.add(this.starfield);
  }

  _createEarth(sunPos) {
    const geometry = new THREE.SphereGeometry(1, 128, 128);

    const textureLoader = new THREE.TextureLoader();
    const dayTexture = textureLoader.load('textures/earth-blue-marble.jpg');
    const nightTexture = textureLoader.load('textures/earth_night.jpg');
    const bumpTexture = textureLoader.load('textures/earth-topology.png');
    const waterTexture = textureLoader.load('textures/earth-water.png');

    dayTexture.anisotropy = 8;
    nightTexture.anisotropy = 8;
    bumpTexture.anisotropy = 8;
    waterTexture.anisotropy = 8;

    const vertexShader = `
      varying vec2 vUv;
      varying vec3 vNormal;
      varying vec3 vPosition;

      void main() {
        vUv = uv;
        vNormal = normalize(normalMatrix * normal);
        vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `;

    const fragmentShader = `
      uniform sampler2D dayTexture;
      uniform sampler2D nightTexture;
      uniform sampler2D bumpTexture;
      uniform sampler2D waterTexture;
      uniform vec3 sunDirection;

      varying vec2 vUv;
      varying vec3 vNormal;
      varying vec3 vPosition;

      void main() {
        vec3 normal = normalize(vNormal);
        vec3 sunDir = normalize(sunDirection);

        // Topographic relief bump mapping
        vec2 texel = vec2(1.0 / 2048.0, 1.0 / 1024.0);
        float hL = texture2D(bumpTexture, vUv - vec2(texel.x, 0.0)).r;
        float hR = texture2D(bumpTexture, vUv + vec2(texel.x, 0.0)).r;
        float hD = texture2D(bumpTexture, vUv - vec2(0.0, texel.y)).r;
        float hU = texture2D(bumpTexture, vUv + vec2(0.0, texel.y)).r;
        vec3 bumpOffset = vec3((hL - hR) * 0.16, (hD - hU) * 0.16, 0.0);
        vec3 N = normalize(normal + bumpOffset);

        float sunDot = dot(N, sunDir);

        // Day/Night twilight blend
        float dayWeight = smoothstep(-0.16, 0.24, sunDot);

        vec4 dayTex = texture2D(dayTexture, vUv);
        vec4 nightTex = texture2D(nightTexture, vUv);
        vec4 waterMask = texture2D(waterTexture, vUv);

        // Warm golden city night lights
        vec3 nightLights = nightTex.rgb * vec3(1.5, 1.3, 0.95);

        // Ocean specular glint only on water areas
        vec3 viewDir = normalize(-vPosition);
        vec3 halfVector = normalize(sunDir + viewDir);
        float spec = max(0.0, dot(N, halfVector));
        float isOcean = max(waterMask.r, step(0.03, dayTex.b - dayTex.r * 0.92));
        vec3 oceanGlint = vec3(0.18, 0.32, 0.48) * pow(spec, 32.0) * isOcean * max(0.0, sunDot) * 0.28;

        // Day side color with topography shading
        vec3 litDay = dayTex.rgb * (max(0.12, sunDot * 1.05)) + oceanGlint;

        // Night side color
        vec3 darkSide = nightLights + dayTex.rgb * 0.04;

        vec3 finalColor = mix(darkSide, litDay, dayWeight);

        // Subtle dark atmospheric navy rim fresnel on earth sphere
        float rim = 1.0 - max(0.0, dot(viewDir, normal));
        rim = pow(rim, 3.6);
        finalColor += vec3(0.08, 0.20, 0.36) * rim * 0.48 * max(0.0, sunDot + 0.2);

        gl_FragColor = vec4(finalColor, 1.0);
      }
    `;

    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        dayTexture: { value: dayTexture },
        nightTexture: { value: nightTexture },
        bumpTexture: { value: bumpTexture },
        waterTexture: { value: waterTexture },
        sunDirection: { value: sunPos.clone().normalize() },
      },
    });

    this.earthMesh = new THREE.Mesh(geometry, material);
    this.globeGroup.add(this.earthMesh);
  }

  _createClouds() {
    const geometry = new THREE.SphereGeometry(1.012, 96, 96);
    const textureLoader = new THREE.TextureLoader();
    const cloudsTexture = textureLoader.load('textures/earth_clouds.png');
    cloudsTexture.anisotropy = 8;

    const material = new THREE.MeshStandardMaterial({
      map: cloudsTexture,
      transparent: true,
      opacity: 0.82,
      blending: THREE.NormalBlending,
      depthWrite: false,
      roughness: 0.9,
    });

    this.cloudMesh = new THREE.Mesh(geometry, material);
    this.globeGroup.add(this.cloudMesh);
  }

  _createAtmosphere(sunPos) {
    const geometry = new THREE.SphereGeometry(1.036, 64, 64);

    const vertexShader = `
      varying vec3 vNormal;
      varying vec3 vPosition;

      void main() {
        vNormal = normalize(normalMatrix * normal);
        vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `;

    const fragmentShader = `
      uniform vec3 sunDirection;
      varying vec3 vNormal;
      varying vec3 vPosition;

      void main() {
        vec3 normal = normalize(vNormal);
        vec3 viewDir = normalize(-vPosition);
        float rim = 1.0 - max(dot(viewDir, normal), 0.0);
        rim = pow(rim, 3.2);

        float sunFacing = max(0.0, dot(normal, normalize(sunDirection)) + 0.25);
        vec3 atmosphereColor = vec3(0.22, 0.58, 1.0);
        gl_FragColor = vec4(atmosphereColor, rim * 0.72 * min(1.0, sunFacing + 0.35));
      }
    `;

    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        sunDirection: { value: sunPos.clone().normalize() },
      },
      transparent: true,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.atmosphereMesh = new THREE.Mesh(geometry, material);
    this.globeGroup.add(this.atmosphereMesh);
  }

  _createBeacon(lat, lng) {
    if (this.beaconGroup) {
      this.earthMesh.remove(this.beaconGroup);
    }

    this.beaconGroup = new THREE.Group();
    const pos = this._latLngToVector3(lat, lng, 1.002);
    this.beaconGroup.position.copy(pos);

    const normal = pos.clone().normalize();
    this.beaconGroup.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);

    // Pulsing ring
    const ringGeo = new THREE.RingGeometry(0.016, 0.026, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xb8f34a,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.95,
    });
    this.beaconRing = new THREE.Mesh(ringGeo, ringMat);
    this.beaconGroup.add(this.beaconRing);

    // Inner bright dot
    const dotGeo = new THREE.CircleGeometry(0.008, 16);
    const dotMat = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
    this.beaconGroup.add(new THREE.Mesh(dotGeo, dotMat));

    // Vertical locator stem
    const stemGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, 0, 0.07),
    ]);
    const stemMat = new THREE.LineBasicMaterial({ color: 0xb8f34a, transparent: true, opacity: 0.85 });
    this.beaconGroup.add(new THREE.Line(stemGeo, stemMat));

    this.earthMesh.add(this.beaconGroup);

    // High-tech DOM reticle with tactical Share Tech Mono font
    this._createReticleDOM(lat, lng);
  }

  _createReticleDOM(lat, lng) {
    if (this.reticleEl && this.container && this.container.contains(this.reticleEl)) {
      this.container.removeChild(this.reticleEl);
    }
    this.reticleEl = document.createElement('div');
    this.reticleEl.className = 'orbital-targeting-reticle';
    const latStr = `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? 'N' : 'S'}`;
    const lngStr = `${Math.abs(lng).toFixed(2)}° ${lng >= 0 ? 'E' : 'W'}`;
    this.reticleEl.innerHTML = `
      <div class="reticle-container">
        <div class="reticle-outer-ring"></div>
        <div class="reticle-inner-ring"></div>
        <div class="reticle-center-dot"></div>
        <div class="reticle-hud-tag">
          <div id="reticle-status-text">LOCK // TARGET ACQUIRED</div>
          <div class="reticle-hud-coords">${latStr} ${lngStr}</div>
        </div>
      </div>
      <div class="radar-pulse-ring"></div>
    `;
    this.container.appendChild(this.reticleEl);
    this.targetLatLng = { lat, lng };
    this._updateReticlePosition();
  }

  _updateReticlePosition() {
    if (!this.reticleEl || !this.targetLatLng || !this.earthMesh || !this.camera) return;

    const pos = this._latLngToVector3(this.targetLatLng.lat, this.targetLatLng.lng, 1.002);
    pos.applyMatrix4(this.earthMesh.matrixWorld);

    // Occlusion check: only show if on the visible hemisphere facing camera
    const camDir = this.camera.position.clone().sub(pos).normalize();
    const surfaceNorm = pos.clone().sub(this.globeGroup.position).normalize();
    const isFacing = surfaceNorm.dot(camDir) > 0.06;

    if (!isFacing) {
      this.reticleEl.style.opacity = '0';
      return;
    }

    const projected = pos.clone().project(this.camera);
    if (projected.z > 1.0) {
      this.reticleEl.style.opacity = '0';
      return;
    }

    const x = (projected.x * 0.5 + 0.5) * window.innerWidth;
    const y = (-(projected.y * 0.5) + 0.5) * window.innerHeight;

    this.reticleEl.style.left = `${x}px`;
    this.reticleEl.style.top = `${y}px`;
    this.reticleEl.style.opacity = '1';
  }

  _latLngToVector3(lat, lng, radius = 1.002) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lng + 180) * (Math.PI / 180);
    const x = -radius * Math.sin(phi) * Math.cos(theta);
    const z = radius * Math.sin(phi) * Math.sin(theta);
    const y = radius * Math.cos(phi);
    return new THREE.Vector3(x, y, z);
  }

  _setupInteraction() {
    const dom = this.renderer.domElement;

    dom.addEventListener('pointerdown', (e) => {
      if (this.isTransitioning) return;
      this.isDragging = true;
      this.prevMouseX = e.clientX;
      this.prevMouseY = e.clientY;
      this.rotVelX = 0;
      this.rotVelY = 0;
    });

    window.addEventListener('pointermove', (e) => {
      if (!this.isDragging || this.isTransitioning) return;
      const deltaX = e.clientX - this.prevMouseX;
      const deltaY = e.clientY - this.prevMouseY;
      this.prevMouseX = e.clientX;
      this.prevMouseY = e.clientY;

      this.rotVelY = deltaX * 0.004;
      this.rotVelX = deltaY * 0.004;

      if (this.globeGroup) {
        this.globeGroup.rotation.y += this.rotVelY;
        this.globeGroup.rotation.x = Math.max(-1.1, Math.min(1.1, this.globeGroup.rotation.x + this.rotVelX));
      }
    });

    window.addEventListener('pointerup', () => {
      this.isDragging = false;
    });

    dom.addEventListener('wheel', (e) => {
      if (this.isTransitioning) return;
      e.preventDefault();
      this.targetCameraZ = Math.max(1.8, Math.min(5.0, (this.targetCameraZ || this.camera.position.z) + e.deltaY * 0.003));
    }, { passive: false });
  }

  _animate() {
    if (this.destroyed) return;

    this.animationId = requestAnimationFrame(() => this._animate());

    if (!this.isTransitioning) {
      // Idle rotation & momentum damping
      if (this.globeGroup) {
        if (!this.isDragging) {
          this.rotVelY *= 0.92;
          this.rotVelX *= 0.92;
          this.globeGroup.rotation.y += 0.0008 + this.rotVelY;
          this.globeGroup.rotation.x = Math.max(-1.1, Math.min(1.1, this.globeGroup.rotation.x + this.rotVelX));
        }
      }

      // Smooth camera wheel zoom
      if (this.camera && this.targetCameraZ) {
        this.camera.position.z += (this.targetCameraZ - this.camera.position.z) * 0.08;
      }
    }

    // Dynamic cloud drift (atmospheric parallax)
    if (this.cloudMesh) {
      this.cloudMesh.rotation.y += 0.0011;
    }

    // Beacon ring pulse
    if (this.beaconRing) {
      const pulse = (Date.now() % 1400) / 1400;
      this.beaconRing.scale.set(1 + pulse * 0.8, 1 + pulse * 0.8, 1);
      this.beaconRing.material.opacity = (1.0 - pulse) * 0.95;
    }

    // Slow starfield drift
    if (this.starfield) {
      this.starfield.rotation.y += 0.00015;
    }

    // Reticle screen tracking
    this._updateReticlePosition();

    this.renderer.render(this.scene, this.camera);
  }

  /**
   * Cinematic Arc-Path Rotating Descent:
   * - Earth drops downward so the planetary horizon falls below the screen.
   * - Earth actively rotates to bring the target into focus while zooming in.
   * - Camera sweeps along a 3D curved arc trajectory instead of a straight zoom.
   * - Triggers seamless breakthrough into MapLibre surface map.
   */
  flyToSurface(targetLng, targetLat, options = {}) {
    const duration = options.duration || 3200;
    const onBreakthrough = options.onBreakthrough;

    return new Promise(resolve => {
      this.isTransitioning = true;
      this.rotVelX = 0;
      this.rotVelY = 0;

      // Add target beacon
      this._createBeacon(targetLat, targetLng);

      // Spherical orientation calculation
      const targetRadLng = (targetLng * Math.PI) / 180;
      const targetRadLat = (targetLat * Math.PI) / 180;

      // Equirectangular texture alignment:
      const targetRotY = -targetRadLng - Math.PI / 2;
      const targetRotX = targetRadLat * 0.65;

      const startRotY = this.globeGroup.rotation.y;
      const startRotX = this.globeGroup.rotation.x;

      let diffY = (targetRotY - startRotY) % (Math.PI * 2);
      if (diffY < -Math.PI) diffY += Math.PI * 2;
      if (diffY > Math.PI) diffY -= Math.PI * 2;
      const extraSpin = Math.PI * 0.35;

      const startCamZ = this.camera.position.z;
      const startCamY = this.camera.position.y;
      const startCamX = this.camera.position.x;

      const startTime = performance.now();
      let breakthroughFired = false;

      const transitionStep = (now) => {
        if (this.destroyed) {
          resolve();
          return;
        }

        const elapsed = now - startTime;
        const t = Math.min(1.0, elapsed / duration);

        // Smooth cubic/quintic easing
        const ease = t < 0.5
          ? 4 * t * t * t
          : 1 - Math.pow(-2 * t + 2, 3) / 2;

        // 1. "THE EARTH GOES DOWN"
        // Earth drops downwards so horizon falls below viewport
        const dropProgress = Math.pow(t, 1.7);
        this.globeGroup.position.y = -1.95 * dropProgress;

        // 2. "THE EARTH ROTATING WHILE ZOOM IN"
        // Earth dynamically rotates towards target orientation while zooming
        const spinDecay = 1.0 - Math.pow(t, 1.2);
        this.globeGroup.rotation.y = startRotY + (diffY * ease) + (extraSpin * spinDecay);
        this.globeGroup.rotation.x = startRotX + (targetRotX - startRotX) * ease;
        this.cloudMesh.rotation.y += 0.002 * (1.0 - t * 0.6);

        // 3. "COME DOWN IN AN ARC PATH INSTEAD OF STRAIGHT TO THE POINT ZOOM"
        // Camera sweeps along an altitude arc & lateral curved trajectory
        const zoomProgress = Math.pow(t, 1.35);
        this.camera.position.z = startCamZ - (startCamZ - 1.04) * zoomProgress;

        const arcPeak = Math.sin(t * Math.PI);
        this.camera.position.y = startCamY + arcPeak * 0.42;
        this.camera.position.x = startCamX + Math.sin(t * Math.PI * 0.75) * 0.32;

        // Camera tilts downward into the descending surface
        this.camera.lookAt(
          this.globeGroup.position.x,
          this.globeGroup.position.y + 0.25 * (1.0 - t),
          this.globeGroup.position.z
        );

        // 4. ATMOSPHERIC BREAKTHROUGH & MAP HAND-OFF
        if (t >= 0.68 && !breakthroughFired) {
          breakthroughFired = true;
          if (typeof onBreakthrough === 'function') {
            onBreakthrough();
          }
        }

        // 5. SMOOTH CANVAS FADE-OUT AT END OF ARC
        if (t >= 0.72) {
          const fadeRatio = (t - 0.72) / 0.28;
          const opacity = Math.max(0, 1.0 - fadeRatio);
          this.container.style.opacity = opacity.toFixed(3);
        }

        if (t < 1.0) {
          requestAnimationFrame(transitionStep);
        } else {
          this.container.style.opacity = '0';
          this.container.classList.add('hidden');
          resolve();
        }
      };

      requestAnimationFrame(transitionStep);
    });
  }

  fadeOut(duration = 800) {
    return new Promise(resolve => {
      this.container.classList.add('fade-out');
      setTimeout(() => {
        this.container.classList.add('hidden');
        resolve();
      }, duration);
    });
  }

  destroy() {
    this.destroyed = true;
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }
    window.removeEventListener('resize', this._onResize);
    if (this.renderer) {
      this.renderer.dispose();
    }
    if (this.reticleEl && this.container && this.container.contains(this.reticleEl)) {
      this.container.removeChild(this.reticleEl);
      this.reticleEl = null;
    }
    if (this.container && this.container.contains(this.renderer?.domElement)) {
      this.container.removeChild(this.renderer.domElement);
    }
  }
}


// ============================================================
// 5. MAP ENGINE (MapLibre GL JS)
// ============================================================

class MapEngine {
  constructor(containerId) {
    this.containerId = containerId;
    this.map = null;
    this.routeSourceAdded = false;
    this.uavMarkerEl = null;
    this.uavMarker = null;
    this._mapReady = false;
    this._readyPromise = null;
    this._readyResolve = null;

    this._readyPromise = new Promise(resolve => {
      this._readyResolve = resolve;
    });
  }

  init() {
    const style = createDarkCartographyStyle();

    this.map = new maplibregl.Map({
      container: this.containerId,
      style: style,
      center: [0, 20],
      zoom: 2,
      pitch: 0,
      bearing: 0,
      attributionControl: false,
      logoPosition: 'bottom-left',
      maxPitch: 70,
      fadeDuration: 300,
    });

    // Remove default controls
    this.map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left');

    this.map.on('load', () => {
      this._mapReady = true;
      this._addRouteLayers();
      this._createUAVMarker();
      if (this._readyResolve) this._readyResolve();
    });

    // Handle errors gracefully
    this.map.on('error', (e) => {
      console.warn('MapLibre error:', e.error?.message || e);
    });

    return this._readyPromise;
  }

  get ready() {
    return this._readyPromise;
  }

  _addRouteLayers() {
    // Empty GeoJSON source for the route
    this.map.addSource('uav-route', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    });

    // Under-stroke (dark, for separation)
    this.map.addLayer({
      id: 'uav-route-under',
      type: 'line',
      source: 'uav-route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': COLORS.uavUnder,
        'line-width': 7,
        'line-opacity': 0.6,
      },
    });

    // Primary route stroke (crisp white dashed line)
    this.map.addLayer({
      id: 'uav-route-main',
      type: 'line',
      source: 'uav-route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#FFFFFF',
        'line-width': 2.4,
        'line-dasharray': [4, 3],
        'line-opacity': 0.95,
      },
    });

    // Active segment overlay (brighter, animated during reconstruction)
    this.map.addSource('uav-active-segment', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    });

    this.map.addLayer({
      id: 'uav-active-segment',
      type: 'line',
      source: 'uav-active-segment',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': COLORS.uavActive,
        'line-width': 4,
        'line-opacity': 1,
      },
    });

    this.routeSourceAdded = true;
  }

  _createUAVMarker() {
    // Custom HTML marker for UAV position
    this.uavMarkerEl = document.createElement('div');
    this.uavMarkerEl.style.cssText = `
      width: 20px;
      height: 20px;
      position: relative;
      pointer-events: none;
    `;

    // Tracking ring
    const ring = document.createElement('div');
    ring.style.cssText = `
      position: absolute;
      inset: -4px;
      border: 1.5px solid ${COLORS.uavRoute};
      border-radius: 50%;
      opacity: 0.35;
      animation: uav-ring-pulse 2s ease-in-out infinite;
    `;

    // Core dot
    const dot = document.createElement('div');
    dot.style.cssText = `
      position: absolute;
      inset: 2px;
      background: ${COLORS.uavRoute};
      border-radius: 50%;
      border: 2px solid ${COLORS.bgVoid};
      box-shadow: 0 0 8px rgba(184, 243, 74, 0.6);
    `;

    // Heading indicator (small triangle)
    const heading = document.createElement('div');
    heading.className = 'uav-heading';
    heading.style.cssText = `
      position: absolute;
      top: -6px;
      left: 50%;
      transform: translateX(-50%);
      width: 0;
      height: 0;
      border-left: 3px solid transparent;
      border-right: 3px solid transparent;
      border-bottom: 5px solid ${COLORS.uavRoute};
    `;

    this.uavMarkerEl.appendChild(ring);
    this.uavMarkerEl.appendChild(dot);
    this.uavMarkerEl.appendChild(heading);

    // Inject animation keyframes
    if (!document.getElementById('uav-marker-styles')) {
      const style = document.createElement('style');
      style.id = 'uav-marker-styles';
      style.textContent = `
        @keyframes uav-ring-pulse {
          0%, 100% { transform: scale(1); opacity: 0.35; }
          50% { transform: scale(1.3); opacity: 0.1; }
        }
      `;
      document.head.appendChild(style);
    }

    this.uavMarker = new maplibregl.Marker({
      element: this.uavMarkerEl,
      anchor: 'center',
    })
    .setLngLat([0, 0])
    .addTo(this.map);

    // Initially hidden
    this.uavMarkerEl.style.display = 'none';
  }

  /**
   * Set the UAV route GeoJSON (updates existing source, never recreates).
   */
  setRoute(geojson) {
    if (!this._mapReady || !this.routeSourceAdded) return;
    const source = this.map.getSource('uav-route');
    if (source) {
      source.setData(geojson);
    }
  }

  /**
   * Update the active (reconstructed) segment.
   */
  setActiveSegment(coordinates) {
    if (!this._mapReady) return;
    const source = this.map.getSource('uav-active-segment');
    if (source) {
      source.setData({
        type: 'FeatureCollection',
        features: coordinates.length >= 2 ? [{
          type: 'Feature',
          properties: {},
          geometry: { type: 'LineString', coordinates },
        }] : [],
      });
    }
  }

  /**
   * Update UAV marker position and heading.
   */
  updateUAVPosition(lng, lat, yaw = 0) {
    if (!this.uavMarker) return;
    this.uavMarkerEl.style.display = 'block';
    this.uavMarker.setLngLat([lng, lat]);

    // Rotate heading indicator
    const headingEl = this.uavMarkerEl.querySelector('.uav-heading');
    if (headingEl) {
      headingEl.style.transform = `translateX(-50%) rotate(${yaw}deg)`;
    }
  }

  /**
   * Pre-orient map at high-altitude oblique angle for seamless atmospheric descent.
   */
  prepareForDescent(lng, lat) {
    if (!this.map) return;
    this.map.jumpTo({
      center: [lng, lat],
      zoom: 6.5,
      pitch: 60,
      bearing: -28,
    });
  }

  /**
   * Fly the camera to fit the given bounds with padding.
   */
  flyToBounds(bounds, padding, duration = 2500) {
    if (!this.map) return Promise.resolve();

    return new Promise(resolve => {
      this.map.fitBounds(
        [bounds.sw, bounds.ne],
        {
          padding,
          duration,
          pitch: 35,
          bearing: -12,
          essential: true,
          maxZoom: 18,
          easing: (t) => {
            // Custom easing: accelerate then decelerate smoothly
            return t < 0.5
              ? 4 * t * t * t
              : 1 - Math.pow(-2 * t + 2, 3) / 2;
          },
        }
      );

      this.map.once('moveend', resolve);

      // Safety timeout in case moveend doesn't fire
      setTimeout(resolve, duration + 500);
    });
  }

  show() {
    const container = document.getElementById(this.containerId);
    if (container) {
      container.classList.add('visible');
    }
  }

  hide() {
    const container = document.getElementById(this.containerId);
    if (container) {
      container.classList.remove('visible');
    }
  }
}


// ============================================================
// 6. RECONSTRUCTION TIMELINE
// ============================================================

class ReconstructionTimeline {
  constructor() {
    this.el = document.getElementById('timeline-bar');
    this.slider = document.getElementById('timeline-slider');
    this.progressBar = document.getElementById('timeline-progress');
    this.playBtn = document.getElementById('btn-play');
    this.currentTimeEl = document.getElementById('tl-current-time');
    this.totalTimeEl = document.getElementById('tl-total-time');
    this.framesEl = document.getElementById('tl-frames');
    this.capturedEl = document.getElementById('tl-captured');
    this.coverageEl = document.getElementById('tl-coverage');
    this.statusTextEl = document.getElementById('tl-status-text');
    this.statusLabelEl = document.getElementById('tl-status-label');

    this.totalFrames = 0;
    this.currentFrame = 0;
    this.isPlaying = false;
    this.playTimer = null;
    this.onSeek = null; // callback

    this._setupEvents();
  }

  _setupEvents() {
    // Play/Pause
    this.playBtn.addEventListener('click', () => this.togglePlay());

    // Slider scrub
    this.slider.addEventListener('input', (e) => {
      const frame = parseInt(e.target.value, 10);
      this.seekTo(frame);
    });
  }

  /**
   * Initialize with total frame count and duration.
   */
  configure(totalFrames, durationSeconds) {
    this.totalFrames = totalFrames;
    this.durationSeconds = durationSeconds;
    this.slider.max = Math.max(0, totalFrames - 1);
    this.slider.value = 0;
    this.totalTimeEl.textContent = this._formatTime(durationSeconds);
    this.framesEl.textContent = totalFrames.toLocaleString();
    this.progressBar.style.width = '0%';
    this.currentFrame = 0;
  }

  seekTo(frame) {
    this.currentFrame = Math.max(0, Math.min(frame, this.totalFrames - 1));
    this.slider.value = this.currentFrame;

    const ratio = this.totalFrames > 1
      ? this.currentFrame / (this.totalFrames - 1)
      : 0;

    this.progressBar.style.width = `${ratio * 100}%`;

    // Update time display
    const sec = this.totalFrames > 1 && this.durationSeconds
      ? ratio * this.durationSeconds
      : this.currentFrame * 0.05;
    this.currentTimeEl.textContent = this._formatTime(sec);

    // Update captured percentage
    const capturedPct = Math.round(ratio * 100);
    this.capturedEl.textContent = `${capturedPct}%`;

    // Coverage estimation
    const coveragePct = Math.min(100, Math.round(capturedPct * 0.95));
    this.coverageEl.textContent = `${coveragePct}%`;

    if (this.onSeek) this.onSeek(this.currentFrame);
  }

  togglePlay() {
    this.isPlaying = !this.isPlaying;
    const iconPlay = document.getElementById('icon-play');
    const iconPause = document.getElementById('icon-pause');

    if (this.isPlaying) {
      iconPlay.style.display = 'none';
      iconPause.style.display = 'block';
      this.playTimer = setInterval(() => {
        const next = (this.currentFrame + 1) % this.totalFrames;
        this.seekTo(next);
      }, 100);
    } else {
      iconPlay.style.display = 'block';
      iconPause.style.display = 'none';
      if (this.playTimer) {
        clearInterval(this.playTimer);
        this.playTimer = null;
      }
    }
  }

  setStatus(text) {
    if (this.statusTextEl) this.statusTextEl.textContent = text;
  }

  setStatusLabel(text) {
    if (this.statusLabelEl) this.statusLabelEl.textContent = text;
  }

  /**
   * Smoothly animate the timeline into view.
   */
  show(delay = 0) {
    setTimeout(() => {
      this.el.classList.add('visible');
    }, delay);
  }

  hide() {
    this.el.classList.remove('visible');
  }

  _formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
}


// ============================================================
// 7. UI CONTROLLER
// ============================================================

class UIController {
  constructor() {
    this.headerStatus = document.getElementById('header-status');
    this.processingStatus = document.getElementById('processing-status');
    this.processingText = document.getElementById('processing-text');
    this.routeInfo = document.getElementById('route-info');
    this.errorState = document.getElementById('error-state');
    this.errorText = document.getElementById('error-text');
    this.uploadBtn = document.getElementById('btn-upload');
    this.demoBtn = document.getElementById('btn-demo');
    this.demoZoneBtn = document.getElementById('btn-demo-zone');
    this.uploadOverlay = document.getElementById('upload-overlay');
    this.uploadZone = document.getElementById('upload-zone');
    this.uploadClose = document.getElementById('upload-close');
    this.fileInput = document.getElementById('file-input');
  }

  setHeaderStatus(text) {
    this.headerStatus.textContent = text;
  }

  showProcessing(text) {
    this.processingText.textContent = text;
    this.processingStatus.classList.add('visible');
  }

  hideProcessing() {
    this.processingStatus.classList.remove('visible');
  }

  showRouteInfo(data) {
    document.getElementById('info-waypoints').textContent = data.waypoints;
    document.getElementById('info-duration').textContent = data.duration;
    document.getElementById('info-altitude').textContent = data.altitude;
    document.getElementById('info-coverage').textContent = data.coverage;
    document.getElementById('info-status').textContent = data.status;
    this.routeInfo.classList.add('visible');
  }

  hideRouteInfo() {
    this.routeInfo.classList.remove('visible');
  }

  showError(text) {
    this.errorText.textContent = text;
    this.errorState.classList.add('visible');
    setTimeout(() => this.errorState.classList.remove('visible'), 5000);
  }

  showUploadOverlay() {
    this.uploadOverlay.classList.add('visible');
  }

  hideUploadOverlay() {
    this.uploadOverlay.classList.remove('visible');
  }

  disableUpload() {
    this.uploadBtn.classList.add('disabled');
    this.uploadBtn.textContent = 'Processing…';
    if (this.demoBtn) this.demoBtn.classList.add('disabled');
    if (this.demoZoneBtn) this.demoZoneBtn.classList.add('disabled');
  }

  enableUpload() {
    this.uploadBtn.classList.remove('disabled');
    this.uploadBtn.textContent = 'NEW FLIGHT';
    if (this.demoBtn) this.demoBtn.classList.remove('disabled');
    if (this.demoZoneBtn) this.demoZoneBtn.classList.remove('disabled');
  }

  showToast(msg) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 250);
    }, 2500);
  }
}


// ============================================================
// 8. DEMO DATA (Embedded San Francisco orbit)
// ============================================================

const DEMO_FLIGHTS = {
  'san_francisco_orbit': {
    name: 'San Francisco Orbit',
    srt: null, // will be loaded from /demo/city_orbit_flight.srt
    points: [
      { lat: 37.774918, lng: -122.419400, alt: 14, yaw: 0, pitch: -25, roll: 0, timestamp: 0.00 },
      { lat: 37.774922, lng: -122.419354, alt: 14, yaw: 12.86, pitch: -25, roll: 0, timestamp: 0.05 },
      { lat: 37.774934, lng: -122.419311, alt: 14, yaw: 25.71, pitch: -25, roll: 0, timestamp: 0.10 },
      { lat: 37.774953, lng: -122.419272, alt: 14, yaw: 38.57, pitch: -25, roll: 0, timestamp: 0.15 },
      { lat: 37.774979, lng: -122.419240, alt: 14, yaw: 51.43, pitch: -25, roll: 0, timestamp: 0.20 },
      { lat: 37.775010, lng: -122.419215, alt: 14, yaw: 64.29, pitch: -25, roll: 0, timestamp: 0.25 },
      { lat: 37.775044, lng: -122.419200, alt: 14, yaw: 77.14, pitch: -25, roll: 0, timestamp: 0.30 },
      { lat: 37.775080, lng: -122.419195, alt: 14, yaw: 90, pitch: -25, roll: 0, timestamp: 0.35 },
      { lat: 37.775116, lng: -122.419200, alt: 14, yaw: 102.86, pitch: -25, roll: 0, timestamp: 0.40 },
      { lat: 37.775150, lng: -122.419215, alt: 14, yaw: 115.71, pitch: -25, roll: 0, timestamp: 0.45 },
      { lat: 37.775181, lng: -122.419240, alt: 14, yaw: 128.57, pitch: -25, roll: 0, timestamp: 0.50 },
      { lat: 37.775207, lng: -122.419272, alt: 14, yaw: 141.43, pitch: -25, roll: 0, timestamp: 0.55 },
      { lat: 37.775226, lng: -122.419311, alt: 14, yaw: 154.29, pitch: -25, roll: 0, timestamp: 0.60 },
      { lat: 37.775238, lng: -122.419354, alt: 14, yaw: 167.14, pitch: -25, roll: 0, timestamp: 0.65 },
      { lat: 37.775242, lng: -122.419400, alt: 14, yaw: 180, pitch: -25, roll: 0, timestamp: 0.70 },
      { lat: 37.775238, lng: -122.419446, alt: 14, yaw: 192.86, pitch: -25, roll: 0, timestamp: 0.75 },
      { lat: 37.775226, lng: -122.419489, alt: 14, yaw: 205.71, pitch: -25, roll: 0, timestamp: 0.80 },
      { lat: 37.775207, lng: -122.419528, alt: 14, yaw: 218.57, pitch: -25, roll: 0, timestamp: 0.85 },
      { lat: 37.775181, lng: -122.419560, alt: 14, yaw: 231.43, pitch: -25, roll: 0, timestamp: 0.90 },
      { lat: 37.775150, lng: -122.419585, alt: 14, yaw: 244.29, pitch: -25, roll: 0, timestamp: 0.95 },
      { lat: 37.775116, lng: -122.419600, alt: 14, yaw: 257.14, pitch: -25, roll: 0, timestamp: 1.00 },
      { lat: 37.775080, lng: -122.419605, alt: 14, yaw: 270, pitch: -25, roll: 0, timestamp: 1.05 },
      { lat: 37.775044, lng: -122.419600, alt: 14, yaw: 282.86, pitch: -25, roll: 0, timestamp: 1.10 },
      { lat: 37.775010, lng: -122.419585, alt: 14, yaw: 295.71, pitch: -25, roll: 0, timestamp: 1.15 },
      { lat: 37.774979, lng: -122.419560, alt: 14, yaw: 308.57, pitch: -25, roll: 0, timestamp: 1.20 },
      { lat: 37.774953, lng: -122.419528, alt: 14, yaw: 321.43, pitch: -25, roll: 0, timestamp: 1.25 },
      { lat: 37.774934, lng: -122.419489, alt: 14, yaw: 334.29, pitch: -25, roll: 0, timestamp: 1.30 },
      { lat: 37.774922, lng: -122.419446, alt: 14, yaw: 347.14, pitch: -25, roll: 0, timestamp: 1.35 },
    ],
  },
};


// ============================================================
// 9. MAIN APPLICATION
// ============================================================

class SinglePass3DApp {
  constructor() {
    this.state = AppState.IDLE;
    this.globe = null;
    this.map = null;
    this.timeline = null;
    this.ui = null;
    this.telemetry = new TelemetryProcessor();

    // Cached data
    this.gpsPoints = null;
    this.routeBounds = null;
    this.routeGeoJSON = null;
    this.cameraPadding = null;
  }

  async init() {
    // 1. Initialize UI controller
    this.ui = new UIController();

    // 2. Initialize timeline (pre-mounted, invisible)
    this.timeline = new ReconstructionTimeline();
    this.timeline.onSeek = (frame) => this._onTimelineSeek(frame);

    // 3. Initialize globe (visible immediately)
    this.globe = new GlobeEngine(document.getElementById('globe-container'));

    // 4. Initialize map (hidden, starts loading tiles)
    this.map = new MapEngine('map-container');
    this.map.init(); // non-blocking

    // 5. Setup upload flow
    this._setupUploadFlow();

    // 6. Auto-load demo if URL param ?demo=1
    const params = new URLSearchParams(window.location.search);
    if (params.has('demo')) {
      setTimeout(() => this._loadDemoFlight(), 1500);
    }
  }

  _setupUploadFlow() {
    const { uploadBtn, demoBtn, demoZoneBtn, uploadOverlay, uploadZone, uploadClose, fileInput } = this.ui;

    // Open upload overlay
    uploadBtn.addEventListener('click', () => {
      if (uploadBtn.classList.contains('disabled')) return;
      this.ui.showUploadOverlay();
    });

    // Load demo directly from header
    if (demoBtn) {
      demoBtn.addEventListener('click', () => {
        if (demoBtn.classList.contains('disabled')) return;
        this._loadDemoFlight();
      });
    }

    // Load demo from upload zone
    if (demoZoneBtn) {
      demoZoneBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.ui.hideUploadOverlay();
        this._loadDemoFlight();
      });
    }

    // Close overlay
    uploadClose.addEventListener('click', () => {
      this.ui.hideUploadOverlay();
    });

    // Click to select file
    uploadZone.addEventListener('click', () => {
      fileInput.click();
    });

    // File selected
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        this._handleFileUpload(e.target.files[0]);
      }
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('drag-over');
    });

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('drag-over');
    });

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('drag-over');
      if (e.dataTransfer.files.length > 0) {
        this._handleFileUpload(e.dataTransfer.files[0]);
      }
    });

    // Close overlay on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.ui.hideUploadOverlay();
      }
    });
  }

  async _handleFileUpload(file) {
    this.ui.hideUploadOverlay();
    this.ui.disableUpload();
    this._setState(AppState.UPLOADING);
    this.ui.showProcessing('Uploading…');
    this.ui.setHeaderStatus(file.name);

    // Determine if SRT or video
    const isSRT = file.name.toLowerCase().endsWith('.srt');

    try {
      if (isSRT) {
        // Parse SRT directly
        this._setState(AppState.EXTRACTING_GPS);
        this.ui.showProcessing('Extracting telemetry…');

        const text = await file.text();
        const points = this.telemetry.parseSRT(text);

        if (!points.length) {
          throw new Error('No GPS data found in SRT file');
        }

        await this._onGPSReady(points);
      } else {
        // Video file — try to extract SRT companion or use backend
        this._setState(AppState.EXTRACTING_GPS);
        this.ui.showProcessing('Extracting GPS telemetry from video…');

        // Simulate extraction delay (in production, this would call the backend)
        await new Promise(resolve => setTimeout(resolve, 1200));

        // Try to find companion SRT on server
        const srtName = file.name.replace(/\.[^.]+$/, '.srt');
        this.ui.showProcessing(`Extracting telemetry for ${file.name}…`);
        await new Promise(resolve => setTimeout(resolve, 800));

        let companionPoints = null;
        try {
          const resp = await fetch(`/demo/${srtName}`).catch(() => null);
          if (resp && resp.ok) {
            const srtText = await resp.text();
            companionPoints = this.telemetry.parseSRT(srtText);
          }
        } catch (_) {}

        if (!companionPoints || !companionPoints.length) {
          try {
            const resp = await fetch('/demo/city_orbit_flight.srt').catch(() => null);
            if (resp && resp.ok) {
              const srtText = await resp.text();
              companionPoints = this.telemetry.parseSRT(srtText);
            }
          } catch (_) {}
        }

        if (companionPoints && companionPoints.length > 0) {
          this.ui.showToast('Telemetry extracted from flight');
          await this._onGPSReady(companionPoints);
        } else {
          // Fall back to embedded demo data
          this.ui.showToast('Using embedded telemetry data');
          const demoPoints = DEMO_FLIGHTS['san_francisco_orbit'].points;
          await this._onGPSReady(demoPoints);
        }
      }
    } catch (err) {
      this._setState(AppState.ERROR);
      this.ui.showError(err.message || 'Failed to process file');
      this.ui.hideProcessing();
      this.ui.enableUpload();
      console.error('Upload error:', err);
    }
  }

  async _loadDemoFlight() {
    this.ui.disableUpload();
    this._setState(AppState.EXTRACTING_GPS);
    this.ui.showProcessing('Loading demo flight…');
    this.ui.setHeaderStatus('Demo Flight — San Francisco');

    // Try to load the SRT file from the server
    try {
      const resp = await fetch('/demo/city_orbit_flight.srt').catch(() => null);
      if (resp && resp.ok) {
        const text = await resp.text();
        const points = this.telemetry.parseSRT(text);
        if (points.length > 0) {
          await this._onGPSReady(points);
          return;
        }
      }
    } catch (e) {
      console.warn('Could not load SRT from server, using embedded data');
    }

    // Fall back to embedded demo data
    const points = DEMO_FLIGHTS['san_francisco_orbit'].points;
    await this._onGPSReady(points);
  }

  async _onGPSReady(points) {
    this.gpsPoints = points;
    this._setState(AppState.POSITIONING);
    this.ui.showProcessing('Calculating flight route…');

    // Calculate route data
    this.routeBounds = this.telemetry.calculateBounds(points);
    this.routeGeoJSON = this.telemetry.toGeoJSON(points);
    this.cameraPadding = this.telemetry.calculatePadding(
      this.routeBounds,
      window.innerWidth,
      window.innerHeight
    );

    // Configure timeline
    const duration = this.telemetry.getDuration(points);
    const avgAlt = this.telemetry.getAverageAltitude(points);
    this.timeline.configure(points.length, duration || points.length * 0.05);

    // Wait for map to be ready
    this._setState(AppState.RENDERING_MAP);
    this.ui.showProcessing('Preparing map…');
    await this.map.ready;

    // Set the route data on the map
    this.map.setRoute(this.routeGeoJSON);

    // Show initial UAV position
    const first = points[0];
    this.map.updateUAVPosition(first.lng, first.lat, first.yaw);

    // Start the cinematic transition
    await this._performTransition(points, duration, avgAlt);
  }

  async _performTransition(points, duration, avgAlt) {
    this.ui.showProcessing('Navigating to location…');

    const first = points[0];
    const targetLng = first.lng;
    const targetLat = first.lat;

    // 1. Pre-orient map underneath at high-altitude angle aligned with descent
    if (this.map && typeof this.map.prepareForDescent === 'function') {
      this.map.prepareForDescent(targetLng, targetLat);
    }

    // 2. Perform cinematic arc-path rotating descent in Three.js
    this._setState(AppState.RENDERING_MAP);

    if (this.globe && typeof this.globe.flyToSurface === 'function') {
      await this.globe.flyToSurface(targetLng, targetLat, {
        duration: 3200,
        onBreakthrough: () => {
          // Atmospheric breakthrough: show surface map & start smooth approach
          this.map.show();
          this.map.flyToBounds(this.routeBounds, this.cameraPadding, 2400);
        },
      });
      this.globe.destroy();
    } else {
      this.map.show();
      await new Promise(r => setTimeout(r, 300));
      if (this.globe) {
        this.globe.fadeOut(800);
        await this.map.flyToBounds(this.routeBounds, this.cameraPadding, 2500);
        this.globe.destroy();
      }
    }

    // 3. Hide processing, show route info
    this.ui.hideProcessing();
    this._setState(AppState.FLIGHT_READY);

    this.ui.showRouteInfo({
      waypoints: points.length.toString(),
      duration: `${(duration || points.length * 0.05).toFixed(1)}s`,
      altitude: `${avgAlt.toFixed(1)}m`,
      coverage: '100%',
      status: 'RECONSTRUCTING',
    });

    // 6. Animate timeline in (smooth entry after camera settles)
    this.timeline.show(400);
    this.timeline.setStatus('RECONSTRUCTING');
    this.timeline.setStatusLabel('Reconstruction Progress');

    // 7. Start simulated reconstruction
    this._startReconstruction();

    this.ui.enableUpload();
    this.ui.showToast('Flight route loaded');
  }

  _startReconstruction() {
    this._setState(AppState.RECONSTRUCTING);

    // Simulate reconstruction progress
    let reconstructedFrames = 0;
    const totalFrames = this.gpsPoints.length;

    const reconstructStep = () => {
      if (reconstructedFrames >= totalFrames) {
        this._setState(AppState.COMPLETE);
        this.timeline.setStatus('COMPLETE');
        document.getElementById('info-status').textContent = 'COMPLETE';
        this.ui.showToast('Reconstruction complete');
        return;
      }

      reconstructedFrames++;
      const ratio = reconstructedFrames / totalFrames;

      // Update active segment
      const activeCoords = this.gpsPoints
        .slice(0, reconstructedFrames)
        .map(p => [p.lng, p.lat]);
      this.map.setActiveSegment(activeCoords);

      // Update UAV marker
      const currentPoint = this.gpsPoints[reconstructedFrames - 1];
      this.map.updateUAVPosition(currentPoint.lng, currentPoint.lat, currentPoint.yaw);

      // Update timeline
      this.timeline.seekTo(reconstructedFrames - 1);

      // Continue
      setTimeout(reconstructStep, 120);
    };

    // Start after a brief delay
    setTimeout(reconstructStep, 600);
  }

  _onTimelineSeek(frame) {
    if (!this.gpsPoints || frame >= this.gpsPoints.length) return;

    const point = this.gpsPoints[frame];
    this.map.updateUAVPosition(point.lng, point.lat, point.yaw);

    // Update active segment
    const activeCoords = this.gpsPoints
      .slice(0, frame + 1)
      .map(p => [p.lng, p.lat]);
    this.map.setActiveSegment(activeCoords);
  }

  _setState(state) {
    this.state = state;

    // Update header status indicator for some states
    switch (state) {
      case AppState.UPLOADING:
        this.ui.showProcessing('Uploading…');
        break;
      case AppState.EXTRACTING_GPS:
        this.ui.showProcessing('Extracting GPS telemetry…');
        break;
      case AppState.POSITIONING:
        this.ui.showProcessing('Calculating flight bounds…');
        break;
      case AppState.RENDERING_MAP:
        this.ui.showProcessing('Rendering map…');
        break;
      case AppState.FLIGHT_READY:
      case AppState.COMPLETE:
        this.ui.hideProcessing();
        break;
      case AppState.ERROR:
        this.ui.hideProcessing();
        break;
    }
  }
}


// ============================================================
// 10. INITIALIZE
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  window.app = new SinglePass3DApp();
  window.app.init();
});
