import { useState, type ReactNode } from 'react';
import { useAuth } from '../lib/auth';
import { Link, navigate } from '../lib/router';
import { Logo } from '../components/landing/icons';

const PATIENT_NAV = [
  { to: '/app/results', label: 'Results' },
  { to: '/app/sharing', label: 'Sharing' },
  { to: '/app/counselling', label: 'Counselling' },
  { to: '/app/explore', label: 'Scenario explorer' },
];

const COUNSELLOR_NAV = [
  { to: '/app/referrals', label: 'Referrals' },
  { to: '/app/provenance', label: 'Residual risk records' },
  { to: '/app/explore', label: 'Scenario explorer' },
];

export function AppShell({ path, children }: { path: string; children: ReactNode }) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const nav = user?.role === 'counsellor' ? COUNSELLOR_NAV : PATIENT_NAV;

  const signOut = async () => {
    await logout();
    navigate('/sign-in', { replace: true });
  };

  return (
    <div className="app">
      <header className="app-header" data-open={menuOpen}>
        <Link to="/app" className="brand brand-app" aria-label="Wadih app home">
          <Logo width={26} height={30} />
          <span>Wadih</span>
        </Link>
        <nav className="app-nav" aria-label="App">
          {nav.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              aria-current={path === n.to || path.startsWith(n.to + '/') ? 'page' : undefined}
              onClick={() => setMenuOpen(false)}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="app-user">
          <span className="app-user-name">
            {user?.display_name ?? user?.email}
            <small>{user?.role === 'counsellor' ? 'Genetic counsellor' : 'Participant'}</small>
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={signOut}>
            Sign out
          </button>
          <button
            type="button"
            className="menu-toggle app-menu-toggle"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span className="sr-only">{menuOpen ? 'Close menu' : 'Open menu'}</span>
            <span aria-hidden="true" />
            <span aria-hidden="true" />
          </button>
        </div>
      </header>
      <main className="app-main" id="app-main">
        {children}
      </main>
      <footer className="app-footer">
        Educational demonstration using synthetic data. Wadih does not provide diagnosis or medical advice.
      </footer>
    </div>
  );
}
