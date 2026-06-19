import { useState } from 'react'
import { api } from '../api/client'
import { Card } from './ui'
import { useToast } from '../context/ToastContext'

const SUGGESTIONS = [
  'Which month had the worst downtime, and why?',
  'How has fuel efficiency trended over the last 6 months?',
  'Compare production this month to the same month last year.',
  'What is driving our re-pulp / reject rate?',
]

// "Ask the plant data" — sends a plain-English question to the AI assistant,
// which answers from the plant's own aggregated history. Renders nothing unless
// the parent says AI is enabled.
export default function AskAI() {
  const toast = useToast()
  const [q, setQ] = useState('')
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)

  const ask = async (question) => {
    const text = (question ?? q).trim()
    if (text.length < 3 || busy) return
    setQ(text); setBusy(true); setAnswer('')
    try {
      const r = await api.aiAsk(text)
      setAnswer(r.answer)
    } catch (e) {
      toast.err(e.message || 'AI request failed')
    } finally { setBusy(false) }
  }

  return (
    <Card title="Ask the plant data" sub="Plain-English questions answered from your production history (powered by Claude)">
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <textarea
          className="range-in"
          style={{ flex: 1, minWidth: 240, minHeight: 64, resize: 'vertical', fontFamily: 'inherit' }}
          placeholder="e.g. Which month had the highest output, and how did fuel use compare?"
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) ask() }}
        />
        <button className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-start' }} disabled={busy || q.trim().length < 3} onClick={() => ask()}>
          {busy ? 'Thinking…' : 'Ask'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
        {SUGGESTIONS.map(s => (
          <button key={s} className="btn btn-ghost btn-sm" disabled={busy} onClick={() => ask(s)} style={{ fontSize: 12 }}>
            {s}
          </button>
        ))}
      </div>

      {answer && <div className="ai-output">{answer}</div>}
      <div className="rep-hint" style={{ marginTop: 8 }}>
        Answers are generated from aggregated monthly figures and may need a sense-check against source records.
      </div>
    </Card>
  )
}
