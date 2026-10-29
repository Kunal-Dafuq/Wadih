import { useState, type FormEvent } from 'react';
import { ApiError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Link, navigate } from '../lib/router';
import { Logo } from '../components/landing/icons';
import { Button, ErrorNote, Field } from './ui';

// Safe synthetic demonstration personas supported by POST /api/v1/auth/demo-session.
const DEMO_PERSONAS = [
  { persona: 'patient_a', label: 'Patient A (Carrier)' },
  { persona: 'patient_b', label: 'Patient B (Partner)' },
  { persona: 'counsellor', label: 'Dr. Chen (Counsellor)' },
];

export function SignIn() {
  const { login, demoLogin } = useAuth();
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

  const launchDemo = async (persona: string) => {
    setPending(true);
    setError(null);
    try {
      await demoLogin(persona);
      navigate('/app', { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'INTERNAL_ERROR', 'Demo sign-in failed.'));
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
          <span className="field-hint">Instant demo access (least-privilege synthetic personas):</span>
          <div className="chip-row">
            {DEMO_PERSONAS.map((a) => (
              <button
                type="button"
                key={a.persona}
                className="chip"
                disabled={pending}
                onClick={() => launchDemo(a.persona)}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>
      </form>
    </main>
  );
}
