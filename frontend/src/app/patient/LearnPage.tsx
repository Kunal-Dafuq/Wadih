import { useState } from 'react';
import { api } from '../../lib/api';
import { Link } from '../../lib/router';
import { useAction, useAsync } from '../../lib/useAsync';
import type { CaseExplanation, KnowledgeCheckResult } from '../../lib/types';
import { carrierLabel, carrierTone, formatDate, inheritanceLabel } from '../labels';
import { Badge, Banner, Button, ErrorNote, Loading, PageHeader, Panel } from '../ui';

/** Strips the "1. " numbering the seeded takeaways carry, since the list is already ordered. */
const stripNumber = (s: string) => s.replace(/^\s*\d+\.\s*/, '');

function TeachBack({ caseId, explanation }: { caseId: number; explanation: CaseExplanation }) {
  const questions = explanation.teach_back_questions;
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<KnowledgeCheckResult | null>(null);
  const submit = useAction(() =>
    api.submitKnowledgeCheck(caseId, {
      answers: questions.map((q) => ({ question_id: q.question_id, selected_option_id: answers[q.question_id] })),
    }),
  );

  const answered = questions.filter((q) => answers[q.question_id]).length;
  const complete = answered === questions.length;
  const evalFor = (qid: number) => result?.evaluations.find((e) => e.question_id === qid);

  const onSubmit = async () => {
    const r = await submit.run();
    if (r) setResult(r);
  };
  const retry = () => {
    setResult(null);
    setAnswers({});
  };

  if (!questions.length) {
    return (
      <Panel title="Check your understanding">
        <p className="muted">No comprehension questions are available for this result yet.</p>
      </Panel>
    );
  }

  return (
    <Panel
      title="Check your understanding"
      aside={
        result ? (
          <Badge tone={result.passed ? 'teal' : 'warn'}>{result.passed ? 'Understood' : 'Needs review'}</Badge>
        ) : (
          <span className="muted small">
            {answered} of {questions.length} answered
          </span>
        )
      }
      className="teach"
    >
      {result && (
        <Banner
          tone={result.passed ? 'teal' : 'amber'}
          title={`${result.score} of ${result.total_questions} correct`}
          actions={
            <>
              <Button variant="ghost" size="sm" onClick={retry}>
                Try again
              </Button>
              {!result.passed && (
                <Link to="/app/counselling" className="btn btn-primary btn-sm">
                  Ask a counsellor
                </Link>
              )}
            </>
          }
        >
          <p>{result.feedback_message}</p>
          <p className="muted small">
            Attempt {result.attempt_count} · {formatDate(result.completed_at)}
          </p>
        </Banner>
      )}

      <ol className="questions">
        {questions.map((q, qi) => {
          const ev = evalFor(q.question_id);
          return (
            <li key={q.question_id} className="question" data-state={ev ? (ev.is_correct ? 'correct' : 'incorrect') : undefined}>
              <fieldset disabled={!!result || submit.pending}>
                <legend>
                  <span className="q-num">{qi + 1}</span>
                  {q.prompt}
                </legend>
                <div className="options">
                  {q.options.map((o) => {
                    const checked = answers[q.question_id] === o.option_id;
                    return (
                      <label key={o.option_id} className="option" data-checked={checked || undefined}>
                        <input
                          type="radio"
                          name={`q-${q.question_id}`}
                          value={o.option_id}
                          checked={checked}
                          onChange={() => setAnswers((a) => ({ ...a, [q.question_id]: o.option_id }))}
                        />
                        <span>{o.text}</span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
              {ev && (
                <p className={`q-feedback ${ev.is_correct ? 'is-correct' : 'is-incorrect'}`}>
                  <strong>{ev.is_correct ? 'Correct.' : 'Not quite.'}</strong> {ev.explanation}
                </p>
              )}
            </li>
          );
        })}
      </ol>

      {submit.error && <ErrorNote error={submit.error} />}
      {!result && (
        <div className="teach-foot">
          <Button onClick={onSubmit} disabled={!complete} pending={submit.pending}>
            Submit answers
          </Button>
          {!complete && <span className="muted small">Answer every question to submit.</span>}
        </div>
      )}
    </Panel>
  );
}

export function LearnPage({ caseId }: { caseId: number }) {
  const exp = useAsync(() => api.getExplanation(caseId), [caseId]);

  return (
    <>
      <Link to={`/app/results/${caseId}`} className="back-link">← Back to result</Link>
      {exp.status === 'loading' && <Loading label="Loading explanation" />}
      {exp.status === 'error' && <ErrorNote error={exp.error} onRetry={exp.reload} />}
      {exp.status === 'success' && (
        <>
          <PageHeader eyebrow={exp.data.case_code} title={exp.data.title}>
            Approved by {exp.data.approved_by_role.replace(/_/g, ' ').toLowerCase()} · content v{exp.data.content_version}
          </PageHeader>

          <div className="split">
            <div className="stack">
              <Panel title="Overview">
                {exp.data.overview_body.split(/\n{2,}/).map((p, i) => (
                  <p key={i} className="prose-p">
                    {p}
                  </p>
                ))}
              </Panel>
              <TeachBack caseId={caseId} explanation={exp.data} />
            </div>

            <aside className="stack">
              <Panel title="Key takeaways">
                <ol className="takeaways">
                  {exp.data.key_takeaways.map((t) => (
                    <li key={t}>{stripNumber(t)}</li>
                  ))}
                </ol>
              </Panel>
              <Panel title="Your conditions">
                <ul className="guide-list">
                  {exp.data.condition_guides.map((g) => (
                    <li key={g.condition_code}>
                      <div className="guide-head">
                        <strong>{g.condition_name}</strong>
                        <Badge tone={carrierTone(g.carrier_state)}>{carrierLabel(g.carrier_state)}</Badge>
                      </div>
                      <p className="muted small">{inheritanceLabel(g.inheritance_mode)}</p>
                      <p>{g.educational_summary}</p>
                    </li>
                  ))}
                </ul>
              </Panel>
              <p className="muted small">{exp.data.limitations_disclaimer}</p>
            </aside>
          </div>
        </>
      )}
    </>
  );
}
