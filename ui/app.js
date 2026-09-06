/**
 * SinglePass3D — Video Input alongside Reconstructed 3D Model Studio
 * Full orientation controls & viewpoint presets.
 */

class SinglePass3DViewer {
  constructor() {
    this.container = document.getElementById('model-panel');
    this.canvas = document.getElementById('webgl-canvas');
    
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.gridHelper = null;
    
    // Master Group for 3D model, trajectory, and marker
    this.modelRootGroup = null;
    
    // Default to real Zurich MAV reconstruction
    this.currentJob = 'zurich_mav_reconstruction';
    this.modelMesh = null;
    this.pointCloud = null;
    this.modelOffset = new THREE.Vector3(0, 0, 0);
    this.trajectoryGroup = null;
    this.cameraMarker = null;
    this.cameraFrustums = [];
    this.trajectoryData = null;
    
    this.shadingMode = 'rgb';
    this.showTrajectory = true;
    this.showWireframe = false;
    this.showPointCloud = false;
    
    this.totalFrames = 40;
    this.currentFrameIdx = 0;
    this.isPlaying = false;
    this.playbackTimer = null;
    this.currentMaxDim = 40;
    
    this.originalColors = null;
    this.vertexNormals = null;
    
    // Interaction Mode: 'orbit' (Camera orbit) vs 'rotate_model' (Direct model-only rotation)
    this.interactionMode = 'orbit';
    this.isDraggingModel = false;
    this.lastPointerX = 0;
    this.lastPointerY = 0;

    // Spatial Analysis & 3D Ruler Measurement Toolkit
    this.rulerActive = false;
    this.rulerPoints = [];
    this.rulerMarkers = [];
    this.rulerLine = null;
    this.measurementsData = null;
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    
    this.initThree();
    this.setupModelDragControls();
    this.setupRulerControls();
    this.setupEventListeners();
    this.loadJobList();
  }

  initThree() {
    // 1. Scene Setup
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0f18);
    this.scene.fog = new THREE.FogExp2(0x0a0f18, 0.006);

    // 2. Camera Setup
    const width = this.container.clientWidth || (window.innerWidth / 2);
    const height = this.container.clientHeight || (window.innerHeight - 54);
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 3000);
    this.camera.position.set(0, -60, 45);
    this.camera.up.set(0, 0, 1); // Z is UP

    // 3. WebGL Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.95;
    this.renderer.shadowMap.enabled = true;

    // 4. Orbit Controls (Rotate: Left-Click, Pan: Right-Click, Zoom: Wheel)
    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.screenSpacePanning = true;

    // 5. Balanced Lighting (Eliminate washed-out overexposure)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.40);
    this.scene.add(ambientLight);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x334155, 0.30);
    hemiLight.position.set(0, 0, 100);
    this.scene.add(hemiLight);

    const sunLight1 = new THREE.DirectionalLight(0xfff7ed, 0.70);
    sunLight1.position.set(40, -60, 80);
    sunLight1.castShadow = true;
    sunLight1.shadow.mapSize.width = 2048;
    sunLight1.shadow.mapSize.height = 2048;
    sunLight1.shadow.camera.near = 0.5;
    sunLight1.shadow.camera.far = 500;
    this.scene.add(sunLight1);

    const sunLight2 = new THREE.DirectionalLight(0x93c5fd, 0.25);
    sunLight2.position.set(-40, 60, 30);
    this.scene.add(sunLight2);

    // 6. Ground Reference Grid
    this.gridHelper = new THREE.GridHelper(100, 50, 0x38bdf8, 0x1e293b);
    this.gridHelper.rotation.x = Math.PI / 2;
    this.gridHelper.position.z = -0.05;
    this.scene.add(this.gridHelper);

    // 7. Master Root Group for all model elements
    this.modelRootGroup = new THREE.Group();
    this.scene.add(this.modelRootGroup);

    // 8. Active Camera Position Marker (Drone Cone)
    const markerGeom = new THREE.ConeGeometry(0.8, 1.8, 8);
    markerGeom.rotateX(Math.PI / 2);
    const markerMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b, wireframe: false });
    this.cameraMarker = new THREE.Mesh(markerGeom, markerMat);
    this.cameraMarker.visible = false;
    this.modelRootGroup.add(this.cameraMarker);

    // 9. Render Loop
    const animate = () => {
      requestAnimationFrame(animate);
      if (this.controls) {
        this.controls.update();
      }
      this.renderer.render(this.scene, this.camera);
    };
    animate();

    // Responsive Resize Observer
    const resizeObserver = new ResizeObserver(() => {
      const w = this.container.clientWidth;
      const h = this.container.clientHeight;
      if (w > 0 && h > 0) {
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
      }
    });
    resizeObserver.observe(this.container);
  }

  async loadJobList() {
    try {
      const resp = await fetch('/api/jobs');
      if (resp.ok) {
        const jobs = await resp.json();
        const sel = document.getElementById('job-selector');
        sel.innerHTML = '';
        
        const friendlyLabels = {
          'church_orbit': 'Historic Church Aerial Orbit (New Video Input)',
          'agz_optA': 'Option A: Reference-Guided UV Inpainting (Sharpest Texture)',
          'agz_optB': 'Option B: Multi-View Generative Gap Closure (Continuous Mesh)',
          'agz_optC': 'Option C: Targeted Courtyard Patch (Closed Sign & Column)',
          'agz_v12': 'AGZ v12 (Restored Background Building + Sharp Baseline)',
          'zurich_mav_reconstruction': 'Zurich Urban MAV (Production 3D Model)',
          'zurich_mav_high_res': 'Zurich Urban MAV (Ultra High-Res)',
          'city_orbit_high_res': 'City Orbit Flight (360° Panoramic)',
          'loop_closure_high_res': 'Loop Closure Flight (Drift-Corrected)',
          'agz_full': 'Air-Ground Zurich (Full Continuous)',
          'job_orbit_high': 'High-Density Orbit Survey',
          'job_001': 'Drone Orbit Survey (Demo 001)'
        };

        jobs.forEach(job => {
          const opt = document.createElement('option');
          opt.value = job;
          opt.textContent = friendlyLabels[job] || job;
          sel.appendChild(opt);
        });

        const urlParams = new URLSearchParams(window.location.search);
        const requestedJob = urlParams.get('job');
        if (requestedJob && jobs.includes(requestedJob)) {
          this.currentJob = requestedJob;
          sel.value = this.currentJob;
        } else if (jobs.length > 0) {
          this.currentJob = jobs[0];
          sel.value = this.currentJob;
        }
      }
    } catch (e) {
      console.log('Using default local job list:', e);
    }
    this.loadJobData(this.currentJob);
  }

  async loadJobData(jobId) {
    this.showToast(`Loading: ${jobId}...`);
    this.clearScene();
    this.currentJob = jobId;
    
    try {
      // 1. Fetch Trajectory JSON
      const trajResp = await fetch(`/outputs/${jobId}/trajectory.json`).catch(() => null);
      if (trajResp && trajResp.ok) {
        this.trajectoryData = await trajResp.json();
      } else {
        this.trajectoryData = null;
      }

      // 2. Load 3D Model (GLB or PLY)
      await this.load3DModel(jobId);

      // 3. Render Trajectory Spline & Frustums
      if (this.trajectoryData) {
        this.renderTrajectory(this.trajectoryData);
      }
      
      // 4. Initialize Video Frame Stream
      this.initVideoFrameStream(jobId);
      this.loadSpatialMeasurements();
      
      this.showToast(`Loaded ${jobId} successfully!`);
    } catch (err) {
      console.error('Failed to load job data:', err);
      this.loadSpatialMeasurements();
      this.showToast(`Loaded ${jobId}`);
    }
  }

  clearScene() {
    if (this.modelMesh) {
      this.modelRootGroup.remove(this.modelMesh);
      this.modelMesh = null;
    }
    if (this.pointCloud) {
      this.modelRootGroup.remove(this.pointCloud);
      this.pointCloud = null;
    }
    if (this.trajectoryGroup) {
      this.modelRootGroup.remove(this.trajectoryGroup);
      this.trajectoryGroup = null;
    }
    this.cameraFrustums = [];
    if (this.cameraMarker) this.cameraMarker.visible = false;
    this.modelOffset.set(0, 0, 0);
    this.modelRootGroup.rotation.set(0, 0, 0);
  }

  initVideoFrameStream(jobId) {
    const frameCount = (this.trajectoryData?.frame_ids?.length) || 40;
    this.totalFrames = frameCount;

    const slider = document.getElementById('frame-slider');
    slider.max = frameCount - 1;
    slider.value = 0;
    
    this.seekFrame(0);
  }

  seekFrame(idx) {
    this.currentFrameIdx = idx;
    const padNum = (num, size) => {
      let s = num + "";
      while (s.length < size) s = "0" + s;
      return s;
    };

    const imgEl = document.getElementById('drone-frame-img');
    const hudFrame = document.getElementById('hud-frame');
    const hudTime = document.getElementById('hud-timestamp');
    const labelCurFrame = document.getElementById('label-cur-frame');
    const labelCurTime = document.getElementById('label-cur-time');

    let frameId = idx;
    let timestamp = (idx / 30.0);
    
    if (this.trajectoryData?.frame_ids && idx < this.trajectoryData.frame_ids.length) {
      frameId = this.trajectoryData.frame_ids[idx];
      timestamp = this.trajectoryData.timestamps ? this.trajectoryData.timestamps[idx] : (frameId / 30.0);
    }

    const frameFile = `/outputs/${this.currentJob}/frames/proxy/frame_${padNum(frameId, 6)}_proxy.jpg`;
    imgEl.src = frameFile;

    hudFrame.textContent = `Frame: ${padNum(frameId, 3)} / ${padNum(this.totalFrames, 3)}`;
    hudTime.textContent = `Time: ${timestamp.toFixed(2)}s`;
    labelCurFrame.textContent = `Frame: ${frameId} / ${this.totalFrames}`;
    labelCurTime.textContent = `${timestamp.toFixed(2)}s`;

    // Move camera marker in 3D scene (shifted by model offset)
    if (this.trajectoryData?.poses) {
      const poseKey = String(frameId);
      const pose = this.trajectoryData.poses[poseKey] || Object.values(this.trajectoryData.poses)[idx];
      if (pose && pose.t_wc && this.cameraMarker) {
        const t = pose.t_wc;
        this.cameraMarker.position.set(
          t[0] - this.modelOffset.x,
          t[1] - this.modelOffset.y,
          t[2] - this.modelOffset.z
        );
        this.cameraMarker.visible = true;

        if (pose.R_wc) {
          const m = new THREE.Matrix4();
          const r = pose.R_wc;
          m.set(
            r[0][0], r[0][1], r[0][2], 0,
            r[1][0], r[1][1], r[1][2], 0,
            r[2][0], r[2][1], r[2][2], 0,
            0, 0, 0, 1
          );
          this.cameraMarker.setRotationFromMatrix(m);
        }

        // Highlight matching frustum
        this.cameraFrustums.forEach((frustum, fIdx) => {
          const line = frustum.children[0];
          if (line) {
            line.material.color.setHex(fIdx === idx ? 0xf59e0b : 0x38bdf8);
          }
        });
      }
    }
  }

  togglePlay() {
    this.isPlaying = !this.isPlaying;
    const iconPlay = document.getElementById('icon-play');
    const iconPause = document.getElementById('icon-pause');
    
    if (this.isPlaying) {
      iconPlay.style.display = 'none';
      iconPause.style.display = 'block';
      
      const slider = document.getElementById('frame-slider');
      this.playbackTimer = setInterval(() => {
        this.currentFrameIdx = (this.currentFrameIdx + 1) % this.totalFrames;
        slider.value = this.currentFrameIdx;
        this.seekFrame(this.currentFrameIdx);
      }, 120);
    } else {
      iconPlay.style.display = 'block';
      iconPause.style.display = 'none';
      if (this.playbackTimer) clearInterval(this.playbackTimer);
    }
  }

  async load3DModel(jobId) {
    const glbUrl = `/outputs/${jobId}/model.glb`;
    const plyUrl = `/outputs/${jobId}/model.ply`;
    
    const gltfLoader = new THREE.GLTFLoader();
    
    return new Promise((resolve) => {
      gltfLoader.load(
        glbUrl,
        (gltf) => {
          this.modelMesh = gltf.scene;
          
          this.modelMesh.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = true;
              child.receiveShadow = true;
              
              const geom = child.geometry;
              if (geom.attributes.color) {
                this.originalColors = geom.attributes.color.clone();
              }
              if (geom.attributes.normal) {
                this.vertexNormals = geom.attributes.normal.clone();
              }
              
              child.material = new THREE.MeshStandardMaterial({
                color: geom.attributes.color ? 0xffffff : 0x94a3b8,
                vertexColors: !!geom.attributes.color,
                roughness: 0.88,
                metalness: 0.05,
                side: THREE.DoubleSide
              });
            }
          });

          this.modelRootGroup.add(this.modelMesh);
          this.centerAndFitModel(this.modelMesh);
          resolve();
        },
        undefined,
        (err) => {
          console.warn('GLB load failed, trying PLY fallback...', err);
          this.loadPLYFallback(plyUrl).then(resolve);
        }
      );
    });
  }

  async loadPLYFallback(plyUrl) {
    const plyLoader = new THREE.PLYLoader();
    return new Promise((resolve) => {
      plyLoader.load(
        plyUrl,
        (geometry) => {
          geometry.computeVertexNormals();
          if (geometry.attributes.color) {
            this.originalColors = geometry.attributes.color.clone();
          }
          if (geometry.attributes.normal) {
            this.vertexNormals = geometry.attributes.normal.clone();
          }

          const material = new THREE.MeshStandardMaterial({
            color: geometry.attributes.color ? 0xffffff : 0x94a3b8,
            vertexColors: !!geometry.attributes.color,
            roughness: 0.88,
            metalness: 0.05,
            side: THREE.DoubleSide
          });
          
          this.modelMesh = new THREE.Mesh(geometry, material);
          this.modelMesh.castShadow = true;
          this.modelMesh.receiveShadow = true;
          this.modelRootGroup.add(this.modelMesh);
          
          this.centerAndFitModel(this.modelMesh);
          resolve();
        },
        undefined,
        (err) => {
          console.error('PLY fallback load failed:', err);
          resolve();
        }
      );
    });
  }

  centerAndFitModel(object) {
    const box = new THREE.Box3().setFromObject(object);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const minZ = box.min.z;
    
    // Store offset: center XY at origin (0, 0) and place ground base (minZ) on the grid (Z = 0)
    this.modelOffset.set(center.x, center.y, minZ);
    
    // Shift mesh so ground sits cleanly on top of grid
    object.position.set(-center.x, -center.y, -minZ);

    this.currentMaxDim = Math.max(size.x, size.y, size.z, 10);
    
    this.camera.near = 0.1;
    this.camera.far = this.currentMaxDim * 30;
    this.camera.updateProjectionMatrix();

    // Initial rotation: level horizontal ground alignment
    this.modelRootGroup.rotation.set(0, 0, 0);
    this.syncRotationUI();

    // Set natural aerial drone oblique viewpoint
    this.setCameraPreset('aerial');
  }

  renderTrajectory(trajectoryData) {
    if (!trajectoryData || !trajectoryData.poses) return;
    
    this.trajectoryGroup = new THREE.Group();
    
    const poses = Array.isArray(trajectoryData.poses) 
      ? trajectoryData.poses 
      : Object.values(trajectoryData.poses);

    if (poses.length === 0) return;

    const points = [];
    poses.forEach((pose, idx) => {
      if (pose && pose.t_wc) {
        const t = pose.t_wc;
        const pos = new THREE.Vector3(
          t[0] - this.modelOffset.x,
          t[1] - this.modelOffset.y,
          t[2] - this.modelOffset.z
        );
        points.push(pos);

        const frustum = this.createCameraFrustum(pose, idx);
        this.trajectoryGroup.add(frustum);
        this.cameraFrustums.push(frustum);
      }
    });

    if (points.length >= 2) {
      const curve = new THREE.CatmullRomCurve3(points);
      const splinePoints = curve.getPoints(Math.max(50, points.length * 4));
      const splineGeom = new THREE.BufferGeometry().setFromPoints(splinePoints);
      const splineMat = new THREE.LineBasicMaterial({
        color: 0x38bdf8,
        linewidth: 3,
        transparent: true,
        opacity: 0.85
      });
      const trajectoryLine = new THREE.Line(splineGeom, splineMat);
      this.trajectoryGroup.add(trajectoryLine);
    }

    this.modelRootGroup.add(this.trajectoryGroup);
  }

  createCameraFrustum(pose, idx) {
    const group = new THREE.Group();
    const t = pose.t_wc;
    group.position.set(
      t[0] - this.modelOffset.x,
      t[1] - this.modelOffset.y,
      t[2] - this.modelOffset.z
    );
    
    if (pose.R_wc) {
      const m = new THREE.Matrix4();
      const r = pose.R_wc;
      m.set(
        r[0][0], r[0][1], r[0][2], 0,
        r[1][0], r[1][1], r[1][2], 0,
        r[2][0], r[2][1], r[2][2], 0,
        0, 0, 0, 1
      );
      group.setRotationFromMatrix(m);
    }

    const s = 0.6;
    const vertices = new Float32Array([
      0, 0, 0,   -s, -s * 0.75, s * 1.5,
      0, 0, 0,    s, -s * 0.75, s * 1.5,
      0, 0, 0,    s,  s * 0.75, s * 1.5,
      0, 0, 0,   -s,  s * 0.75, s * 1.5,
      -s, -s * 0.75, s * 1.5,   s, -s * 0.75, s * 1.5,
       s, -s * 0.75, s * 1.5,   s,  s * 0.75, s * 1.5,
       s,  s * 0.75, s * 1.5,  -s,  s * 0.75, s * 1.5,
      -s,  s * 0.75, s * 1.5,  -s, -s * 0.75, s * 1.5,
    ]);

    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    const mat = new THREE.LineBasicMaterial({ color: 0x38bdf8, opacity: 0.6, transparent: true });
    const line = new THREE.LineSegments(geom, mat);
    group.add(line);

    return group;
  }

  // --- Interaction & Direct Model Drag Controls ---

  setInteractionMode(mode) {
    this.interactionMode = mode;
    const btnOrbit = document.getElementById('btn-mode-orbit');
    const btnRotModel = document.getElementById('btn-mode-rot-model');
    const canvas = this.renderer.domElement;

    if (btnOrbit) btnOrbit.classList.toggle('active', mode === 'orbit');
    if (btnRotModel) btnRotModel.classList.toggle('active', mode === 'rotate_model');

    if (mode === 'rotate_model') {
      this.controls.enabled = false;
      canvas.style.cursor = 'grab';
      this.showToast('Mode: Left-drag to rotate ONLY the 3D model');
    } else {
      this.controls.enabled = true;
      canvas.style.cursor = 'default';
      this.showToast('Mode: Orbit camera viewpoint');
    }
  }

  setupModelDragControls() {
    const canvas = this.renderer.domElement;

    canvas.addEventListener('pointerdown', (e) => {
      if (this.interactionMode === 'rotate_model') {
        this.isDraggingModel = true;
        this.lastPointerX = e.clientX;
        this.lastPointerY = e.clientY;
        this.controls.enabled = false;
        canvas.style.cursor = 'grabbing';
        e.preventDefault();
      }
    });

    window.addEventListener('pointermove', (e) => {
      if (this.isDraggingModel && this.modelRootGroup) {
        const dx = e.clientX - this.lastPointerX;
        const dy = e.clientY - this.lastPointerY;
        this.lastPointerX = e.clientX;
        this.lastPointerY = e.clientY;

        // Directly rotate the 3D model only: horizontal drag -> Yaw (Z), vertical drag -> Pitch (X)
        this.modelRootGroup.rotation.z += dx * 0.008;
        this.modelRootGroup.rotation.x += dy * 0.008;

        this.syncRotationUI();
        e.preventDefault();
      }
    });

    window.addEventListener('pointerup', () => {
      if (this.isDraggingModel) {
        this.isDraggingModel = false;
        canvas.style.cursor = this.interactionMode === 'rotate_model' ? 'grab' : 'default';
        if (this.interactionMode === 'orbit') {
          this.controls.enabled = true;
        }
      }
    });

    // Prevent default touch/gesture page scroll when interacting with 3D canvas
    canvas.addEventListener('wheel', (e) => {
      e.stopPropagation();
    }, { passive: false });
  }

  syncRotationUI() {
    if (!this.modelRootGroup) return;
    
    // Normalize angles to (-180, 180] in degrees
    let degZ = Math.round((this.modelRootGroup.rotation.z * 180 / Math.PI) % 360);
    if (degZ > 180) degZ -= 360;
    if (degZ < -180) degZ += 360;

    let degX = Math.round((this.modelRootGroup.rotation.x * 180 / Math.PI) % 360);
    if (degX > 90) degX = 90;
    if (degX < -90) degX = -90;

    let degY = Math.round((this.modelRootGroup.rotation.y * 180 / Math.PI) % 360);
    if (degY > 90) degY = 90;
    if (degY < -90) degY = -90;

    const slZ = document.getElementById('slider-rot-z');
    const slX = document.getElementById('slider-rot-x');
    const slY = document.getElementById('slider-rot-y');
    if (slZ) slZ.value = degZ;
    if (slX) slX.value = degX;
    if (slY) slY.value = degY;

    const valZ = document.getElementById('val-rot-z');
    const valX = document.getElementById('val-rot-x');
    const valY = document.getElementById('val-rot-y');
    if (valZ) valZ.textContent = `${degZ}°`;
    if (valX) valX.textContent = `${degX}°`;
    if (valY) valY.textContent = `${degY}°`;
  }

  // --- 3D Ruler & Spatial Measurement Toolkit ---

  setupRulerControls() {
    const canvas = this.renderer.domElement;

    canvas.addEventListener('click', (e) => {
      if (!this.rulerActive || !this.modelMesh) return;

      const rect = canvas.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      this.raycaster.setFromCamera(this.mouse, this.camera);
      const intersects = this.raycaster.intersectObject(this.modelMesh, true);

      if (intersects.length > 0) {
        const hit = intersects[0];
        this.addRulerPoint(hit.point);
      }
    });
  }

  toggleRuler() {
    this.rulerActive = !this.rulerActive;
    const btn = document.getElementById('btn-tool-ruler');
    const card = document.getElementById('spatial-card');
    const canvas = this.renderer.domElement;

    if (btn) btn.classList.toggle('active', this.rulerActive);

    if (this.rulerActive) {
      if (card) card.style.display = 'flex';
      canvas.style.cursor = 'crosshair';
      this.showToast('3D Ruler Active: Click 2 points on the model to measure distance & height');
    } else {
      canvas.style.cursor = this.interactionMode === 'rotate_model' ? 'grab' : 'default';
      this.showToast('3D Ruler Disabled');
    }
  }

  toggleSpatialAnalytics() {
    const card = document.getElementById('spatial-card');
    const btn = document.getElementById('btn-tool-analytics');
    if (!card) return;

    const isVisible = card.style.display !== 'none';
    card.style.display = isVisible ? 'none' : 'flex';
    if (btn) btn.classList.toggle('active', !isVisible);

    if (!isVisible) {
      this.loadSpatialMeasurements();
    }
  }

  addRulerPoint(worldPoint) {
    if (this.rulerPoints.length >= 2) {
      this.clearRulerMeasurements();
    }

    this.rulerPoints.push(worldPoint.clone());

    // Add marker sphere
    const markerGeo = new THREE.SphereGeometry(0.35, 16, 16);
    const markerMat = new THREE.MeshBasicMaterial({ color: this.rulerPoints.length === 1 ? 0xef4444 : 0x10b981 });
    const marker = new THREE.Mesh(markerGeo, markerMat);
    marker.position.copy(worldPoint);
    this.scene.add(marker);
    this.rulerMarkers.push(marker);

    const inst = document.getElementById('measure-instruction');
    const results = document.getElementById('measure-results');

    if (this.rulerPoints.length === 1) {
      if (inst) inst.textContent = 'Point 1 set. Click Point 2 on the model.';
      if (results) results.style.display = 'none';
    } else if (this.rulerPoints.length === 2) {
      const p1 = this.rulerPoints[0];
      const p2 = this.rulerPoints[1];

      // Draw dimension line
      const lineGeo = new THREE.BufferGeometry().setFromPoints([p1, p2]);
      const lineMat = new THREE.LineBasicMaterial({ color: 0x38bdf8, linewidth: 3 });
      this.rulerLine = new THREE.Line(lineGeo, lineMat);
      this.scene.add(this.rulerLine);

      // Metric calculations in real meters
      const dist3d = p1.distanceTo(p2);
      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const distXY = Math.sqrt(dx * dx + dy * dy);
      const distZ = Math.abs(p2.z - p1.z);

      if (inst) inst.textContent = 'Measurement computed between Point 1 & 2:';
      if (results) results.style.display = 'block';

      const el3d = document.getElementById('val-dist-3d');
      const elXY = document.getElementById('val-dist-xy');
      const elZ = document.getElementById('val-dist-z');

      if (el3d) el3d.textContent = `${dist3d.toFixed(2)} m`;
      if (elXY) elXY.textContent = `${distXY.toFixed(2)} m`;
      if (elZ) elZ.textContent = `${distZ.toFixed(2)} m`;

      this.showToast(`Measured 3D Distance: ${dist3d.toFixed(2)} m | Height: ${distZ.toFixed(2)} m`);
    }
  }

  clearRulerMeasurements() {
    this.rulerPoints = [];
    this.rulerMarkers.forEach(m => this.scene.remove(m));
    this.rulerMarkers = [];
    if (this.rulerLine) {
      this.scene.remove(this.rulerLine);
      this.rulerLine = null;
    }

    const inst = document.getElementById('measure-instruction');
    const results = document.getElementById('measure-results');
    if (inst) inst.textContent = 'Click 2 points on the 3D model to measure distance & height.';
    if (results) results.style.display = 'none';
  }

  async loadSpatialMeasurements() {
    try {
      const res = await fetch(`/outputs/${this.currentJob}/measurements.json`);
      if (!res.ok) return;
      const data = await res.json();
      this.measurementsData = data;

      const elFootprint = document.getElementById('val-footprint-area');
      const elVolume = document.getElementById('val-built-volume');
      const elGsd = document.getElementById('val-gsd');
      const elElev = document.getElementById('val-elev-span');

      if (elFootprint && data.projected_footprint_area_m2) {
        elFootprint.textContent = `${data.projected_footprint_area_m2} m²`;
      }
      if (elVolume && data.estimated_above_ground_volume_m3) {
        elVolume.textContent = `${data.estimated_above_ground_volume_m3} m³`;
      }
      if (elGsd && data.ground_sample_distance_m) {
        elGsd.textContent = `${(data.ground_sample_distance_m * 100).toFixed(1)} cm/px`;
      }
      if (elElev && data.elevation_range_m?.span) {
        elElev.textContent = `${data.elevation_range_m.span} m`;
      }
    } catch (e) {
      console.log('No measurements.json for job:', e);
    }
  }

  // --- Orientation & View Controls ---

  rotateModel(axis, angleRad) {
    if (!this.modelRootGroup) return;
    if (axis === 'x') this.modelRootGroup.rotation.x += angleRad;
    if (axis === 'y') this.modelRootGroup.rotation.y += angleRad;
    if (axis === 'z') this.modelRootGroup.rotation.z += angleRad;
    this.syncRotationUI();
    this.showToast(`Rotated ${axis.toUpperCase()} ${Math.round(angleRad * 180 / Math.PI)}°`);
  }

  setCameraPreset(preset) {
    const d = this.currentMaxDim;
    if (preset === 'aerial') {
      this.camera.position.set(0, -d * 1.3, d * 0.9);
      this.camera.lookAt(0, 0, d * 0.2);
      this.controls.target.set(0, 0, d * 0.2);
    } else if (preset === 'top') {
      this.camera.position.set(0, 0, d * 1.8);
      this.camera.lookAt(0, 0, 0);
      this.controls.target.set(0, 0, 0);
    } else if (preset === 'front') {
      this.camera.position.set(0, -d * 1.8, d * 0.3);
      this.camera.lookAt(0, 0, d * 0.2);
      this.controls.target.set(0, 0, d * 0.2);
    } else if (preset === 'side') {
      this.camera.position.set(d * 1.8, 0, d * 0.3);
      this.camera.lookAt(0, 0, d * 0.2);
      this.controls.target.set(0, 0, d * 0.2);
    } else if (preset === 'isometric') {
      this.camera.position.set(d * 1.1, -d * 1.1, d * 1.1);
      this.camera.lookAt(0, 0, d * 0.2);
      this.controls.target.set(0, 0, d * 0.2);
    }
    this.controls.update();
  }

  resetOrientation() {
    if (this.modelRootGroup) {
      this.modelRootGroup.rotation.set(0, 0, 0);
    }
    this.syncRotationUI();
    document.getElementById('view-preset-selector').value = 'aerial';
    this.setCameraPreset('aerial');
    this.showToast('Reset orientation & viewpoint');
  }

  applyShadingMode(mode) {
    this.shadingMode = mode;
    
    document.querySelectorAll('.btn-header[data-mode]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    if (!this.modelMesh) return;

    this.modelMesh.traverse((child) => {
      if (!child.isMesh) return;
      
      const geom = child.geometry;
      const count = geom.attributes.position.count;
      let newColors = new Float32Array(count * 3);

      if (mode === 'rgb') {
        if (this.originalColors) {
          newColors = this.originalColors.array.slice();
        } else {
          for (let i = 0; i < count; i++) {
            newColors[i * 3] = 0.58; newColors[i * 3 + 1] = 0.64; newColors[i * 3 + 2] = 0.72;
          }
        }
      } else if (mode === 'semantics') {
        const pos = geom.attributes.position.array;
        const norm = geom.attributes.normal?.array;
        for (let i = 0; i < count; i++) {
          const z = pos[i * 3 + 2];
          const nz = norm ? norm[i * 3 + 2] : 0.8;
          
          if (nz > 0.85 && z < 2.0) {
            newColors[i * 3] = 0.96; newColors[i * 3 + 1] = 0.62; newColors[i * 3 + 2] = 0.04; // Ground
          } else if (nz > 0.7) {
            newColors[i * 3] = 0.96; newColors[i * 3 + 1] = 0.25; newColors[i * 3 + 2] = 0.37; // Roof
          } else if (Math.abs(nz) < 0.4) {
            newColors[i * 3] = 0.22; newColors[i * 3 + 1] = 0.74; newColors[i * 3 + 2] = 0.97; // Facade
          } else {
            newColors[i * 3] = 0.06; newColors[i * 3 + 1] = 0.73; newColors[i * 3 + 2] = 0.51; // Vegetation
          }
        }
      } else if (mode === 'confidence') {
        for (let i = 0; i < count; i++) {
          const conf = 0.6 + 0.4 * Math.sin(i * 0.1);
          if (conf > 0.8) {
            newColors[i * 3] = 0.06; newColors[i * 3 + 1] = 0.73; newColors[i * 3 + 2] = 0.51;
          } else if (conf > 0.5) {
            newColors[i * 3] = 0.96; newColors[i * 3 + 1] = 0.62; newColors[i * 3 + 2] = 0.04;
          } else {
            newColors[i * 3] = 0.96; newColors[i * 3 + 1] = 0.25; newColors[i * 3 + 2] = 0.37;
          }
        }
      } else if (mode === 'normals') {
        if (this.vertexNormals) {
          const nArr = this.vertexNormals.array;
          for (let i = 0; i < count; i++) {
            newColors[i * 3] = nArr[i * 3] * 0.5 + 0.5;
            newColors[i * 3 + 1] = nArr[i * 3 + 1] * 0.5 + 0.5;
            newColors[i * 3 + 2] = nArr[i * 3 + 2] * 0.5 + 0.5;
          }
        }
      }

      geom.setAttribute('color', new THREE.BufferAttribute(newColors, 3));
      geom.attributes.color.needsUpdate = true;
      child.material.vertexColors = true;
      child.material.needsUpdate = true;
    });
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
    }, 2200);
  }

  setupEventListeners() {
    // Job Selector
    document.getElementById('job-selector').addEventListener('change', (e) => {
      this.loadJobData(e.target.value);
    });

    // Shading Mode Buttons
    document.querySelectorAll('.btn-header[data-mode]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.applyShadingMode(btn.dataset.mode);
      });
    });

    // Wireframe Toggle
    document.getElementById('btn-toggle-wireframe').addEventListener('click', (e) => {
      this.showWireframe = !this.showWireframe;
      if (this.modelMesh) {
        this.modelMesh.traverse(child => {
          if (child.isMesh) child.material.wireframe = this.showWireframe;
        });
      }
      e.currentTarget.classList.toggle('active', this.showWireframe);
    });

    // Point Cloud Toggle
    document.getElementById('btn-toggle-pointcloud').addEventListener('click', (e) => {
      this.showPointCloud = !this.showPointCloud;
      if (this.pointCloud) {
        this.pointCloud.visible = this.showPointCloud;
      } else if (this.showPointCloud) {
        // Load splats.ply as point cloud
        const plyLoader = new THREE.PLYLoader();
        plyLoader.load(`/outputs/${this.currentJob}/splats.ply`, (geom) => {
          const mat = new THREE.PointsMaterial({
            size: 0.08,
            sizeAttenuation: true,
            vertexColors: !!geom.attributes.color
          });
          this.pointCloud = new THREE.Points(geom, mat);
          this.pointCloud.position.set(-this.modelOffset.x, -this.modelOffset.y, -this.modelOffset.z);
          this.modelRootGroup.add(this.pointCloud);
        });
      }
      if (this.modelMesh) {
        this.modelMesh.visible = !this.showPointCloud;
      }
      e.currentTarget.classList.toggle('active', this.showPointCloud);
    });

    // Interaction Mode Toggles (Orbit View vs Rotate Model Only)
    const btnModeOrbit = document.getElementById('btn-mode-orbit');
    if (btnModeOrbit) {
      btnModeOrbit.addEventListener('click', () => {
        this.setInteractionMode('orbit');
      });
    }

    const btnModeRotModel = document.getElementById('btn-mode-rot-model');
    if (btnModeRotModel) {
      btnModeRotModel.addEventListener('click', () => {
        this.setInteractionMode('rotate_model');
      });
    }

    // Model Orientation Card Sliders
    const slZ = document.getElementById('slider-rot-z');
    if (slZ) {
      slZ.addEventListener('input', (e) => {
        if (!this.modelRootGroup) return;
        this.modelRootGroup.rotation.z = (parseFloat(e.target.value) * Math.PI) / 180;
        this.syncRotationUI();
      });
    }

    const slX = document.getElementById('slider-rot-x');
    if (slX) {
      slX.addEventListener('input', (e) => {
        if (!this.modelRootGroup) return;
        this.modelRootGroup.rotation.x = (parseFloat(e.target.value) * Math.PI) / 180;
        this.syncRotationUI();
      });
    }

    const slY = document.getElementById('slider-rot-y');
    if (slY) {
      slY.addEventListener('input', (e) => {
        if (!this.modelRootGroup) return;
        this.modelRootGroup.rotation.y = (parseFloat(e.target.value) * Math.PI) / 180;
        this.syncRotationUI();
      });
    }

    // Quick Micro Rotation Degree Buttons
    document.querySelectorAll('.btn-micro[data-rot-z]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (!this.modelRootGroup) return;
        const deg = parseFloat(btn.dataset.rotZ);
        this.modelRootGroup.rotation.z += (deg * Math.PI) / 180;
        this.syncRotationUI();
      });
    });

    const btnQuickResetRot = document.getElementById('btn-quick-reset-rot');
    if (btnQuickResetRot) {
      btnQuickResetRot.addEventListener('click', () => {
        if (!this.modelRootGroup) return;
        this.modelRootGroup.rotation.set(0, 0, 0);
        this.syncRotationUI();
        this.showToast('Reset model rotation to 0°');
      });
    }

    // Camera View Presets
    document.getElementById('view-preset-selector').addEventListener('change', (e) => {
      this.setCameraPreset(e.target.value);
    });

    // Grid Toggle
    document.getElementById('btn-toggle-grid').addEventListener('click', (e) => {
      if (this.gridHelper) {
        this.gridHelper.visible = !this.gridHelper.visible;
        e.currentTarget.classList.toggle('active', this.gridHelper.visible);
      }
    });

    // Trajectory Toggle
    document.getElementById('btn-toggle-trajectory').addEventListener('click', (e) => {
      this.showTrajectory = !this.showTrajectory;
      if (this.trajectoryGroup) this.trajectoryGroup.visible = this.showTrajectory;
      e.currentTarget.classList.toggle('active', this.showTrajectory);
    });

    // 3D Ruler Tool
    const btnToolRuler = document.getElementById('btn-tool-ruler');
    if (btnToolRuler) {
      btnToolRuler.addEventListener('click', () => {
        this.toggleRuler();
      });
    }

    // Spatial Analytics Card
    const btnToolAnalytics = document.getElementById('btn-tool-analytics');
    if (btnToolAnalytics) {
      btnToolAnalytics.addEventListener('click', () => {
        this.toggleSpatialAnalytics();
      });
    }

    // Close Spatial Card
    const btnCloseSpatial = document.getElementById('btn-close-spatial');
    if (btnCloseSpatial) {
      btnCloseSpatial.addEventListener('click', () => {
        const card = document.getElementById('spatial-card');
        if (card) card.style.display = 'none';
        if (this.rulerActive) this.toggleRuler();
      });
    }

    // Clear Measurement
    const btnClearRuler = document.getElementById('btn-clear-ruler');
    if (btnClearRuler) {
      btnClearRuler.addEventListener('click', () => {
        this.clearRulerMeasurements();
      });
    }

    // Reset View & Orientation
    document.getElementById('btn-reset-cam').addEventListener('click', () => {
      this.resetOrientation();
    });

    // Play/Pause Flight
    document.getElementById('btn-play-pause').addEventListener('click', () => {
      this.togglePlay();
    });

    // Scrubber Slider
    document.getElementById('frame-slider').addEventListener('input', (e) => {
      this.seekFrame(parseInt(e.target.value, 10));
    });
  }
}

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', () => {
  window.app = new SinglePass3DViewer();
});
