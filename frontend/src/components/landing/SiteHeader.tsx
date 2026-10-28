import { useEffect, useState } from 'react';
import { ArrowRight, Logo } from './icons';

export const NAV_LINKS = [
  { href: '#how-it-works', label: 'How it works' },
  { href: '#approach', label: 'Our approach' },
  { href: '#use-cases', label: 'Use cases' },
  { href: '#resources', label: 'Resources' },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className="site-header" data-scrolled={scrolled} data-open={open}>
      <a href="#top" className="brand" aria-label="Wadih home">
        <Logo />
        <span>Wadih</span>
      </a>

      <nav className="nav-pill" aria-label="Primary">
        {NAV_LINKS.map((l, i) => (
          <span key={l.href} className="nav-item">
            {i > 0 && <span className="nav-dot" aria-hidden="true" />}
            <a href={l.href}>{l.label}</a>
          </span>
        ))}
      </nav>

      <div className="header-actions">
        <a href="/sign-in" className="sign-in">
          Sign in
        </a>
        <a href="/sign-in" className="btn btn-primary btn-sm">
          Get started <ArrowRight />
        </a>
        <button
          type="button"
          className="menu-toggle"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>
      </div>

      <nav id="mobile-nav" className="mobile-nav" aria-label="Mobile" hidden={!open}>
        {NAV_LINKS.map((l) => (
          <a key={l.href} href={l.href} onClick={() => setOpen(false)}>
            {l.label}
          </a>
        ))}
      </nav>
    </header>
  );
}
