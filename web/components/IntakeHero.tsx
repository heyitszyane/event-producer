import { type FormEvent } from 'react'

const EXAMPLE_BRIEF = [
  'Need a 100-pax AI founder networking night in Singapore on 2026-07-10.',
  'Budget is around 10k SGD. Want it to feel premium but not flashy,',
  'light F&B, a short fireside chat, and a few structured networking prompts.',
  'No full conference setup. Audience is founders, investors, and AI builders.',
  'Need this to be credible, efficient, and not overproduced.',
].join(' ')

interface IntakeHeroProps {
  brief: string
  onBriefChange: (v: string) => void
  onSubmit: (e: FormEvent) => void
  loading: boolean
  hasRun: boolean
}

export default function IntakeHero({
  brief,
  onBriefChange,
  onSubmit,
  loading,
  hasRun,
}: IntakeHeroProps) {
  return (
    <section
      className="card intake-hero"
      id="intake"
      aria-labelledby="intake-heading"
    >
      <div className="card__header">
        <h2 id="intake-heading">Brief Intake</h2>
        <span className="badge badge--info">Casefile</span>
      </div>

      <form onSubmit={onSubmit} className="intake-hero__form">
        <textarea
          className="input intake-hero__textarea"
          value={brief}
          onChange={(e) => onBriefChange(e.target.value)}
          placeholder="Add event notes, goals, constraints, and context."
          rows={5}
          aria-label="Event brief"
        />
        <div className="intake-hero__actions">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => onBriefChange(EXAMPLE_BRIEF)}
            disabled={loading}
            aria-label="Load an example brief"
          >
            Try example
          </button>
          <button
            type="submit"
            disabled={loading || !brief.trim()}
            className={`btn btn--primary ${loading ? 'loading-pulse' : ''}`}
          >
            {loading
              ? 'Saving...'
              : hasRun
              ? 'Save casefile and generate first pass'
              : 'Save casefile and generate first pass'}
          </button>
        </div>
      </form>
    </section>
  )
}
