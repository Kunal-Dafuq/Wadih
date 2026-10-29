import { useEffect } from 'react';
import { AppRoutes } from './app/AppRoutes';
import { SignIn } from './app/SignIn';
import { Hero } from './components/landing/Hero';
import { Sections } from './components/landing/Sections';
import { SiteHeader } from './components/landing/SiteHeader';
import { AuthProvider, useAuth } from './lib/auth';
import { navigate, usePath } from './lib/router';

function Landing() {
  return (
    <>
      <a href="#how-it-works" className="skip-link">
        Skip to content
      </a>
      <SiteHeader />
      <Hero />
      <Sections />
    </>
  );
}

function SignInRoute() {
  const { status } = useAuth();
  useEffect(() => {
    if (status === 'signed-in') navigate('/app', { replace: true });
  }, [status]);
  return status === 'signed-in' ? null : <SignIn />;
}

function Routes() {
  const path = usePath();
  if (path === '/sign-in') return <SignInRoute />;
  if (path === '/app' || path.startsWith('/app/')) return <AppRoutes path={path} />;
  return <Landing />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes />
    </AuthProvider>
  );
}
