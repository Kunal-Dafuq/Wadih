import { useEffect, useRef, useState } from 'react';
import type { HelixScene } from './HelixScene';

/**
 * Mounts the WebGL helix behind the hero. Pauses when off-screen or the tab is
 * hidden, and renders a single still frame for reduced-motion users.
 */
export function HelixCanvas() {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'fallback'>('loading');

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let scene: HelixScene | null = null;
    let cancelled = false;
    let visible = true;
    const cleanups: (() => void)[] = [];
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    const sync = () => {
      if (!scene) return;
      if (visible && document.visibilityState === 'visible') scene.start();
      else scene.stop();
    };

    import('./HelixScene')
      .then(({ HelixScene }) => {
        if (cancelled) return;
        try {
          scene = new HelixScene(el, { reducedMotion: motionQuery.matches });
        } catch {
          setState('fallback');
          return;
        }
        const s = scene;
        setState('ready');
        sync();

        const ro = new ResizeObserver(() => s.resize());
        ro.observe(el);
        cleanups.push(() => ro.disconnect());

        const io = new IntersectionObserver(([entry]) => {
          visible = entry.isIntersecting;
          sync();
        });
        io.observe(el);
        cleanups.push(() => io.disconnect());

        document.addEventListener('visibilitychange', sync);
        cleanups.push(() => document.removeEventListener('visibilitychange', sync));

        const onMotion = () => {
          s.setReducedMotion(motionQuery.matches);
          sync();
        };
        motionQuery.addEventListener('change', onMotion);
        cleanups.push(() => motionQuery.removeEventListener('change', onMotion));

        if (window.matchMedia('(pointer: fine)').matches) {
          const onMove = (e: PointerEvent) => {
            s.setPointer((e.clientX / window.innerWidth) * 2 - 1, -((e.clientY / window.innerHeight) * 2 - 1));
          };
          window.addEventListener('pointermove', onMove, { passive: true });
          cleanups.push(() => window.removeEventListener('pointermove', onMove));
        }
      })
      .catch(() => setState('fallback'));

    return () => {
      cancelled = true;
      cleanups.forEach((fn) => fn());
      scene?.dispose();
    };
  }, []);

  return <div ref={ref} className="helix-canvas" data-state={state} aria-hidden="true" />;
}
