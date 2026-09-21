/**
 * Mistral Small 4 — one point, made three times.
 *
 * This replaced the ontology-of-memory card.
 *
 * ── The point ───────────────────────────────────────────────────────────
 *
 * The exact model in this talk is one anyone can pull and run. Not a
 * hosted endpoint, not a preview, not a partner build: the string in our
 * launch line is the string you would type.
 *
 * ── It is argued by absence, and the absences are checkable ─────────────
 *
 * All three are facts about scripts/launch_sglang.sh, and each is a thing
 * that ISN'T there:
 *
 *   NO TOKEN          no HF_TOKEN, no login, no credential anywhere in the
 *                     launch path. The script names the model and runs.
 *   NO --quantization  the checkpoint arrives FP8 and is served FP8. There
 *                     is no calibration pass and no conversion step.
 *   --tp 1            one GPU. The script's own line: "one H200/B200 holds
 *                     the FP8 weights at ~113 GB".
 *
 * Showing how little there is beats asserting that it is easy.
 *
 * ── What is NOT sourced here, and is therefore a caption ────────────────
 *
 * That this one checkpoint replaced three — Codestral for code, Magistral
 * for reasoning, a Small/Large for instruction — is Mistral's product
 * history, not a fact in this repo. What IS in the repo is their own pixel
 * icons for all four, vendored with provenance in public/brand/SOURCES.md.
 * So the merge is one dim caption under the hero rather than a diagram
 * claiming to be evidence.
 *
 * Likewise "open weights": the repo proves you can pull them with no
 * credential. It does not say what the licence permits, so neither does
 * the card.
 *
 * Everything in the third panel is this run's own, off ATTEMPT_DONE.
 */
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { BRANDS, NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import type { SlideProps } from './types'
import type { RunEvent } from '@/lib/types'

const ACCENT = BRANDS.mistral.accent

/**
 * NOT A FALLBACK MODEL STRING. There used to be one here, and it was wrong
 * in kind: a card whose whole argument is "the string in our launch line is
 * the string you would type" must not type a string the run did not record.
 * A summary rebuilt from the event log after a run was stopped carries
 * `model: ""`, and on swarm-1789998106 it does.
 */
const NOT_RECORDED = '(not recorded in this run)'

/**
 * The checkpoint this run served, or the fallback.
 *
 * `metrics.model` is not always a model: a run that could not read it back
 * writes the EMPTY STRING, and `?? FALLBACK` does not catch that — the field
 * is present, it is just blank. (Its neighbour `gpu` writes the literal
 * `(not recorded)` in the same situation.) The panel rendered a blank box
 * where the identifier should be until this checked for an org/name pair
 * rather than for null.
 */
const modelPath = (raw: string | null | undefined): string | null => {
  const v = (raw ?? '').trim()
  return v.includes('/') ? v : null
}

/** From the launch script's own note on why TP defaults to 1. */
const WEIGHTS_GB = 113

/**
 * The three it replaced, by role. Mistral's own icons, already vendored —
 * see the header on why these are a caption and not a diagram.
 */
const REPLACED = [
  { role: 'code', name: 'Codestral', logo: '/brand/mistral-model-codestral.svg' },
  {
    role: 'reasoning',
    name: 'Magistral',
    logo: '/brand/mistral-model-magistral.svg',
  },
  { role: 'instruct', name: 'Large', logo: '/brand/mistral-model-large.svg' },
]

/** The three absences, in the order they reveal. */
const ABSENCES = [
  { head: 'no token', sub: 'no login, no credential in the launch path' },
  { head: 'no --quantization', sub: 'FP8 as shipped, served as shipped' },
  { head: '--tp 1', sub: `one GPU · ${WEIGHTS_GB} GB of weights` },
]

const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'
const FADE = 500
/** Three beats, then a hold with all three lit. */
const BEAT = 1500
const HOLD = 5000

function Panel({
  label,
  children,
  grow,
}: {
  label: string
  children: ReactNode
  grow: number
}) {
  return (
    <section
      className="flex min-w-0 flex-col"
      style={{
        flex: `${grow} 1 0`,
        background: alpha(NEO4J.periwinkle, 0.07),
        border: `2px solid ${alpha(NEO4J.periwinkle, 0.3)}`,
        borderRadius: 10,
        padding: '18px 24px',
      }}
    >
      <h3
        className="font-pixel shrink-0"
        style={{
          fontSize: pt(24),
          color: 'hsl(var(--muted))',
          letterSpacing: '0.14em',
          marginBottom: 14,
        }}
      >
        {label}
      </h3>
      <div className="flex min-h-0 flex-1 flex-col justify-center">{children}</div>
    </section>
  )
}

export function ModelSlide({ onStage }: SlideProps) {
  const { metrics, events } = useRunFeed()
  /** -1 is the hold: every absence lit at once. */
  const [beat, setBeat] = useState(-1)

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still) {
      setBeat(-1)
      return
    }
    let timer: number
    const step = (n: number) => {
      setBeat(n)
      timer = window.setTimeout(
        () => step(n < 0 ? 0 : n + 1 > 2 ? -1 : n + 1),
        n < 0 ? HOLD : BEAT,
      )
    }
    step(0)
    return () => window.clearTimeout(timer)
  }, [onStage])

  const done = (events as RunEvent[]).filter((e) => e.type === 'ATTEMPT_DONE')
  const tools: Record<string, number> = {}
  for (const e of done) {
    for (const [k, v] of Object.entries(
      (e.tools ?? {}) as Record<string, number>,
    )) {
      tools[k] = (tools[k] ?? 0) + v
    }
  }
  const calls = Object.values(tools).reduce((n, v) => n + v, 0)
  const written = (tools.edit ?? 0) + (tools.write_file ?? 0)
  const turns = done.reduce((n, e) => n + (e.turns_used ?? 0), 0)
  const arms = new Set(done.map((e) => e.swarm).filter(Boolean)).size

  const identifier = modelPath(metrics?.model)
  const [org, repo] = (identifier ?? '').split('/')

  const FIGURES: [string, string][] = [
    [calls.toLocaleString(), 'tool calls'],
    [String(Object.keys(tools).length), 'distinct tools'],
    [written.toLocaleString(), 'files written'],
    [turns.toLocaleString(), 'turns'],
    [String(done.length), 'graded attempts'],
  ]

  return (
    <SlideChrome
      title="Mistral Small 4"
      accent={ACCENT}
      mark="/brand/mistral-model-small.svg"
      badge="119B · FP8 · one GPU"
      focused={onStage}
      footer={
        <span>
          the three absences are facts about scripts/launch_sglang.sh · the figures
          are this run's own, off each ATTEMPT_DONE · icons are Mistral's,
          provenance in public/brand/SOURCES.md
        </span>
      }
    >
      <div className="flex h-full" style={{ gap: 20 }}>
        <Panel label="WHAT IT IS" grow={26}>
          <div className="flex flex-col items-center">
            <img
              src="/brand/mistral-model-small.svg"
              alt=""
              aria-hidden
              style={{
                width: pt(120),
                height: 'auto',
                imageRendering: 'pixelated',
              }}
            />
            <div
              className="heading-solid"
              style={{ fontSize: pt(40), color: ACCENT, marginTop: 14 }}
            >
              Small 4
            </div>
            <div
              className="font-pixel"
              style={{
                fontSize: pt(24),
                color: 'hsl(var(--muted-fg))',
                marginTop: 6,
                textAlign: 'center',
              }}
            >
              119B · FP8 as shipped
            </div>
          </div>

          {/* The merge, as a caption. See the header: product history, not a
              fact in this repo, so it is not drawn as evidence. */}
          <div style={{ marginTop: 26 }}>
            <div
              className="font-pixel"
              style={{
                fontSize: pt(22),
                color: 'hsl(var(--muted))',
                textAlign: 'center',
              }}
            >
              one checkpoint where there were three
            </div>
            <div
              className="flex items-start justify-center"
              style={{ gap: 18, marginTop: 12 }}
            >
              {REPLACED.map((m) => (
                <div key={m.name} style={{ textAlign: 'center' }}>
                  <img
                    src={m.logo}
                    alt=""
                    aria-hidden
                    style={{
                      width: pt(56),
                      height: 'auto',
                      imageRendering: 'pixelated',
                      // The icon is dimmed; its caption is not. Fading the
                      // whole group took the label to 1.23:1.
                      opacity: 0.5,
                    }}
                  />
                  <div
                    className="font-pixel"
                    style={{ fontSize: pt(20), color: 'hsl(var(--muted))' }}
                  >
                    {m.role}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Panel label="WHY IT'S GOOD" grow={40}>
          <div
            className="heading-solid"
            style={{ fontSize: pt(52), color: ACCENT, letterSpacing: '0.02em' }}
          >
            Open weights
          </div>

          {/* The identifier, set large: the string in our launch line is the
              string anyone else would type. */}
          <div
            className="font-pixel"
            style={{
              marginTop: 16,
              padding: '14px 18px',
              borderRadius: 8,
              background: alpha(NEO4J.periwinkle, 0.12),
              border: `2px solid ${alpha(NEO4J.periwinkle, 0.35)}`,
              overflowWrap: 'anywhere',
            }}
          >
            {identifier ? (
              <>
                <span style={{ fontSize: pt(28), color: 'hsl(var(--muted))' }}>
                  {`${org}/`}
                </span>
                <span style={{ fontSize: pt(34), color: alpha(NEO4J.cream, 0.95) }}>
                  {repo}
                </span>
              </>
            ) : (
              <span style={{ fontSize: pt(28), color: 'hsl(var(--muted))' }}>
                {NOT_RECORDED}
              </span>
            )}
          </div>

          <ul style={{ marginTop: 20 }}>
            {ABSENCES.map((a, i) => {
              const lit = beat < 0 || beat === i
              return (
                <li
                  key={a.head}
                  style={{
                    marginBottom: 12,
                    // Not 0.32: unlit measured 1.75:1. The beat is a
                    // change in emphasis, not a change in legibility.
                    opacity: lit ? 1 : 0.6,
                    transition: `opacity ${FADE}ms ${EASE}`,
                  }}
                >
                  <div
                    className="font-pixel"
                    style={{ fontSize: pt(32), color: ACCENT }}
                  >
                    {a.head}
                  </div>
                  <div
                    className="font-pixel"
                    style={{ fontSize: pt(23), color: 'hsl(var(--muted-fg))' }}
                  >
                    {a.sub}
                  </div>
                </li>
              )
            })}
          </ul>

          <p
            className="font-pixel"
            style={{
              fontSize: pt(23),
              color: alpha(NEO4J.cream, 0.8),
              marginTop: 8,
            }}
          >
            Six flags, and you are serving it too.
          </p>
        </Panel>

        <Panel label="HOW WE USE IT" grow={34}>
          {done.length === 0 ? (
            <p
              className="font-pixel"
              style={{ fontSize: pt(26), color: 'hsl(var(--muted))' }}
            >
              Nothing graded yet in this run. The figures here are counted from each
              ATTEMPT_DONE, and the first one lands a few minutes in.
            </p>
          ) : (
            <div>
              {FIGURES.map(([n, of]) => (
                <div
                  key={of}
                  className="flex items-baseline"
                  style={{ gap: 14, marginBottom: 10 }}
                >
                  <span
                    className="heading-solid"
                    style={{
                      fontSize: pt(38),
                      color: ACCENT,
                      minWidth: pt(120),
                      textAlign: 'right',
                    }}
                  >
                    {n}
                  </span>
                  <span
                    className="font-pixel"
                    style={{ fontSize: pt(24), color: 'hsl(var(--muted-fg))' }}
                  >
                    {of}
                  </span>
                </div>
              ))}
              <p
                className="font-pixel"
                style={{
                  fontSize: pt(23),
                  color: 'hsl(var(--muted))',
                  marginTop: 18,
                }}
              >
                {arms === 2
                  ? 'Both arms, one server, one GPU. Live, this run.'
                  : 'One server, one GPU. Live, this run.'}
              </p>
            </div>
          )}
        </Panel>
      </div>
    </SlideChrome>
  )
}
