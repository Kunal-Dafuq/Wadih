import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import {
  backdropFragment,
  backdropVertex,
  bondFragment,
  bondVertex,
  dustVertex,
  flowVertex,
  glassFragment,
  glassVertex,
  pointFragment,
} from './shaders';

const TEAL = new THREE.Color('#38d9c0');
const TEAL_DEEP = new THREE.Color('#118a80');
const AMBER = new THREE.Color('#ffae42');
const GOLD = new THREE.Color('#f7cf86');

const LENGTH = 32;
const RADIUS = 1.15;
const PITCH = 3.4; // units per full turn
const TWIST = (Math.PI * 2) / PITCH;
const STRAND_OFFSET = Math.PI * 0.8; // gives DNA its major/minor groove
const SPIN_SPEED = 0.3; // rad/s around the helix axis
const MOL_Y: [number, number] = [-3, 11]; // vertical band floating molecules drift through
const TORSION = 0.22; // amplitude (rad) of the travelling twist wave

/**
 * Uniform objects shared by every material so lights, twist and focus are
 * updated once per frame. Created per scene instance.
 */
function sharedUniforms() {
  return {
    uKeyDir: { value: new THREE.Vector3(0.6, 0.7, 0.4).normalize() },
    uKeyColor: { value: new THREE.Color('#ffd49a') },
    uRimDir: { value: new THREE.Vector3(-0.8, -0.2, 0.3).normalize() },
    uRimColor: { value: new THREE.Color('#6ff5dc') },
    uTorsion: { value: TORSION },
    uFocal: { value: 12.5 },
    uDof: { value: 0.09 },
  };
}
type Shared = ReturnType<typeof sharedUniforms>;

interface Quality {
  flow: number;
  inner: number;
  dust: number;
  bokeh: number;
  molecules: number;
  maxPixelRatio: number;
  samples: number;
  /** Sphere segments for backbone beads and ring atoms. */
  detail: [number, number];
}

function qualityFor(width: number): Quality {
  const small = width < 760;
  return small
    ? { flow: 700, inner: 600, dust: 260, bokeh: 22, molecules: 7, maxPixelRatio: 1.5, samples: 0, detail: [14, 8] }
    : { flow: 1700, inner: 1400, dust: 650, bokeh: 46, molecules: 14, maxPixelRatio: 2, samples: 4, detail: [22, 10] };
}

/** Small deterministic PRNG so the composition is identical on every load. */
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function strandPoint(y: number, phase: number, radius = RADIUS) {
  const a = y * TWIST + phase;
  return new THREE.Vector3(Math.cos(a) * radius, y, Math.sin(a) * radius);
}

class HelixCurve extends THREE.Curve<THREE.Vector3> {
  constructor(private phase: number) {
    super();
  }
  getPoint(t: number, target = new THREE.Vector3()) {
    const y = (t - 0.5) * LENGTH;
    return target.copy(strandPoint(y, this.phase));
  }
}

function glassMaterial(
  shared: Shared,
  opts: {
    color: THREE.Color;
    tint?: THREE.Color;
    tintMix?: number;
    glow?: number;
    body?: number;
    pulse?: number;
    speck?: number;
    sheen?: number;
    torsion?: boolean;
  },
) {
  return new THREE.ShaderMaterial({
    vertexShader: glassVertex,
    fragmentShader: glassFragment,
    uniforms: {
      uKeyDir: shared.uKeyDir,
      uKeyColor: shared.uKeyColor,
      uRimDir: shared.uRimDir,
      uRimColor: shared.uRimColor,
      uTorsion: opts.torsion === false ? { value: 0 } : shared.uTorsion,
      uSpeck: { value: opts.speck ?? 0 },
      uSheen: { value: opts.sheen ?? 1 },
      uFocal: shared.uFocal,
      uTime: { value: 0 },
      uLength: { value: LENGTH },
      uColor: { value: opts.color.clone() },
      uTint: { value: (opts.tint ?? opts.color).clone() },
      uTintMix: { value: opts.tintMix ?? 0 },
      uGlow: { value: opts.glow ?? 1.4 },
      uBody: { value: opts.body ?? 0.08 },
      uPulse: { value: opts.pulse ?? 1 },
      uPulseSpeed: { value: 2.4 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
}

function pointsMaterial(
  shared: Shared,
  vertexShader: string,
  uniforms: Record<string, THREE.IUniform>,
  softness: number,
) {
  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader: pointFragment,
    uniforms: {
      uFocal: shared.uFocal,
      uDof: shared.uDof,
      uTorsion: shared.uTorsion,
      uJitter: { value: 0 },
      uTime: { value: 0 },
      uPixelRatio: { value: 1 },
      uSoftness: { value: softness },
      uOpacity: { value: 1 },
      ...uniforms,
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
}

export interface HelixSceneOptions {
  reducedMotion: boolean;
}

export class HelixScene {
  private renderer: THREE.WebGLRenderer;
  private composer: EffectComposer;
  private bloom: UnrealBloomPass;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(34, 1, 0.1, 120);
  private rig = new THREE.Group(); // tilt + placement of the hero helix
  private spin = new THREE.Group(); // rotates about the helix axis
  private ghosts: THREE.Group[] = [];
  private molecules: { group: THREE.Group; velocity: THREE.Vector3; spin: THREE.Vector3 }[] = [];
  private timed: THREE.ShaderMaterial[] = [];
  private pixelRatioMats: THREE.ShaderMaterial[] = [];
  private backdrop: THREE.ShaderMaterial;
  private quality: Quality;
  private shared = sharedUniforms();
  private focus = new THREE.Vector3();
  private width = 1;
  private height = 1;
  private time = 6; // start mid-motion so the first frame is already composed
  private last = 0;
  private raf = 0;
  private running = false;
  private reducedMotion: boolean;
  private pointer = new THREE.Vector2();
  private pointerSmooth = new THREE.Vector2();

  constructor(private container: HTMLElement, opts: HelixSceneOptions) {
    this.reducedMotion = opts.reducedMotion;
    const rect = container.getBoundingClientRect();
    this.width = Math.max(1, rect.width);
    this.height = Math.max(1, rect.height);
    this.quality = qualityFor(this.width);

    this.renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.quality.maxPixelRatio));
    this.renderer.setSize(this.width, this.height, false);
    this.renderer.toneMapping = THREE.NeutralToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.setClearColor('#020806', 1);
    this.renderer.domElement.setAttribute('aria-hidden', 'true');
    container.appendChild(this.renderer.domElement);

    this.camera.position.set(0, 0, 14);
    this.scene.add(this.rig);
    this.rig.add(this.spin);

    this.backdrop = new THREE.ShaderMaterial({
      vertexShader: backdropVertex,
      fragmentShader: backdropFragment,
      uniforms: {
        uTime: { value: 0 },
        uAspect: { value: 1 },
        uIntensity: { value: 1 },
        uFocus: { value: new THREE.Vector2(0.64, 0.55) },
      },
      depthWrite: false,
      depthTest: false,
    });
    const bg = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.backdrop);
    bg.frustumCulled = false;
    bg.renderOrder = -10;
    this.scene.add(bg);
    this.timed.push(this.backdrop);

    this.buildHelix();
    this.buildFlow();
    this.buildMolecules();
    this.buildAtmosphere();

    const target = new THREE.WebGLRenderTarget(1, 1, {
      type: THREE.HalfFloatType,
      samples: this.quality.samples,
    });
    this.composer = new EffectComposer(this.renderer, target);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(this.width, this.height), 0.62, 0.45, 0.48);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.resize();
  }

  // ---------------------------------------------------------------- building

  private buildHelix() {
    const sh = this.shared;
    const strands: [number, THREE.Color, THREE.Color][] = [
      [0, AMBER, GOLD],
      [STRAND_OFFSET, TEAL, TEAL_DEEP],
    ];

    for (const [phase, color, tint] of strands) {
      const curve = new HelixCurve(phase);
      // Outer glass sheath binding the sugar-phosphate chain together.
      const sheath = new THREE.Mesh(
        new THREE.TubeGeometry(curve, 1000, 0.085, 14, false),
        glassMaterial(sh, { color, tint, tintMix: 0.5, glow: 0.75, body: 0.03, speck: 0.4, sheen: 0.8 }),
      );
      // Thin luminous core visible through the glass.
      const core = new THREE.Mesh(
        new THREE.TubeGeometry(curve, 1000, 0.022, 6, false),
        glassMaterial(sh, { color: GOLD, tint: AMBER, tintMix: 0.6, glow: 0.12, body: 0.16, sheen: 0 }),
      );
      this.spin.add(sheath, core);
      this.timed.push(sheath.material as THREE.ShaderMaterial, core.material as THREE.ShaderMaterial);
    }

    const rand = mulberry32(7);
    const perTurn = 10.5;
    const count = Math.floor((LENGTH / PITCH) * perTurn);
    const step = LENGTH / count;
    const up = new THREE.Vector3(0, 1, 0);
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();

    // Backbone: a sugar (large) then two phosphate-group (small) glass beads per base pair.
    const chainPerStrand = count * 3;
    const chain = new THREE.InstancedMesh(
      new THREE.SphereGeometry(1, this.quality.detail[0], Math.round(this.quality.detail[0] * 0.65)),
      glassMaterial(sh, { color: GOLD, glow: 0.7, body: 0.03, speck: 1.0, sheen: 0.9 }),
      chainPerStrand * 2,
    );
    let ci = 0;
    for (const [phase, warm] of [
      [0, true],
      [STRAND_OFFSET, false],
    ] as const) {
      for (let k = 0; k < chainPerStrand; k++) {
        const y = -LENGTH / 2 + (k / 3 + 0.5) * step;
        const r = k % 3 === 0 ? 0.15 : k % 3 === 1 ? 0.1 : 0.085;
        m.compose(strandPoint(y, phase), q.identity(), s.set(r, r, r));
        chain.setMatrixAt(ci, m);
        const roll = rand();
        chain.setColorAt(ci, warm ? (roll > 0.5 ? AMBER : GOLD) : roll > 0.18 ? (roll > 0.6 ? TEAL : TEAL_DEEP) : GOLD);
        ci++;
      }
    }

    // Base pairs: a stalk from each backbone ending in a purine or pyrimidine ring.
    const rungs = new THREE.InstancedMesh(
      new THREE.CylinderGeometry(0.028, 0.028, 1, 8, 1, true),
      glassMaterial(sh, { color: TEAL, glow: 0.8, body: 0.06, sheen: 0.6 }),
      count * 2,
    );
    const ringAtoms: { p: THREE.Vector3; c: THREE.Color; r: number }[] = [];
    const bondPos: number[] = [];
    const bondCol: number[] = [];
    const hBond = new THREE.Color('#bfeee0');
    const pairColors: [THREE.Color, THREE.Color][] = [
      [TEAL, new THREE.Color('#7ff3dc')],
      [AMBER, GOLD],
      [new THREE.Color('#7ff3dc'), TEAL],
      [GOLD, AMBER],
    ];

    const addBond = (a: THREE.Vector3, b: THREE.Vector3, c: THREE.Color) => {
      bondPos.push(a.x, a.y, a.z, b.x, b.y, b.z);
      bondCol.push(c.r, c.g, c.b, c.r, c.g, c.b);
    };

    /** Lays a 6-ring (pyrimidine) or fused 6+5 ring (purine) in the base plane spanned by u, v. */
    const addRing = (center: THREE.Vector3, u: THREE.Vector3, v: THREE.Vector3, purine: boolean, c: THREE.Color) => {
      const r6 = 0.1;
      const at = (x: number, y: number) => center.clone().addScaledVector(u, x).addScaledVector(v, y);
      const hex: THREE.Vector3[] = [];
      for (let k = 0; k < 6; k++) {
        const a = (k / 6) * Math.PI * 2 + Math.PI / 6;
        hex.push(at(Math.cos(a) * r6, Math.sin(a) * r6));
      }
      hex.forEach((p, k) => {
        ringAtoms.push({ p, c, r: 0.024 });
        addBond(p, hex[(k + 1) % 6], c);
      });
      if (purine) {
        // Five-membered ring fused on the edge facing the backbone.
        const e0 = hex[2];
        const e1 = hex[3];
        const mid = e0.clone().lerp(e1, 0.5);
        const out = mid.clone().sub(center).normalize();
        const p1 = e0.clone().addScaledVector(out, 0.085);
        const p2 = e1.clone().addScaledVector(out, 0.085);
        const tip = mid.clone().addScaledVector(out, 0.14);
        for (const p of [p1, p2, tip]) ringAtoms.push({ p, c, r: 0.022 });
        addBond(e0, p1, c);
        addBond(p1, tip, c);
        addBond(tip, p2, c);
        addBond(p2, e1, c);
      }
      // One exocyclic atom gives each base a little asymmetry.
      const ext = hex[0].clone().addScaledVector(hex[0].clone().sub(center).normalize(), 0.07);
      ringAtoms.push({ p: ext, c: GOLD, r: 0.02 });
      addBond(hex[0], ext, GOLD);
    };

    for (let i = 0; i < count; i++) {
      const y = -LENGTH / 2 + (i + 0.5) * step;
      const a = strandPoint(y, 0, RADIUS - 0.06);
      const b = strandPoint(y, STRAND_OFFSET, RADIUS - 0.06);
      const dirAB = b.clone().sub(a);
      const span = dirAB.length();
      dirAB.normalize();
      const [ca, cb] = pairColors[Math.floor(rand() * pairColors.length)];
      const purineA = rand() < 0.5;
      // Base planes sit across the axis; a propeller twist lets them read in perspective.
      const side = new THREE.Vector3().crossVectors(up, dirAB).normalize();

      const halves: [THREE.Vector3, number, THREE.Color, boolean, number][] = [
        [a, 1, ca, purineA, 0.17],
        [b, -1, cb, !purineA, -0.17],
      ];
      halves.forEach(([origin, dirSign, c, purine, prop], h) => {
        const dir = dirAB.clone().multiplyScalar(dirSign);
        const ringCenter = origin.clone().addScaledVector(dir, span * 0.5 - (purine ? 0.2 : 0.15));
        const v = side.clone().applyAxisAngle(dir, prop * Math.PI + 0.35).normalize();
        addRing(ringCenter, dir, v, purine, c);

        const stalkEnd = ringCenter.clone().addScaledVector(dir, -0.1);
        const len = origin.distanceTo(stalkEnd);
        q.setFromUnitVectors(up, dir);
        m.compose(origin.clone().lerp(stalkEnd, 0.5), q, s.set(1, len, 1));
        rungs.setMatrixAt(i * 2 + h, m);
        rungs.setColorAt(i * 2 + h, c);
      });

      // Hydrogen bonds bridging the two bases across the middle.
      const mid = a.clone().lerp(b, 0.5);
      for (const off of [-0.04, 0.04]) {
        const o = side.clone().multiplyScalar(off);
        addBond(mid.clone().addScaledVector(dirAB, -0.06).add(o), mid.clone().addScaledVector(dirAB, 0.06).add(o), hBond);
      }
    }

    const atoms = new THREE.InstancedMesh(
      new THREE.SphereGeometry(1, this.quality.detail[1], Math.round(this.quality.detail[1] * 0.7)),
      glassMaterial(sh, { color: TEAL, glow: 1.1, body: 0.5, sheen: 0.4 }),
      ringAtoms.length,
    );
    ringAtoms.forEach(({ p, c, r }, k) => {
      m.compose(p, q.identity(), s.set(r, r, r));
      atoms.setMatrixAt(k, m);
      atoms.setColorAt(k, c);
    });

    const bondGeo = new THREE.BufferGeometry();
    bondGeo.setAttribute('position', new THREE.Float32BufferAttribute(bondPos, 3));
    bondGeo.setAttribute('color', new THREE.Float32BufferAttribute(bondCol, 3));
    const bondMat = new THREE.ShaderMaterial({
      vertexShader: bondVertex,
      fragmentShader: bondFragment,
      uniforms: {
        uTime: { value: 0 },
        uTorsion: sh.uTorsion,
        uLength: { value: LENGTH },
        uOpacity: { value: 0.55 },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const bonds = new THREE.LineSegments(bondGeo, bondMat);

    for (const obj of [chain, rungs, atoms, bonds]) {
      obj.frustumCulled = false;
      this.spin.add(obj);
      this.timed.push(obj.material as THREE.ShaderMaterial);
    }
  }

  /** Points for a helix laid out as particles; used for glowing interiors and defocused background helices. */
  private helixParticles(count: number, rand: () => number, jitter: number, speedRange: [number, number]) {
    const params = new Float32Array(count * 4);
    const misc = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const strand = rand() < 0.5 ? 0 : STRAND_OFFSET;
      params[i * 4] = strand + (rand() - 0.5) * jitter;
      params[i * 4 + 1] = RADIUS + (rand() - 0.5) * jitter * 1.6;
      params[i * 4 + 2] = (rand() - 0.5) * LENGTH;
      params[i * 4 + 3] = speedRange[0] + rand() * (speedRange[1] - speedRange[0]);
      misc[i * 3] = 0.6 + rand() * 1.6;
      misc[i * 3 + 1] = rand();
      misc[i * 3 + 2] = rand();
    }
    return { params, misc };
  }

  private buildFlow() {
    const rand = mulberry32(21);
    const q = this.quality;

    // Sparks travelling inside the glass strands.
    {
      const { params, misc } = this.helixParticles(q.inner, rand, 0.12, [0.15, 0.6]);
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(q.inner * 3), 3));
      geo.setAttribute('aParams', new THREE.BufferAttribute(params, 4));
      geo.setAttribute('aMisc', new THREE.BufferAttribute(misc, 3));
      const mat = pointsMaterial(
        this.shared,
        flowVertex,
        {
          uLength: { value: LENGTH },
          uTwist: { value: TWIST },
          uSpin: { value: 0 },
          uWobble: { value: 0.02 },
          uJitter: { value: 0.025 },
          uScale: { value: 34 },
          uColorA: { value: GOLD.clone().multiplyScalar(0.7) },
          uColorB: { value: new THREE.Color('#9ffbe8').multiplyScalar(0.5) },
        },
        0,
      );
      const pts = new THREE.Points(geo, mat);
      pts.frustumCulled = false;
      this.spin.add(pts);
      this.timed.push(mat);
      this.pixelRatioMats.push(mat);
    }

    // Particles orbiting the molecule: a tight stream along the grooves plus a looser halo.
    {
      const n = q.flow;
      const params = new Float32Array(n * 4);
      const misc = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const halo = rand() < 0.55;
        const r = halo ? RADIUS + 0.6 + Math.pow(rand(), 1.6) * 4.2 : RADIUS * (0.4 + rand() * 0.9);
        params[i * 4] = rand() * Math.PI * 2;
        params[i * 4 + 1] = r;
        params[i * 4 + 2] = (rand() - 0.5) * LENGTH;
        params[i * 4 + 3] = (halo ? 0.12 : 0.35) + rand() * 0.35;
        misc[i * 3] = halo ? 0.6 + Math.pow(rand(), 3) * 3.2 : 0.5 + rand() * 1.2;
        misc[i * 3 + 1] = rand() < 0.62 ? rand() * 0.25 : 0.75 + rand() * 0.25;
        misc[i * 3 + 2] = rand();
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
      geo.setAttribute('aParams', new THREE.BufferAttribute(params, 4));
      geo.setAttribute('aMisc', new THREE.BufferAttribute(misc, 3));
      const mat = pointsMaterial(
        this.shared,
        flowVertex,
        {
          uLength: { value: LENGTH },
          uTwist: { value: TWIST * 0.35 },
          uSpin: { value: -0.12 },
          uWobble: { value: 0.08 },
          uJitter: { value: 0.22 },
          uScale: { value: 36 },
          uColorA: { value: AMBER.clone().multiplyScalar(0.75) },
          uColorB: { value: new THREE.Color('#5ff0d6').multiplyScalar(0.5) },
        },
        0,
      );
      const pts = new THREE.Points(geo, mat);
      pts.frustumCulled = false;
      this.rig.add(pts);
      this.timed.push(mat);
      this.pixelRatioMats.push(mat);
    }
  }

  private buildMolecules() {
    const rand = mulberry32(99);
    const atomGeo = new THREE.SphereGeometry(1, 18, 12);
    const bondMat = new THREE.LineBasicMaterial({
      color: new THREE.Color('#c9a46a'),
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    for (let k = 0; k < this.quality.molecules; k++) {
      const atoms = 3 + Math.floor(rand() * 5);
      const positions: THREE.Vector3[] = [new THREE.Vector3()];
      const bonds: number[] = [];
      for (let i = 1; i < atoms; i++) {
        const from = positions[Math.floor(rand() * positions.length)];
        const dir = new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).normalize();
        const p = from.clone().addScaledVector(dir, 0.32 + rand() * 0.14);
        positions.push(p);
        bonds.push(from.x, from.y, from.z, p.x, p.y, p.z);
      }
      const warm = rand() < 0.55;
      const mesh = new THREE.InstancedMesh(
        atomGeo,
        glassMaterial(this.shared, { color: warm ? AMBER : TEAL, glow: 1.2, body: 0.2, pulse: 0, torsion: false }),
        atoms,
      );
      const m = new THREE.Matrix4();
      positions.forEach((p, i) => {
        const r = (i === 0 ? 0.11 : 0.055) + rand() * 0.05;
        m.compose(p, new THREE.Quaternion(), new THREE.Vector3(r, r, r));
        mesh.setMatrixAt(i, m);
        mesh.setColorAt(i, rand() < 0.75 ? (warm ? AMBER : TEAL) : GOLD);
      });
      mesh.frustumCulled = false;
      (mesh.material as THREE.ShaderMaterial).uniforms.uLength.value = 1000;
      this.timed.push(mesh.material as THREE.ShaderMaterial);

      const bondGeo = new THREE.BufferGeometry();
      bondGeo.setAttribute('position', new THREE.Float32BufferAttribute(bonds, 3));
      const group = new THREE.Group();
      group.add(mesh, new THREE.LineSegments(bondGeo, bondMat));

      // Keep molecules on the far side of the helix from the headline (rig +x, upper half).
      const angle = (rand() - 0.5) * Math.PI * 0.9;
      const dist = RADIUS + 0.7 + rand() * 1.8;
      group.position.set(Math.cos(angle) * dist, MOL_Y[0] + rand() * (MOL_Y[1] - MOL_Y[0]), Math.sin(angle) * dist);
      const scale = 0.45 + rand() * 0.55;
      group.scale.setScalar(scale);
      this.rig.add(group);
      this.molecules.push({
        group,
        velocity: new THREE.Vector3((rand() - 0.5) * 0.04, 0.08 + rand() * 0.12, (rand() - 0.5) * 0.04),
        spin: new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).multiplyScalar(0.5),
      });
    }
  }

  private buildAtmosphere() {
    const rand = mulberry32(314);
    const q = this.quality;

    const dustCloud = (n: number, box: [number, number, number], zOffset: number, sizes: [number, number], warmBias: number) => {
      const pos = new Float32Array(n * 3);
      const misc = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        pos[i * 3] = (rand() - 0.5) * box[0];
        pos[i * 3 + 1] = (rand() - 0.5) * box[1];
        pos[i * 3 + 2] = zOffset + (rand() - 0.5) * box[2];
        misc[i * 3] = sizes[0] + Math.pow(rand(), 2.2) * (sizes[1] - sizes[0]);
        misc[i * 3 + 1] = rand() < warmBias ? rand() * 0.3 : 0.7 + rand() * 0.3;
        misc[i * 3 + 2] = rand();
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.setAttribute('aMisc', new THREE.BufferAttribute(misc, 3));
      return geo;
    };

    // Fine suspended dust across the frame.
    {
      const mat = pointsMaterial(
        this.shared,
        dustVertex,
        {
          uScale: { value: 30 },
          uDrift: { value: 0.5 },
          uColorA: { value: AMBER.clone() },
          uColorB: { value: TEAL.clone() },
        },
        0,
      );
      mat.uniforms.uOpacity.value = 0.45;
      const pts = new THREE.Points(dustCloud(q.dust, [34, 22, 18], -3, [0.4, 2.2], 0.6), mat);
      pts.frustumCulled = false;
      this.scene.add(pts);
      this.timed.push(mat);
      this.pixelRatioMats.push(mat);
    }

    // Large out-of-focus bokeh, some very close to the lens.
    {
      const mat = pointsMaterial(
        this.shared,
        dustVertex,
        {
          uScale: { value: 60 },
          uDrift: { value: 0.35 },
          uDof: { value: 0 },
          uColorA: { value: AMBER.clone().multiplyScalar(0.9) },
          uColorB: { value: TEAL_DEEP.clone() },
        },
        1,
      );
      mat.uniforms.uOpacity.value = 0.12;
      const pts = new THREE.Points(dustCloud(q.bokeh, [30, 18, 16], -2, [4, 16], 0.7), mat);
      pts.frustumCulled = false;
      this.scene.add(pts);
      this.timed.push(mat);
      this.pixelRatioMats.push(mat);
    }

    // Defocused helices in the distance for depth.
    const ghostDefs: { pos: [number, number, number]; rot: [number, number, number]; n: number; size: number; opacity: number }[] = [
      { pos: [-9, 1, -16], rot: [0.2, 0, 0.55], n: 900, size: 8, opacity: 0.09 },
      { pos: [13, -2, -20], rot: [0.1, 0, -0.25], n: 800, size: 9, opacity: 0.07 },
      { pos: [-3, -7, -9], rot: [0.4, 0, -1.25], n: 500, size: 6, opacity: 0.07 },
    ];
    for (const def of ghostDefs) {
      const n = Math.round(def.n * (q.flow / 1700));
      const { params, misc } = this.helixParticles(n, rand, 0.35, [0.05, 0.15]);
      for (let i = 0; i < n; i++) misc[i * 3] = def.size * (0.5 + rand());
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
      geo.setAttribute('aParams', new THREE.BufferAttribute(params, 4));
      geo.setAttribute('aMisc', new THREE.BufferAttribute(misc, 3));
      const mat = pointsMaterial(
        this.shared,
        flowVertex,
        {
          uLength: { value: LENGTH },
          uTwist: { value: TWIST },
          uSpin: { value: 0 },
          uWobble: { value: 0.0 },
          uDof: { value: 0 },
          uTorsion: { value: 0 },
          uScale: { value: 30 },
          uColorA: { value: AMBER.clone() },
          uColorB: { value: TEAL.clone() },
        },
        1,
      );
      mat.uniforms.uOpacity.value = def.opacity;
      // These sit far back, so drop the near-camera distance fade.
      mat.vertexShader = mat.vertexShader.replace('smoothstep(34.0, 8.0, -mv.z)', '1.0');
      const pts = new THREE.Points(geo, mat);
      pts.frustumCulled = false;
      const g = new THREE.Group();
      g.position.set(...def.pos);
      g.rotation.set(...def.rot);
      g.add(pts);
      this.scene.add(g);
      this.ghosts.push(g);
      this.timed.push(mat);
      this.pixelRatioMats.push(mat);
    }
  }

  // ----------------------------------------------------------------- runtime

  /** Pointer in -1..1 for a subtle parallax. */
  setPointer(x: number, y: number) {
    this.pointer.set(x, y);
  }

  setReducedMotion(value: boolean) {
    this.reducedMotion = value;
    if (value) {
      this.stop();
      this.renderFrame();
    }
  }

  resize() {
    const rect = this.container.getBoundingClientRect();
    this.width = Math.max(1, rect.width);
    this.height = Math.max(1, rect.height);
    const pr = Math.min(window.devicePixelRatio || 1, this.quality.maxPixelRatio);
    this.renderer.setPixelRatio(pr);
    this.renderer.setSize(this.width, this.height, false);
    this.composer.setPixelRatio(pr);
    this.composer.setSize(this.width, this.height);
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    for (const mat of this.pixelRatioMats) mat.uniforms.uPixelRatio.value = pr;
    this.backdrop.uniforms.uAspect.value = this.camera.aspect;
    this.layout();
    if (!this.running) this.renderFrame();
  }

  /** Places the helix for the current aspect ratio, mirroring the reference composition. */
  private layout() {
    const aspect = this.camera.aspect;
    const halfH = Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)) * this.camera.position.z;
    const halfW = halfH * aspect;
    if (aspect >= 1.15) {
      // Landscape: helix in the right ~55% of the frame, rising to the upper right.
      this.rig.position.set(halfW * 0.2, -0.3, 1.6);
      this.rig.rotation.set(0.32, 0.1, -0.56);
      this.camera.fov = 34;
      this.backdrop.uniforms.uFocus.value.set(0.64, 0.52);
      this.backdrop.uniforms.uIntensity.value = 0.72;
    } else {
      // Portrait: helix rises behind the copy, slightly set back.
      this.rig.position.set(halfW * 0.3, halfH * 0.36, -3);
      this.rig.rotation.set(0.3, 0.1, -0.5);
      this.camera.fov = 40;
      this.backdrop.uniforms.uFocus.value.set(0.6, 0.72);
      this.backdrop.uniforms.uIntensity.value = 0.45;
    }
    this.camera.updateProjectionMatrix();
  }

  private update(dt: number) {
    this.time += dt;
    const t = this.time;
    for (const mat of this.timed) mat.uniforms.uTime.value = t;

    this.spin.rotation.y = t * SPIN_SPEED;
    // A slow, breathing sway on the whole molecule.
    this.spin.position.y = Math.sin(t * 0.18) * 0.25;
    this.rig.rotation.x += (0.32 + Math.sin(t * 0.13) * 0.03 - this.rig.rotation.x) * 0.05;

    for (const g of this.ghosts) g.rotation.y = t * 0.12;

    // Key light slowly orbits so glints travel across the glass; rim light breathes.
    const sh = this.shared;
    sh.uKeyDir.value.set(Math.cos(t * 0.16) * 0.7, 0.6 + Math.sin(t * 0.11) * 0.2, 0.45 + Math.sin(t * 0.16) * 0.35).normalize();
    sh.uRimDir.value.set(-0.8, -0.2 + Math.sin(t * 0.09) * 0.25, 0.3).normalize();
    sh.uKeyColor.value.setRGB(1.0, 0.83, 0.6).multiplyScalar(0.9 + Math.sin(t * 0.4) * 0.1);

    for (const mol of this.molecules) {
      const g = mol.group;
      g.position.addScaledVector(mol.velocity, dt);
      if (g.position.y > MOL_Y[1]) g.position.y = MOL_Y[0];
      g.rotation.x += mol.spin.x * dt;
      g.rotation.y += mol.spin.y * dt;
      g.rotation.z += mol.spin.z * dt;
    }

    // Parallax.
    this.pointerSmooth.lerp(this.pointer, Math.min(1, dt * 2.5));
    this.camera.position.x = this.pointerSmooth.x * 0.45;
    this.camera.position.y = this.pointerSmooth.y * 0.3;
    this.camera.lookAt(0, 0, 0);

    // Keep the helix in the focal plane for the particle depth-of-field.
    this.rig.getWorldPosition(this.focus);
    sh.uFocal.value = this.camera.position.distanceTo(this.focus);
  }

  private renderFrame() {
    if (this.reducedMotion) this.update(0);
    this.composer.render();
  }

  private loop = (now: number) => {
    if (!this.running) return;
    const dt = this.last ? Math.min((now - this.last) / 1000, 1 / 20) : 0;
    this.last = now;
    this.update(dt);
    this.composer.render();
    this.raf = requestAnimationFrame(this.loop);
  };

  start() {
    if (this.running) return;
    if (this.reducedMotion) {
      this.renderFrame();
      return;
    }
    this.running = true;
    this.last = 0;
    this.raf = requestAnimationFrame(this.loop);
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.raf);
  }

  dispose() {
    this.stop();
    this.scene.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      mesh.geometry?.dispose();
      const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
      else mat?.dispose();
    });
    this.composer.dispose();
    this.bloom.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
