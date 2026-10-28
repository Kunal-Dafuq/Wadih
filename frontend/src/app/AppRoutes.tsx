import { useEffect, type ReactNode } from 'react';
import { useAuth } from '../lib/auth';
import { Link, match, navigate } from '../lib/router';
import { AppShell } from './AppShell';
import { ExplorePage } from './ExplorePage';
import { ProvenancePage, ReferralDetailPage, ReferralsPage } from './counsellor/CounsellorPages';
import { CaseDetailPage } from './patient/CaseDetailPage';
import { CounsellingPage } from './patient/CounsellingPage';
import { LearnPage } from './patient/LearnPage';
import { ResultsPage } from './patient/ResultsPage';
import { SharedCasePage } from './patient/SharedCasePage';
import { SharingPage } from './patient/SharingPage';
import { Empty, Loading } from './ui';

function Redirect({ to }: { to: string }) {
  useEffect(() => navigate(to, { replace: true }), [to]);
  return null;
}

const id = (v: string) => (/^\d+$/.test(v) ? Number(v) : NaN);

function patientRoute(path: string): ReactNode {
  if (path === '/app' || path === '/app/') return <Redirect to="/app/results" />;
  if (path === '/app/results') return <ResultsPage />;
  let m = match('/app/results/:caseId', path);
  if (m && !Number.isNaN(id(m.caseId))) return <CaseDetailPage key={m.caseId} caseId={id(m.caseId)} />;
  m = match('/app/results/:caseId/learn', path);
  if (m && !Number.isNaN(id(m.caseId))) return <LearnPage key={m.caseId} caseId={id(m.caseId)} />;
  if (path === '/app/sharing') return <SharingPage />;
  m = match('/app/shared/:caseId', path);
  if (m && !Number.isNaN(id(m.caseId))) return <SharedCasePage key={m.caseId} caseId={id(m.caseId)} />;
  if (path === '/app/counselling') return <CounsellingPage />;
  if (path === '/app/explore') return <ExplorePage />;
  return null;
}

function counsellorRoute(path: string): ReactNode {
  if (path === '/app' || path === '/app/') return <Redirect to="/app/referrals" />;
  if (path === '/app/referrals') return <ReferralsPage />;
  const m = match('/app/referrals/:referralId', path);
  if (m && !Number.isNaN(id(m.referralId))) return <ReferralDetailPage key={m.referralId} referralId={id(m.referralId)} />;
  if (path === '/app/provenance') return <ProvenancePage />;
  if (path === '/app/explore') return <ExplorePage readOnly />;
  return null;
}

/** Authenticated application under /app. */
export function AppRoutes({ path }: { path: string }) {
  const { status, user } = useAuth();

  if (status === 'restoring') return <Loading label="Restoring your session" />;
  if (status === 'signed-out' || !user) return <Redirect to="/sign-in" />;

  const page = user.role === 'counsellor' ? counsellorRoute(path) : patientRoute(path);
  return (
    <AppShell path={path}>
      {page ?? (
        <Empty title="Page not found">
          <Link to="/app" className="text-link">
            Go to your dashboard
          </Link>
        </Empty>
      )}
    </AppShell>
  );
}
