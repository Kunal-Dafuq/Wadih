import { useState, type FormEvent } from 'react';
import { api } from '../lib/api';
import { useAction } from '../lib/useAsync';
import {
  INHERITANCE_PATTERNS,
  SCREENING_INTERPRETATIONS,
  type InheritancePattern,
  type RiskAssessment,
  type ScreeningInterpretation,
} from '../lib/types';
import { RiskResult } from './components/RiskResult';
import { carrierLabel, inheritanceLabel } from './labels';
import { Button, ErrorNote, Field, PageHeader, Panel } from './ui';

/**
 * Educational "what if" tool backed by POST /api/v1/risk/assess. Nothing is
 * stored and no personal record is used: the backend computes the result from
 * the structured inputs below.
 */
export function ExplorePage({ readOnly }: { readOnly?: boolean }) {
  const [conditionName, setConditionName] = useState('Beta Thalassemia');
  const [conditionCode, setConditionCode] = useState('HBB_BETA_THAL');
  const [gene, setGene] = useState('HBB');
  const [pattern, setPattern] = useState<InheritancePattern>('AUTOSOMAL_RECESSIVE');
  const [p1, setP1] = useState<ScreeningInterpretation>('CARRIER_DETECTED');
  const [p2, setP2] = useState<ScreeningInterpretation | ''>('CARRIER_DETECTED');
  const [result, setResult] = useState<RiskAssessment | null>(null);

  const action = useAction(() =>
    api.assessScenario({
      condition_code: conditionCode.trim(),
      condition_name: conditionName.trim(),
      gene_symbol: gene.trim() || null,
      inheritance_pattern: pattern,
      partner_1_finding: p1,
      partner_2_finding: p2 || null,
    }),
  );

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const r = await action.run();
    setResult(r ?? null);
  };

  return (
    <>
      <PageHeader eyebrow="Educational tool" title={<>Scenario <em>explorer.</em></>}>
        See how the deterministic engine handles different combinations of findings. This does not use or change your
        records, and results are illustrations only.
      </PageHeader>
      <div className="split">
        <Panel title="Scenario">
          <form className="share-form" onSubmit={submit}>
            <div className="field-row">
              <Field label="Condition">
                <input required value={conditionName} onChange={(e) => setConditionName(e.target.value)} />
              </Field>
              <Field label="Gene">
                <input value={gene} onChange={(e) => setGene(e.target.value)} />
              </Field>
            </div>
            <Field label="Condition code">
              <input required value={conditionCode} onChange={(e) => setConditionCode(e.target.value)} />
            </Field>
            <Field label="Inheritance pattern">
              <select value={pattern} onChange={(e) => setPattern(e.target.value as InheritancePattern)}>
                {INHERITANCE_PATTERNS.map((p) => (
                  <option key={p} value={p}>
                    {inheritanceLabel(p)}
                  </option>
                ))}
              </select>
            </Field>
            <div className="field-row">
              <Field label="Partner 1 finding">
                <select value={p1} onChange={(e) => setP1(e.target.value as ScreeningInterpretation)}>
                  {SCREENING_INTERPRETATIONS.map((s) => (
                    <option key={s} value={s}>
                      {carrierLabel(s)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Partner 2 finding">
                <select value={p2} onChange={(e) => setP2(e.target.value as ScreeningInterpretation | '')}>
                  <option value="">Not tested / not linked</option>
                  {SCREENING_INTERPRETATIONS.map((s) => (
                    <option key={s} value={s}>
                      {carrierLabel(s)}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {action.error && <ErrorNote error={action.error} />}
            <Button type="submit" pending={action.pending} disabled={!conditionName.trim() || !conditionCode.trim()}>
              Run scenario
            </Button>
          </form>
        </Panel>
        <div>
          {result ? (
            <RiskResult assessment={result} readOnly={readOnly} />
          ) : (
            <Panel>
              <p className="muted">Choose findings and run the scenario to see how the engine responds.</p>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
