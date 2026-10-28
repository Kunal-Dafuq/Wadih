import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.4,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
};

export const ArrowRight = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="18" height="18" {...base} strokeWidth={1.8} {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const Play = (p: IconProps) => (
  <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden {...p}>
    <circle cx="12" cy="12" r="12" fill="currentColor" />
    <path d="M10 8.2v7.6L16 12z" fill="var(--bg)" />
  </svg>
);

export const BookIcon = (p: IconProps) => (
  <svg viewBox="0 0 40 40" width="40" height="40" {...base} {...p}>
    <path d="M20 11c-3.5-2.4-8.5-3-14-2.4v21c5.5-.6 10.5 0 14 2.4 3.5-2.4 8.5-3 14-2.4v-21c-5.5-.6-10.5 0-14 2.4z" />
    <path d="M20 11v21" />
    <path d="M10 14.5c2.6-.1 4.8.3 6.6 1M10 19c2.6-.1 4.8.3 6.6 1M23.4 15.5c1.8-.7 4-1.1 6.6-1M23.4 20c1.8-.7 4-1.1 6.6-1" opacity=".6" />
  </svg>
);

export const ShieldIcon = (p: IconProps) => (
  <svg viewBox="0 0 40 40" width="40" height="40" {...base} {...p}>
    <path d="M20 5l12 4.5v9c0 8-5.2 13.6-12 16.5C13.2 32.1 8 26.5 8 18.5v-9z" />
    <path d="M14.5 20l4 4 7-8" />
  </svg>
);

export const PeopleIcon = (p: IconProps) => (
  <svg viewBox="0 0 40 40" width="40" height="40" {...base} {...p}>
    <circle cx="20" cy="12" r="4" />
    <circle cx="9.5" cy="15" r="3.2" />
    <circle cx="30.5" cy="15" r="3.2" />
    <path d="M12.5 31c0-5 3.4-9 7.5-9s7.5 4 7.5 9" />
    <path d="M4 30c0-4 2.5-7.2 5.5-7.2 1.4 0 2.6.6 3.6 1.6M36 30c0-4-2.5-7.2-5.5-7.2-1.4 0-2.6.6-3.6 1.6" />
  </svg>
);

export const SproutIcon = (p: IconProps) => (
  <svg viewBox="0 0 40 40" width="40" height="40" {...base} {...p}>
    <path d="M21 22v-8" />
    <path d="M21 14c0-4.5 3.5-8 9-8 0 5-3.6 8-9 8zM21 17c0-3.6-2.8-6.3-7.2-6.3 0 4 2.9 6.3 7.2 6.3z" />
    <path d="M4 27.5h5.5l6 2.2h6.3a2 2 0 0 1 0 4H15M9.5 34.5l13.3.5 11-5.4a2 2 0 0 0-1.9-3.5L25 29.4" />
  </svg>
);

export const HelixGlyph = (p: IconProps) => (
  <svg viewBox="0 0 24 40" width="24" height="40" {...base} strokeWidth={1.5} {...p}>
    <path d="M4 3c0 8 16 9 16 17S4 29 4 37M20 3c0 8-16 9-16 17s16 9 16 17" />
    <path d="M7 8h10M6 14h12M7 26h10M6 32h12" opacity=".6" />
  </svg>
);

export const Logo = (p: IconProps) => (
  <svg viewBox="0 0 36 40" width="34" height="38" aria-hidden {...p}>
    <defs>
      <linearGradient id="wadih-leaf" x1="0" y1="1" x2="1" y2="0">
        <stop offset="0" stopColor="#4f9a6f" />
        <stop offset="1" stopColor="#b6e4a6" />
      </linearGradient>
    </defs>
    <path
      d="M7 35C3 25 6 11 30 3c3 14-1 27-15 31-3 .9-5.6 1.4-8 1z"
      fill="url(#wadih-leaf)"
      opacity=".95"
    />
    <path
      d="M8 34c4-9 10-17 19-26M14 25.5l-5-1.2M17.5 21l-2-6M21 16.5l5 .5M12.5 29l6 .2"
      fill="none"
      stroke="#0b1c16"
      strokeWidth="1.3"
      strokeLinecap="round"
      opacity=".7"
    />
  </svg>
);
