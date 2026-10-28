import { useEffect, useState } from 'react';
import { HelixCanvas } from './helix/HelixCanvas';
import { ArrowRight, BookIcon, HelixGlyph, PeopleIcon, Play, ShieldIcon, SproutIcon } from './icons';

const PILLARS = [
  { Icon: BookIcon, label: ['Clear, educational', 'explanations'] },
  { Icon: ShieldIcon, label: ['Your data,', 'your control'] },
  { Icon: PeopleIcon, label: ['Clinically bounded', 'information'] },
  { Icon: SproutIcon, label: ['Guidance to', 'counselling'] },
];

// Genes commonly included in reproductive carrier screening panels. Purely decorative: no values are shown.
const PANEL = ['CFTR', 'HBB', 'SMN1', 'HEXA', 'GJB2'];

const JOURNEY = ['Understand results', 'Manage sharing', 'Get expert guidance'];

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const q = window.matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => setReduced(q.matches);
    q.addEventListener('change', on);
    return () => q.removeEventListener('change', on);
  }, []);
  return reduced;
}

const BASES = 'ATGC';
const SEED_SEQ = ['ATGCTAGTA', 'GCTAAGTCC', 'TAGCTAGCT'];

/** A quietly mutating sequence readout, purely decorative. */
function SequenceReadout() {
  const reduced = usePrefersReducedMotion();
  const [rows, setRows] = useState(SEED_SEQ);
  const [hot, setHot] = useState<[number, number] | null>(null);

  useEffect(() => {
    if (reduced) return;
    const id = window.setInterval(() => {
      const r = Math.floor(Math.random() * rows.length);
      const c = Math.floor(Math.random() * 9);
      setRows((prev) =>
        prev.map((row, i) => (i === r ? row.slice(0, c) + BASES[Math.floor(Math.random() * 4)] + row.slice(c + 1) : row)),
      );
      setHot([r, c]);
    }, 1100);
    return () => window.clearInterval(id);
  }, [reduced, rows.length]);

  return (
    <div className="anno anno-seq" aria-hidden="true">
      {rows.map((row, r) => (
        <div key={r} className="seq-row">
          {row.split('').map((ch, c) => (
            <span key={c} className={hot && hot[0] === r && hot[1] === c ? 'is-hot' : undefined}>
              {ch}
            </span>
          ))}
          {r === 1 && <i className="seq-lead" />}
        </div>
      ))}
      <i className="seq-rule" />
    </div>
  );
}

export function Hero() {
  return (
    <section className="hero" id="top" aria-labelledby="hero-title">
      <HelixCanvas />
      <div className="hero-shade" aria-hidden="true" />

      <div className="hero-content">
        <p className="eyebrow reveal" style={{ ['--d' as string]: '0.1s' }}>
          Genetic risk clarity &amp; care navigator
        </p>
        <h1 id="hero-title" className="hero-title reveal" style={{ ['--d' as string]: '0.2s' }}>
          <span>Understand</span>
          <span>what runs</span>
          <span>
            in <em>your family.</em>
          </span>
        </h1>
        <p className="hero-lede reveal" style={{ ['--d' as string]: '0.35s' }}>
          Wadih helps you interpret inherited-disease screening results, control what is shared, and reach appropriate
          counselling <span className="muted">— through a respectful, privacy-first platform.</span>
        </p>
        <div className="hero-ctas reveal" style={{ ['--d' as string]: '0.45s' }}>
          <a href="/sign-in" className="btn btn-primary">
            Get started <ArrowRight />
          </a>
          <a href="#how-it-works" className="btn btn-ghost">
            <Play /> See how it works
          </a>
        </div>
        <ul className="pillars reveal" style={{ ['--d' as string]: '0.6s' }}>
          {PILLARS.map(({ Icon, label }) => (
            <li key={label[0]}>
              <Icon />
              <span>
                {label[0]}
                <br />
                {label[1]}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Floating annotations — decorative context around the helix. */}
      <div className="anno anno-panel glass" aria-hidden="true">
        <div className="anno-label">Carrier panel</div>
        <ul>
          {PANEL.map((g, i) => (
            <li key={g} style={{ ['--i' as string]: i }}>
              <span>{g}</span>
              <i className="bar">
                <i className="wave" />
              </i>
            </li>
          ))}
        </ul>
        <div className="anno-foot">Illustrative</div>
      </div>

      <div className="anno anno-inherit" aria-hidden="true">
        <div className="anno-label">Inheritance pattern</div>
        <div className="inherit-row">
          <HelixGlyph />
          <span>
            Autosomal
            <br />
            recessive
          </span>
        </div>
        <i className="anno-rule" />
      </div>

      <div className="anno anno-journey glass" aria-hidden="true">
        <div className="anno-label">Your journey</div>
        <ol>
          {JOURNEY.map((s, i) => (
            <li key={s} style={{ ['--i' as string]: i }}>
              <i className="dot" />
              <span>{s}</span>
            </li>
          ))}
        </ol>
      </div>

      <SequenceReadout />

      <a href="#how-it-works" className="scroll-cue" aria-label="Scroll to how it works">
        <span className="mouse" aria-hidden="true">
          <i />
        </span>
        <span>Scroll to explore</span>
        <i className="scroll-line" aria-hidden="true" />
      </a>
    </section>
  );
}
