/*
 * Catalyst 3D presence runtime.
 *
 * The runtime is intentionally renderer-only: Catalyst cognition owns state;
 * this module turns that state into body motion, gaze, expression, clothing,
 * and speech activity. The actual Catalyst.vrm is a segmented weighted-skin humanoid alpha rig
 * (body parts are parented to humanoid bones) with VRMC_springBone hair joints.
 *
 * The browser loads Three/three-vrm from a CDN so the main repo stays small.
 * A timed fallback keeps the rest of Catalyst usable when the CDN is blocked.
 */
const MODULE_SOURCES = [
  {
    three: 'https://esm.sh/three@0.180.0',
    vrm: 'https://esm.sh/@pixiv/three-vrm@3.4.2?bundle',
    gltf: 'https://esm.sh/three@0.180.0/examples/jsm/loaders/GLTFLoader.js',
  },
  {
    three: 'https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js',
    vrm: 'https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.4.2/lib/three-vrm.module.js',
    gltf: 'https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/loaders/GLTFLoader.js',
  },
];

let THREE = null;
let VRM = null;
let GLTFLoaderClass = null;
let scene = null;
let camera = null;
let renderer = null;
let currentVrm = null;
let currentContainer = null;
let canvas = null;
let libsLoading = null;
let modelLoading = null;
let initialized = false;
let last = performance.now();
let blinkClock = 0;
let blinkActive = false;
let audioEnergy = 0;
let currentLoadedUrl = '';
let rigHeight = 1.7;
let baseRotations = new Map();
let motionEnabled = true;

const $ = (id) => document.getElementById(id);

const state = {
  state: 'idle',
  emotion: 'neutral',
  speechLevel: 0,
  targetLook: { x: 0, y: 0 },
  appearance: 'signature',
  expression: 'neutral',
  gesture: 'none',
  motion: 'full',
};

const refs = new Map();
const EXPRESSION_PROFILES = {
  neutral: {},
  happy: { Mouth: [1.06, 1.36, 1], MouthInner: [0.98, 1.22, 1], browY: 0.012 },
  curious: { browY: 0.02, browX: 0.004, eyeY: 1.035 },
  thinking: { browY: -0.006, mouthY: 0.99 },
  serious: { browY: -0.012, eyeY: 0.99, mouthY: 0.99 },
  surprised: { Mouth: [1.12, 2.15, 1], MouthInner: [1.06, 1.95, 1], eyeY: 1.08 },
  concerned: { browY: -0.010, mouthY: 0.95 },
  playful: { Mouth: [1.08, 1.20, 1], browY: 0.014, eyeY: 1.015 },
  sad: { Mouth: [1.0, 1.10, 1], mouthY: -0.015, browY: -0.016 },
};

const APPEARANCE_PALETTE = {
  signature: { key: 0xfff0e9, rim: 0x8a78ff },
  lounge: { key: 0xffe9f2, rim: 0x7f99d9 },
  focus: { key: 0xffffff, rim: 0x8b76ff },
  night: { key: 0xe7ddff, rim: 0x6c56d8 },
};

function setRuntimeBadge(text) {
  const el = $('avatarRuntimeBadge');
  if (el) el.textContent = text;
}

function setFallbackOpacity(opacity) {
  const imgs = [$('catalystAvatar'), $('liveFallbackAvatar')].filter(Boolean);
  imgs.forEach((img) => {
    img.style.display = 'block';
    img.style.opacity = String(opacity);
  });
  if (canvas) {
    canvas.style.display = 'block';
    canvas.style.opacity = currentVrm ? '1' : '0';
  }
}

function timedImport(url, ms = 12000) {
  return Promise.race([
    import(/* @vite-ignore */ url),
    new Promise((_, reject) => setTimeout(() => reject(new Error(`Timed out loading ${url}`)), ms)),
  ]);
}

async function loadLibraries() {
  if (THREE && VRM && GLTFLoaderClass) return;
  if (libsLoading) return libsLoading;
  libsLoading = (async () => {
    let lastError = null;
    for (const source of MODULE_SOURCES) {
      try {
        const [three, vrm, gltf] = await Promise.all([
          timedImport(source.three),
          timedImport(source.vrm),
          timedImport(source.gltf),
        ]);
        THREE = three;
        VRM = vrm;
        GLTFLoaderClass = gltf.GLTFLoader || gltf.default;
        if (!THREE || !VRM || !GLTFLoaderClass) throw new Error('3D modules did not expose the expected APIs.');
        return;
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error('Unable to load 3D runtime modules.');
  })();
  try {
    await libsLoading;
  } finally {
    if (!THREE || !VRM || !GLTFLoaderClass) libsLoading = null;
  }
}

function createScene(containerId = 'avatarWrap') {
  if (canvas && renderer) {
    mountAvatar(containerId);
    return;
  }
  const container = $(containerId);
  if (!container) throw new Error(`Avatar container #${containerId} not found`);
  currentContainer = container;
  canvas = document.createElement('canvas');
  canvas.className = 'catalyst-vrm-canvas';
  canvas.setAttribute('aria-label', 'Catalyst live 3D avatar');
  canvas.tabIndex = -1;
  container.prepend(canvas);

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(29, 1, 0.01, 100);
  camera.position.set(0, 1.0, 3.0);

  renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'high-performance',
    preserveDrawingBuffer: false,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;

  const hemi = new THREE.HemisphereLight(0xffffff, 0x15141a, 1.65);
  hemi.name = 'CatalystAmbient';
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xfff0e9, 2.15);
  key.name = 'CatalystKey';
  key.position.set(2.2, 3.5, 4.4);
  key.castShadow = true;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xb6a2ff, 0.75);
  fill.name = 'CatalystFill';
  fill.position.set(-2.5, 1.8, 2.0);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0x8672ff, 1.25);
  rim.name = 'CatalystRim';
  rim.position.set(-2.7, 2.8, -1.8);
  scene.add(rim);

  resize();
  window.addEventListener('resize', resize, { passive: true });
  canvas.addEventListener('pointermove', onPointerMove, { passive: true });
  canvas.addEventListener('pointerleave', () => {
    state.targetLook.x = 0;
    state.targetLook.y = 0;
  }, { passive: true });
}

function onPointerMove(e) {
  if (!canvas) return;
  const r = canvas.getBoundingClientRect();
  state.targetLook.x = ((e.clientX - r.left) / Math.max(1, r.width) - 0.5) * 0.65;
  state.targetLook.y = ((e.clientY - r.top) / Math.max(1, r.height) - 0.5) * -0.38;
}

function resize() {
  if (!renderer || !camera || !canvas) return;
  const host = currentContainer || $('avatarWrap');
  const w = Math.max(1, host?.clientWidth || 500);
  const h = Math.max(1, host?.clientHeight || 650);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

export function mountAvatar(containerId = 'avatarWrap') {
  const next = $(containerId);
  if (!next || !canvas) return false;
  if (canvas.parentElement !== next) next.prepend(canvas);
  currentContainer = next;
  resize();
  return true;
}

function cacheReferences() {
  refs.clear();
  const names = [
    'Head','Neck','Chest','Spine','Hips','LeftShoulder','RightShoulder',
    'LeftEyeWhite','RightEyeWhite','LeftIris','RightIris','LeftPupil','RightPupil',
    'LeftBrow','RightBrow','Mouth','MouthInner','HairCap','LeftUpperArm','RightUpperArm',
    'LeftLowerArm','RightLowerArm','LeftHand','RightHand',
  ];
  names.forEach((name) => {
    const obj = currentVrm?.scene?.getObjectByName(name);
    if (obj) refs.set(name, obj);
  });
  baseRotations = new Map();
  refs.forEach((obj, name) => {
    if (['Head','Neck','Chest','Spine','Hips','LeftUpperArm','RightUpperArm','LeftLowerArm','RightLowerArm','LeftShoulder','RightShoulder'].includes(name)) {
      baseRotations.set(name, { x: obj.rotation.x, y: obj.rotation.y, z: obj.rotation.z });
    }
  });
}

function resetObjectTransform(name) {
  const obj = refs.get(name);
  if (!obj) return;
  const base = baseRotations.get(name);
  if (base) obj.rotation.set(base.x, base.y, base.z);
}

function setObjectScale(name, sx, sy, sz) {
  const obj = refs.get(name);
  if (!obj) return;
  obj.scale.set(sx, sy, sz);
}

function setObjectPosition(name, x, y, z) {
  const obj = refs.get(name);
  if (!obj) return;
  obj.position.set(x, y, z);
}

function setExpressionManagerValue(name, value = 0) {
  const manager = currentVrm?.expressionManager;
  if (!manager) return false;
  try {
    manager.setValue(name, Math.max(0, Math.min(1, Number(value) || 0)));
    return true;
  } catch (_) {
    return false;
  }
}

function resetExpressions() {
  const manager = currentVrm?.expressionManager;
  if (manager?.expressionMap) {
    for (const name of Object.keys(manager.expressionMap)) {
      try { manager.setValue(name, 0); } catch (_) {}
    }
  }
  manager?.update?.();
}

function resetFaceTransforms() {
  setObjectScale('LeftEyeWhite', 1, 1, 1);
  setObjectScale('RightEyeWhite', 1, 1, 1);
  setObjectScale('LeftIris', 1, 1, 1);
  setObjectScale('RightIris', 1, 1, 1);
  setObjectScale('LeftPupil', 1, 1, 1);
  setObjectScale('RightPupil', 1, 1, 1);
  setObjectScale('Mouth', 1, 1, 1);
  setObjectScale('MouthInner', 1, 1, 1);
  setObjectPosition('Mouth', 0, -0.062, -0.148);
  setObjectPosition('MouthInner', 0, -0.064, -0.155);
  setObjectPosition('LeftBrow', -0.06, 0.095, -0.145);
  setObjectPosition('RightBrow', 0.06, 0.095, -0.145);
}

function applyExpressionPreset(name = 'neutral') {
  state.expression = name;
  resetExpressions();
  resetFaceTransforms();
  const profile = EXPRESSION_PROFILES[name] || EXPRESSION_PROFILES.neutral;
  const happy = name === 'happy' || name === 'playful';
  setExpressionManagerValue('happy', happy ? (name === 'playful' ? 0.62 : 0.82) : 0);
  setExpressionManagerValue('sad', name === 'sad' ? 0.72 : 0);
  setExpressionManagerValue('surprised', name === 'surprised' ? 0.82 : 0);
  setExpressionManagerValue('angry', name === 'serious' ? 0.18 : 0);
  setExpressionManagerValue('relaxed', name === 'warm' ? 0.45 : 0);
  setExpressionManagerValue('aa', 0);
  setExpressionManagerValue('ih', 0);
  setExpressionManagerValue('oh', 0);

  if (profile.Mouth) setObjectScale('Mouth', ...profile.Mouth);
  if (profile.MouthInner) setObjectScale('MouthInner', ...profile.MouthInner);
  if (profile.eyeY) {
    setObjectScale('LeftEyeWhite', 1, profile.eyeY, 1);
    setObjectScale('RightEyeWhite', 1, profile.eyeY, 1);
  }
  const browY = 0.095 + (profile.browY || 0);
  const browX = profile.browX || 0;
  setObjectPosition('LeftBrow', -0.06 + browX, browY, -0.145);
  setObjectPosition('RightBrow', 0.06 - browX, browY, -0.145);
  if (profile.mouthY) setObjectPosition('Mouth', 0, -0.062 + profile.mouthY, -0.148);
  state.emotion = name;
}

function applyEmotion(emotion) {
  const accepted = Object.prototype.hasOwnProperty.call(EXPRESSION_PROFILES, emotion) ? emotion : 'neutral';
  applyExpressionPreset(accepted);
}

function applySpeech(level) {
  state.speechLevel = Math.max(0, Math.min(1, Number(level) || 0));
  setExpressionManagerValue('aa', state.speechLevel * 0.82);
  setExpressionManagerValue('ih', state.speechLevel * 0.25);
  setExpressionManagerValue('oh', state.speechLevel * 0.18);
  const mouth = 1 + state.speechLevel * 0.85;
  setObjectScale('Mouth', 1, mouth, 1);
  setObjectScale('MouthInner', 1, 1 + state.speechLevel * 0.95, 1);
  currentVrm?.expressionManager?.update?.();
}

function applyStageLighting(appearance) {
  const pal = APPEARANCE_PALETTE[appearance] || APPEARANCE_PALETTE.signature;
  scene?.getObjectByName('CatalystKey')?.color?.setHex(pal.key);
  scene?.getObjectByName('CatalystRim')?.color?.setHex(pal.rim);
}

function setWardrobe(appearance) {
  if (!currentVrm) return;
  const selected = String(appearance || 'signature').toLowerCase();
  currentVrm.scene.traverse((obj) => {
    if (!obj?.name?.startsWith('Outfit_')) return;
    const outfit = obj.name.split('_')[1]?.toLowerCase();
    obj.visible = outfit === selected;
  });
  lastAppearance = selected;
  applyStageLighting(selected);
}

let lastAppearance = 'signature';

export function setCatalystAppearance(appearance = 'signature') {
  const allowed = new Set(['signature', 'lounge', 'focus', 'night']);
  const selected = String(appearance || 'signature').toLowerCase();
  if (!allowed.has(selected)) return false;
  state.appearance = selected;
  lastAppearance = selected;
  if (!currentVrm) return false;
  setWardrobe(selected);
  return true;
}

export function setCatalystExpression(expression = 'neutral') {
  const selected = Object.prototype.hasOwnProperty.call(EXPRESSION_PROFILES, expression) ? expression : 'neutral';
  state.expression = selected;
  if (currentVrm) applyExpressionPreset(selected);
  return selected;
}

export function setCatalystGesture(gesture = 'none') {
  state.gesture = String(gesture || 'none').toLowerCase();
  return state.gesture;
}

export function setCatalystMotionMode(mode = 'full') {
  state.motion = mode === 'reduced' ? 'reduced' : 'full';
  motionEnabled = state.motion !== 'reduced';
  document.documentElement.dataset.motion = state.motion;
  return state.motion;
}

export function setCatalystSpeechLevel(level = 0) {
  audioEnergy = Math.max(0, Math.min(1, Number(level) || 0));
  if (currentVrm) applySpeech(audioEnergy);
}

export function setCatalystAvatarState(next = {}) {
  state.state = String(next.state || state.state || 'idle').toLowerCase();
  state.emotion = String(next.emotion || state.emotion || 'neutral').toLowerCase();
  state.gesture = String(next.gesture || state.gesture || 'none').toLowerCase();
  state.appearance = String(next.appearance || state.appearance || 'signature').toLowerCase();
  if (next.motion) setCatalystMotionMode(next.motion);
  applyEmotion(state.emotion);
  applySpeech(next.speech_level ?? state.speechLevel ?? 0);
  const wrap = $('avatarWrap');
  if (wrap) wrap.dataset.state = state.state;
  return { ...state };
}

function autoFrameModel() {
  if (!currentVrm || !camera || !THREE) return;
  const box = new THREE.Box3().setFromObject(currentVrm.scene);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  rigHeight = Math.max(1, size.y || 1.7);
  const distance = Math.max(1.7, rigHeight * 1.78);
  camera.position.set(center.x, center.y + rigHeight * 0.045, distance);
  camera.near = Math.max(0.01, rigHeight / 200);
  camera.far = Math.max(50, rigHeight * 20);
  camera.lookAt(center.x, center.y + rigHeight * 0.055, 0);
  camera.updateProjectionMatrix();
}

function applyMotion(now, dt) {
  if (!motionEnabled || state.motion === 'reduced') return;
  const t = now * 0.001;
  const breathing = Math.sin(t * 1.45) * 0.007;
  const talking = state.state === 'speaking' ? Math.sin(t * 6.5) * 0.018 : 0;
  const thinking = state.state === 'thinking' ? Math.sin(t * 1.3) * 0.025 : 0;
  const gesture = state.gesture;
  const amp = gesture === 'celebrate' ? 0.16 : gesture === 'gesture' ? 0.085 : state.state === 'speaking' ? 0.035 : 0.0;

  const applyBone = (name, dx = 0, dy = 0, dz = 0, smoothing = 8) => {
    const obj = refs.get(name);
    const base = baseRotations.get(name);
    if (!obj || !base) return;
    const target = { x: base.x + dx, y: base.y + dy, z: base.z + dz };
    const a = Math.min(1, dt * smoothing);
    obj.rotation.x += (target.x - obj.rotation.x) * a;
    obj.rotation.y += (target.y - obj.rotation.y) * a;
    obj.rotation.z += (target.z - obj.rotation.z) * a;
  };

  applyBone('Chest', thinking * 0.55 + breathing, 0, talking * 0.4, 5);
  applyBone('Spine', breathing * 0.7, 0, 0, 5);
  applyBone('Head', state.targetLook.y * 0.09 + thinking * 0.2, state.targetLook.x * 0.16, 0, 4.5);
  applyBone('Neck', state.targetLook.y * 0.035, state.targetLook.x * 0.07, 0, 5.5);
  applyBone('LeftShoulder', 0, 0, -amp * 0.15, 6);
  applyBone('RightShoulder', 0, 0, amp * 0.15, 6);
  applyBone('LeftUpperArm', 0, 0, amp * 0.80 + talking * 0.3, 6);
  applyBone('RightUpperArm', 0, 0, -amp * 0.80 - talking * 0.3, 6);
  applyBone('LeftLowerArm', amp * 0.12, 0, 0, 6);
  applyBone('RightLowerArm', -amp * 0.12, 0, 0, 6);

  // Add a very small idle body drift so the model never feels frozen.
  const hips = refs.get('Hips');
  const hipsBase = baseRotations.get('Hips');
  if (hips && hipsBase) {
    hips.rotation.z += ((Math.sin(t * 0.75) * 0.007 + hipsBase.z) - hips.rotation.z) * Math.min(1, dt * 4);
  }
}

function animateBlink(dt) {
  if (!currentVrm) return;
  blinkClock += dt;
  if (!blinkActive && blinkClock > 3.0 + Math.random() * 2.9) {
    blinkActive = true;
    blinkClock = 0;
  }
  if (!blinkActive) return;
  const t = blinkClock;
  const amount = t < 0.10 ? t / 0.10 : t < 0.20 ? 1 - (t - 0.10) / 0.10 : 0;
  if (t < 0.23) {
    setExpressionManagerValue('blink', amount);
    const scaleY = 1 - amount * 0.93;
    setObjectScale('LeftEyeWhite', 1, scaleY, 1);
    setObjectScale('RightEyeWhite', 1, scaleY, 1);
    setObjectScale('LeftIris', 1, 1 - amount * 0.90, 1);
    setObjectScale('RightIris', 1, 1 - amount * 0.90, 1);
    setObjectScale('LeftPupil', 1, 1 - amount * 0.88, 1);
    setObjectScale('RightPupil', 1, 1 - amount * 0.88, 1);
  } else {
    blinkActive = false;
    setExpressionManagerValue('blink', 0);
  }
}

async function loadModel(url = '/assets/catalyst/catalyst.vrm') {
  if (currentVrm && currentLoadedUrl === url) return true;
  if (modelLoading) return modelLoading;
  modelLoading = (async () => {
    try {
      await loadLibraries();
      createScene(currentContainer?.id || 'avatarWrap');
      const gltfLoader = new GLTFLoaderClass();
      gltfLoader.crossOrigin = 'anonymous';
      gltfLoader.register((parser) => new VRM.VRMLoaderPlugin(parser));
      const gltf = await gltfLoader.loadAsync(url);
      currentVrm = gltf.userData.vrm;
      if (!currentVrm) throw new Error('Loaded file is not a VRM model');
      currentLoadedUrl = url;
      currentVrm.scene.rotation.y = Math.PI;
      currentVrm.scene.traverse((obj) => {
        obj.frustumCulled = false;
        if (obj.isMesh) {
          obj.castShadow = true;
          obj.receiveShadow = true;
        }
      });
      if (VRM.VRMUtils) {
        try { VRM.VRMUtils.removeUnnecessaryVertices(gltf.scene); } catch (_) {}
        try { VRM.VRMUtils.combineMorphs?.(currentVrm); } catch (_) {}
      }
      scene.add(currentVrm.scene);
      cacheReferences();
      setFallbackOpacity(0.04);
      setRuntimeBadge('VRM 1.0 · LIVE');
      setWardrobe(state.appearance || lastAppearance);
      applyExpressionPreset(state.expression || state.emotion || 'neutral');
      autoFrameModel();
      resize();
      window.dispatchEvent(new CustomEvent('catalyst:avatar-ready', { detail: { live: true, rigHeight } }));
      return true;
    } catch (error) {
      console.warn('[Catalyst VRM] model unavailable:', error?.message || error);
      currentVrm = null;
      setRuntimeBadge('REFERENCE MODE · 3D RUNTIME UNAVAILABLE');
      setFallbackOpacity(1);
      window.dispatchEvent(new CustomEvent('catalyst:avatar-ready', { detail: { live: false, error: String(error?.message || error) } }));
      return false;
    } finally {
      modelLoading = null;
    }
  })();
  return modelLoading;
}

function animate(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  if (currentVrm && renderer && scene && camera) {
    const head = currentVrm.humanoid?.getNormalizedBoneNode?.('head');
    const leftEye = currentVrm.humanoid?.getNormalizedBoneNode?.('leftEye');
    const rightEye = currentVrm.humanoid?.getNormalizedBoneNode?.('rightEye');
    if (head && state.motion !== 'reduced') {
      const targetY = state.targetLook.x * 0.12;
      const targetX = state.targetLook.y * 0.07;
      head.rotation.y += (targetY - head.rotation.y) * Math.min(1, dt * 3.5);
      head.rotation.x += (targetX - head.rotation.x) * Math.min(1, dt * 3.5);
    }
    if (leftEye && rightEye && state.motion !== 'reduced') {
      leftEye.rotation.y += (state.targetLook.x * 0.25 - leftEye.rotation.y) * Math.min(1, dt * 7);
      rightEye.rotation.y += (state.targetLook.x * 0.25 - rightEye.rotation.y) * Math.min(1, dt * 7);
    }
    applyMotion(now, dt);
    animateBlink(dt);
    if (state.state === 'speaking') applySpeech(Math.max(audioEnergy, state.speechLevel));
    currentVrm.update(dt);
    renderer.render(scene, camera);
  }
  requestAnimationFrame(animate);
}

export async function initCatalystVRM(options = {}) {
  if (!initialized) {
    initialized = true;
    try {
      await loadLibraries();
      createScene(options.containerId || 'avatarWrap');
      requestAnimationFrame(animate);
      await loadModel(options.url || '/assets/catalyst/catalyst.vrm');
    } catch (error) {
      console.warn('[Catalyst VRM] renderer startup failed:', error);
      setRuntimeBadge('REFERENCE MODE · 3D RUNTIME UNAVAILABLE');
      setFallbackOpacity(1);
      requestAnimationFrame(animate);
    }
  } else if (options.containerId) {
    mountAvatar(options.containerId);
  }
  return { live: !!currentVrm };
}

window.CatalystAvatar = {
  init: initCatalystVRM,
  setState: setCatalystAvatarState,
  setSpeechLevel: setCatalystSpeechLevel,
  setAppearance: setCatalystAppearance,
  setExpression: setCatalystExpression,
  setGesture: setCatalystGesture,
  setMotion: setCatalystMotionMode,
  mount: mountAvatar,
  isLive: () => !!currentVrm,
};
