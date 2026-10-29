/**
 * GLSL for the hero helix. Everything is additive and fresnel-lit so the
 * strands read as glowing glass rather than solid plastic.
 */

/**
 * A slow torsional wave that travels through the molecule, so the helix
 * writhes in 3D on top of its steady spin. Applied in helix-local space.
 */
const torsion = /* glsl */ `
  uniform float uTorsion;
  mat2 torsionAt(float y, float t) {
    float a = uTorsion * (sin(y * 0.19 - t * 0.55) + 0.5 * sin(y * 0.07 + t * 0.31));
    float c = cos(a);
    float s = sin(a);
    return mat2(c, -s, s, c);
  }
`;

/** Glass surfaces: backbone tubes, base-pair rungs, beads, ring atoms and molecule atoms. */
export const glassVertex = /* glsl */ `
  uniform vec3 uColor;
  uniform float uTime;
  ${torsion}
  varying vec3 vNormalW;
  varying vec3 vViewW;
  varying vec3 vColor;
  varying vec3 vLocal;
  varying float vY;
  varying float vDepth;

  void main() {
    vec4 local = vec4(position, 1.0);
    vec3 nrm = normal;
    #ifdef USE_INSTANCING
      local = instanceMatrix * local;
      nrm = mat3(instanceMatrix) * nrm;
    #endif
    mat2 tw = torsionAt(local.y, uTime);
    local.xz = tw * local.xz;
    nrm.xz = tw * nrm.xz;
    vY = local.y;
    vLocal = position * 9.0 + local.xyz * 3.0;
    vec4 world = modelMatrix * local;
    vNormalW = normalize(mat3(modelMatrix) * nrm);
    vViewW = cameraPosition - world.xyz;
    vColor = uColor;
    #ifdef USE_INSTANCING_COLOR
      vColor = instanceColor;
    #endif
    vec4 mv = viewMatrix * world;
    vDepth = -mv.z;
    gl_Position = projectionMatrix * mv;
  }
`;

export const glassFragment = /* glsl */ `
  uniform float uTime;
  uniform float uLength;
  uniform float uGlow;
  uniform float uBody;
  uniform float uPulse;
  uniform float uPulseSpeed;
  uniform float uSpeck;
  uniform float uSheen;
  uniform float uFocal;
  uniform vec3 uTint;
  uniform float uTintMix;
  uniform vec3 uKeyDir;
  uniform vec3 uKeyColor;
  uniform vec3 uRimDir;
  uniform vec3 uRimColor;
  varying vec3 vNormalW;
  varying vec3 vViewW;
  varying vec3 vColor;
  varying vec3 vLocal;
  varying float vY;
  varying float vDepth;

  float hash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }

  void main() {
    vec3 N = normalize(vNormalW);
    vec3 V = normalize(vViewW);
    if (dot(N, V) < 0.0) N = -N; // back faces of the open glass still catch light
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    float edge = 1.0 - ndv;
    float fres = pow(edge, 3.2);

    // Glass walls: light travelling through the wall thickness shows as a thin
    // bright line just inside the silhouette, while the centre stays clear.
    float wall = smoothstep(0.58, 0.76, edge) * (1.0 - smoothstep(0.84, 0.97, edge));

    // Key light (warm) and rim light (cool). Wrapped diffuse decides which side of
    // each strand is lit, so the glow has direction instead of being uniform.
    float kd = clamp(dot(N, uKeyDir) * 0.5 + 0.5, 0.0, 1.0);
    float rd = clamp(dot(N, uRimDir), 0.0, 1.0);
    float spec = pow(max(dot(N, normalize(uKeyDir + V)), 0.0), 140.0);
    float rimSpec = pow(max(dot(N, normalize(uRimDir + V)), 0.0), 60.0);

    // Two soft bands of light travelling up the molecule.
    float span = uLength + 12.0;
    float p1 = mod(uTime * uPulseSpeed, span) - span * 0.5;
    float p2 = mod(uTime * uPulseSpeed + span * 0.55, span) - span * 0.5;
    float pulse = exp(-pow((vY - p1) / 1.7, 2.0)) + 0.55 * exp(-pow((vY - p2) / 1.3, 2.0));
    pulse *= uPulse;

    // Slow teal/amber variation along the length.
    float band = 0.5 + 0.5 * sin(vY * 0.42 + 1.3 + uTime * 0.08);
    vec3 base = mix(vColor, uTint, uTintMix * smoothstep(0.3, 0.95, band));

    // Depth: the far side of the helix recedes into cool shadow, the near side
    // is warmer and brighter, like a shallow cinematic depth of field.
    float dz = clamp((vDepth - uFocal) / 2.2, -1.0, 1.0);
    float depthLight = mix(1.25, 0.32, dz * 0.5 + 0.5);
    base = mix(base, vec3(0.05, 0.32, 0.30), smoothstep(0.0, 1.0, dz) * 0.45);

    // Gold flecks suspended inside the glass, twinkling independently.
    float h = hash(floor(vLocal));
    float speck = step(0.94, h) * pow(0.5 + 0.5 * sin(uTime * (1.5 + h * 3.0) + h * 60.0), 3.0);

    // Subtle thin-film colour shift at grazing angles.
    vec3 film = 0.5 + 0.5 * cos(6.2831 * (edge * 0.9 + vec3(0.0, 0.33, 0.67)) + uTime * 0.15);

    float hl = uLength * 0.5;
    float fade = smoothstep(34.0, 8.0, vDepth) * smoothstep(hl, hl - 5.0, abs(vY));
    fade *= mix(0.35, 1.0, smoothstep(6.0, 11.0, vDepth));

    vec3 col = base * uBody * (0.25 + 0.75 * edge)              // nearly clear centre
             + base * fres * uGlow * (0.3 + 0.9 * kd)            // lit silhouette
             + base * wall * uGlow * 0.3 * (0.4 + 0.6 * kd)      // wall thickness
             + base * film * fres * uSheen * 0.25
             + uKeyColor * spec * uSheen * 0.9                   // small, sharp glints
             + uRimColor * (rimSpec * 0.5 + fres * rd * 0.45) * uSheen
             + base * pulse * 0.75
             + vec3(1.0, 0.72, 0.35) * speck * uSpeck * 0.8;
    col *= depthLight;
    // Soft-limit per fragment so overlapping layers keep their hue instead of clipping to white.
    float peak = max(max(col.r, col.g), col.b);
    col *= 1.0 / (1.0 + peak * 0.6);
    gl_FragColor = vec4(col * fade, 1.0);
  }
`;

/** Hairline bonds inside the base rings, following the same torsion as the glass. */
export const bondVertex = /* glsl */ `
  uniform float uTime;
  ${torsion}
  attribute vec3 color;
  varying vec3 vColor;
  varying float vDepth;
  varying float vY;
  void main() {
    vec3 p = position;
    p.xz = torsionAt(p.y, uTime) * p.xz;
    vY = p.y;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vDepth = -mv.z;
    vColor = color;
    gl_Position = projectionMatrix * mv;
  }
`;

export const bondFragment = /* glsl */ `
  uniform float uLength;
  uniform float uOpacity;
  varying vec3 vColor;
  varying float vDepth;
  varying float vY;
  void main() {
    float hl = uLength * 0.5;
    float fade = smoothstep(34.0, 8.0, vDepth) * smoothstep(hl, hl - 5.0, abs(vY));
    fade *= mix(0.35, 1.0, smoothstep(6.0, 11.0, vDepth));
    gl_FragColor = vec4(vColor * uOpacity * fade, 1.0);
  }
`;

/** Shared depth-of-field: points away from the focal plane grow softer and dimmer. */
const dof = /* glsl */ `
  uniform float uFocal;
  uniform float uDof;
  float cocAt(float depth) {
    return clamp(abs(depth - uFocal) * uDof, 0.0, 3.0);
  }
`;

/** Particles that stream along/around the helix in helix-local space. */
export const flowVertex = /* glsl */ `
  attribute vec4 aParams; // angle0, radius, y0, speed
  attribute vec3 aMisc;   // size, colour mix, phase
  uniform float uTime;
  uniform float uLength;
  uniform float uTwist;
  uniform float uSpin;
  uniform float uWobble;
  uniform float uJitter;
  uniform float uPixelRatio;
  uniform float uScale;
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  ${torsion}
  ${dof}
  varying vec3 vColor;
  varying float vAlpha;
  varying float vSoft;

  void main() {
    float L = uLength;
    float ph = aMisc.z;
    float y = mod(aParams.z + uTime * aParams.w + L * 0.5, L) - L * 0.5;
    float ang = aParams.x + y * uTwist + uTime * uSpin;
    float r = aParams.y * (1.0 + sin(uTime * 0.6 + ph * 6.2831) * uWobble);
    vec3 p = vec3(cos(ang) * r, y, sin(ang) * r);
    // Each particle also wanders on its own slow Lissajous path.
    p += vec3(
      sin(uTime * (0.31 + ph * 0.37) + ph * 21.0),
      sin(uTime * (0.23 + aMisc.y * 0.29) + ph * 13.0) * 0.6,
      cos(uTime * (0.27 + ph * 0.41) + aMisc.y * 9.0)
    ) * uJitter;
    p.xz = torsionAt(p.y, uTime) * p.xz;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;

    float coc = cocAt(-mv.z);
    float twinkle = 0.45 + 0.55 * pow(0.5 + 0.5 * sin(uTime * (1.2 + ph * 2.4) + ph * 40.0), 2.0);
    gl_PointSize = aMisc.x * uPixelRatio * uScale * (1.0 + coc) / -mv.z;
    vColor = mix(uColorA, uColorB, aMisc.y);
    vSoft = clamp(coc * 0.6, 0.0, 1.0);
    vAlpha = twinkle / ((1.0 + coc) * (1.0 + coc))
      * smoothstep(L * 0.5, L * 0.5 - 4.0, abs(y))
      * smoothstep(34.0, 8.0, -mv.z);
  }
`;

/** Free-floating dust and bokeh with a gentle drift. */
export const dustVertex = /* glsl */ `
  attribute vec3 aMisc; // size, colour mix, phase
  uniform float uTime;
  uniform float uPixelRatio;
  uniform float uScale;
  uniform float uDrift;
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  ${dof}
  varying vec3 vColor;
  varying float vAlpha;
  varying float vSoft;

  void main() {
    vec3 p = position;
    p.x += sin(uTime * 0.07 + aMisc.z * 12.0) * uDrift;
    p.y += sin(uTime * 0.05 + aMisc.z * 7.0) * uDrift * 1.4;
    p.z += cos(uTime * 0.06 + aMisc.z * 9.0) * uDrift * 0.6;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float coc = cocAt(-mv.z);
    gl_PointSize = aMisc.x * uPixelRatio * uScale * (1.0 + coc) / max(-mv.z, 0.5);
    vColor = mix(uColorA, uColorB, aMisc.y);
    vSoft = clamp(coc * 0.6, 0.0, 1.0);
    vAlpha = (0.65 + 0.35 * sin(uTime * 0.5 + aMisc.z * 30.0)) / ((1.0 + coc) * (1.0 + coc));
  }
`;

export const pointFragment = /* glsl */ `
  uniform float uSoftness;
  uniform float uOpacity;
  varying vec3 vColor;
  varying float vAlpha;
  varying float vSoft;

  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    if (d > 1.0) discard;
    float core = pow(1.0 - d, 2.6);
    float disc = smoothstep(1.0, 0.72, d) * (0.5 + 0.5 * smoothstep(0.45, 0.95, d));
    // Out-of-focus points open up into soft bokeh discs.
    float a = mix(core, disc * 0.45, max(uSoftness, vSoft));
    gl_FragColor = vec4(vColor * a * vAlpha * uOpacity, 1.0);
  }
`;

/** Full-screen backdrop: deep forest black with breathing teal and amber light. */
export const backdropVertex = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.9999, 1.0);
  }
`;

export const backdropFragment = /* glsl */ `
  uniform float uTime;
  uniform float uAspect;
  uniform float uIntensity;
  uniform vec2 uFocus;
  varying vec2 vUv;

  float glow(vec2 uv, vec2 c, float r) {
    vec2 d = (uv - c) * vec2(uAspect, 1.0);
    return exp(-dot(d, d) / (r * r));
  }

  void main() {
    vec2 uv = vUv;
    vec3 col = vec3(0.006, 0.020, 0.017);
    float breathe = 0.85 + 0.15 * sin(uTime * 0.35);
    col += vec3(0.010, 0.085, 0.068) * glow(uv, uFocus, 0.55) * breathe * uIntensity;
    col += vec3(0.020, 0.060, 0.045) * glow(uv, uFocus + vec2(-0.05, 0.1), 0.25);
    col += vec3(0.090, 0.045, 0.012) * glow(uv, vec2(0.98, 0.1), 0.32) * (0.9 + 0.1 * sin(uTime * 0.27 + 1.0));
    col += vec3(0.070, 0.040, 0.012) * glow(uv, vec2(0.05, 0.05), 0.28);
    col += vec3(0.050, 0.030, 0.010) * glow(uv, vec2(0.93, 0.95), 0.22);
    float vig = smoothstep(1.25, 0.25, length((uv - vec2(0.55, 0.5)) * vec2(1.0, 1.15)));
    col *= mix(0.45, 1.0, vig);
    gl_FragColor = vec4(col, 1.0);
  }
`;
