/**
 * The skill the agent actually wrote.
 *
 * Read off disk, verbatim, from whichever `skills/versions*` directory was
 * written most recently. This is the artefact the whole warm arm exists to
 * produce, and the one thing an audience can check for themselves: if the
 * procedure contains Pydantic API knowledge, the agent put it there — the
 * distillation prompt in `orchestrator/distill.py` contains no Pydantic API,
 * no import path and no validator name.
 *
 * Follows the live version as it is distilled. The header block is the AIP
 * frontmatter — spec URL, schema id, version, and the trace ids it was derived
 * from — which is the provenance that makes "derived from its own run" a claim
 * rather than an assertion.
 */
import { useEffect, useMemo, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'

interface SkillIndex {
  dir: string | null
  versions: { file: string; version: number; bytes: number }[]
}
interface SkillText extends SkillIndex {
  text: string
  version: number
  bytes: number
}

/** Roughly what the harness counts. Good enough to show the cap being felt. */
const approxTokens = (s: string) => Math.round(s.length / 4)

export function SkillSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  const [index, setIndex] = useState<SkillIndex>({ dir: null, versions: [] })
  const [doc, setDoc] = useState<SkillText | null>(null)

  // Re-read the index when a distillation lands; otherwise leave it alone.
  const distillations = useMemo(
    () => events.filter((e) => e.type === 'DISTILLED').length,
    [events],
  )

  useEffect(() => {
    void fetch('/api/skills')
      .then((r) => r.json())
      .then(setIndex)
      .catch(() => undefined)
  }, [distillations])

  const latest = index.versions[index.versions.length - 1]
  useEffect(() => {
    if (!latest) return
    void fetch(`/api/skills/${latest.version}`)
      .then((r) => r.json())
      .then(setDoc)
      .catch(() => undefined)
  }, [latest?.version])

  const { front, body } = useMemo(() => {
    const t = doc?.text ?? ''
    const m = /^---\n([\s\S]*?)\n---\n?/.exec(t)
    return m ? { front: m[1], body: t.slice(m[0].length) } : { front: '', body: t }
  }, [doc?.text])

  return (
    <SlideChrome
      title="The distilled skill"
      accent={NEO4J.marigold}
      badge={
        doc
          ? `v${doc.version} · ~${approxTokens(doc.text).toLocaleString('en-GB')} tok`
          : 'no skill on disk'
      }
      focused={onStage}
      footer={
        <span>
          {index.dir ?? 'skills/versions*'} · {index.versions.length} version(s) ·
          the distillation prompt contains no Pydantic API — anything here, the
          agent found
        </span>
      }
    >
      {!doc ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
        >
          no distilled skill yet
        </div>
      ) : (
        <div className="flex h-full flex-col" style={{ gap: 10 }}>
          <pre
            className="font-pixel shrink-0"
            style={{
              fontSize: 24,
              lineHeight: 1.3,
              color: NEO4J.lightPeriwinkle,
              background: alpha(NEO4J.periwinkle, 0.08),
              border: `1px solid ${alpha(NEO4J.periwinkle, 0.3)}`,
              borderRadius: 8,
              padding: '8px 12px',
              whiteSpace: 'pre-wrap',
              maxHeight: '32%',
              overflow: 'hidden',
            }}
          >
            {front}
          </pre>
          {/* The procedure itself. Clipped, not scrolled: a card that needs
              scrolling on stage is a card nobody reads. */}
          <pre
            className="font-pixel min-h-0 flex-1"
            style={{
              fontSize: 26,
              lineHeight: 1.32,
              color: NEO4J.cream,
              whiteSpace: 'pre-wrap',
              overflow: 'hidden',
              margin: 0,
            }}
          >
            {body}
          </pre>
        </div>
      )}
    </SlideChrome>
  )
}
