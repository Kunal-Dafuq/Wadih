import { useState, type FormEvent } from 'react';
import { ApiError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Link, navigate } from '../lib/router';
import { Logo } from '../components/landing/icons';
import { Button, ErrorNote, Field } from './ui';

// Accounts created by the backend seed script (backend/app/seed/seed_demo.py).
const DEMO_ACCOUNTS = [
  { email: 'patient.a@wadih.demo', label: 'Patient A' },
  { email: 'patient.b@wadih.demo', label: 'Patient B' },
  { email: 'counsellor@wadih.demo', label: 'Counsellor' },
];

export function SignIn() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate('/app', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'INTERNAL_ERROR', 'Sign in failed.'));
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="auth-page">
      <div className="auth-glow" aria-hidden="true" />
      <Link to="/" className="brand auth-brand" aria-label="Wadih home">
        <Logo />
        <span>Wadih</span>
      </Link>
      <form className="auth-card" onSubmit={submit} noValidate>
        <p className="eyebrow">Demonstration access</p>
        <h1 className="auth-title">
          Sign in to <em>Wadih.</em>
        </h1>
        <p className="auth-lede">Use a demo account. All screening data is synthetic.</p>

        {error && <ErrorNote error={error} />}

        <Field label="Email">
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Password">
          <input
            type="password"
            autoComplete="current-password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Button type="submit" pending={pending} disabled={!email || password.length < 6}>
          Sign in
        </Button>

        <div className="demo-accounts">
          <span className="field-hint">Demo accounts (password is in the backend README):</span>
          <div className="chip-row">
            {DEMO_ACCOUNTS.map((a) => (
              <button type="button" key={a.email} className="chip" onClick={() => setEmail(a.email)}>
                {a.label}
              </button>
            ))}
          </div>
        </div>
      </form>
    </main>
  );
}
