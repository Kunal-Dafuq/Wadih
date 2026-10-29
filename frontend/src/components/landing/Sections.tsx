import { Logo } from './icons';

const STEPS = [
  {
    n: '01',
    title: 'Understand your results',
    body: 'Screening findings are explained in plain language — what a carrier result means, how inheritance works, and what it does not tell you.',
  },
  {
    n: '02',
    title: 'Decide what is shared',
    body: 'Granular consent controls let you choose who sees what, for how long, and change your mind at any time.',
  },
  {
    n: '03',
    title: 'Reach the right counsel',
    body: 'Check your understanding, then find a route to appropriate genetic counselling and referral when you are ready.',
  },
];

const PRINCIPLES = [
  ['Educational, not diagnostic', 'Wadih explains and contextualises. It never replaces a clinician or a genetic counsellor.'],
  ['Private by default', 'Nothing is shared without an explicit, revocable choice from you.'],
  ['Clinically bounded', 'Information stays within what screening can and cannot say — no speculation, no alarm.'],
];

const USE_CASES = [
  ['Planning a pregnancy', 'Make sense of reproductive carrier screening before decisions need to be made.'],
  ['After a carrier result', 'Understand what a result means for you, a partner, and future children.'],
  ['Talking with family', 'Decide what to share with relatives, and how to start the conversation.'],
];

const RESOURCES = [
  'How autosomal recessive inheritance works',
  'Carrier screening, explained',
  'Questions to bring to a genetic counsellor',
  'Your rights over genetic information',
];

export function Sections() {
  return (
    <main className="sections">
      <section id="how-it-works" className="section" aria-labelledby="how-title">
        <header className="section-head">
          <p className="eyebrow">How it works</p>
          <h2 id="how-title" className="section-title">
            Three calm steps, <em>at your pace.</em>
          </h2>
        </header>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.n}>
              <span className="step-n">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="approach" className="section section-split" aria-labelledby="approach-title">
        <header className="section-head">
          <p className="eyebrow">Our approach</p>
          <h2 id="approach-title" className="section-title">
            Clarity first. <em>Consent always.</em>
          </h2>
        </header>
        <dl className="principles">
          {PRINCIPLES.map(([t, d]) => (
            <div key={t}>
              <dt>{t}</dt>
              <dd>{d}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section id="use-cases" className="section" aria-labelledby="use-title">
        <header className="section-head">
          <p className="eyebrow">Use cases</p>
          <h2 id="use-title" className="section-title">
            For the moments <em>that matter.</em>
          </h2>
        </header>
        <ul className="cases">
          {USE_CASES.map(([t, d]) => (
            <li key={t}>
              <h3>{t}</h3>
              <p>{d}</p>
            </li>
          ))}
        </ul>
      </section>

      <section id="resources" className="section section-split" aria-labelledby="res-title">
        <header className="section-head">
          <p className="eyebrow">Resources</p>
          <h2 id="res-title" className="section-title">
            A learning library, <em>in preparation.</em>
          </h2>
        </header>
        <ul className="resources">
          {RESOURCES.map((r) => (
            <li key={r}>
              <span>{r}</span>
              <span className="soon">Coming soon</span>
            </li>
          ))}
        </ul>
      </section>

      <section id="start" className="section closing" aria-labelledby="start-title">
        <h2 id="start-title" className="closing-title">
          Begin with <em>understanding.</em>
        </h2>
        <p>
          Wadih is an educational demonstration platform. It uses synthetic screening data and does not provide
          diagnosis or medical advice.
        </p>
        <a href="#how-it-works" className="btn btn-ghost">
          Read how it works
        </a>
      </section>

      <footer className="site-footer">
        <span className="brand brand-sm">
          <Logo width={22} height={24} />
          <span>Wadih</span>
        </span>
        <span>Privacy-first genetic screening education.</span>
      </footer>
    </main>
  );
}
