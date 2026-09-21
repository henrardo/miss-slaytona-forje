/**
 * Mistral Vibe, pointed at a GPU in the next rack.
 *
 * The claim is "a config file swap", so the card shows the file. It is the
 * real template — harness/vibe-config.template.toml, rendered per agent by
 * `render_config()` in orchestrator/vibe_agent.py — and its own comment
 * names the documented surface it uses: api_style="openai" plus
 * backend="generic" targets any OpenAI-compatible endpoint, which is what
 * SGLang's /v1/chat/completions is.
 *
 * ONE LINE MOVES. `api_base` alternates between Mistral's hosted endpoint
 * and the pod's local port while the rest of the block sits still, because
 * that is the entire argument: same file, same five keys, one value. Nothing
 * else on the card animates.
 *
 * The wire underneath is the path every token in this run took, and the
 * figures beside it are counted on that wire — the proxies at 8821 and 8822
 * ARE the `proxy_usage` counters the RadixAttention card reads. So "it ran
 * against a local GPU" is a measurement here, not a promise.
 */
import { useEffect, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import type { SlideProps } from './types'
import type { RunEvent } from '@/lib/types'
import mistralM from '@/wordmark/glyphs/mistral-M.svg?url'

const ACCENT = NEO4J.periwinkle

/** The two values `api_base` can hold. Only one of them is ever used here. */
const HOSTED = 'https://api.mistral.ai/v1'
const LOCAL = 'http://127.0.0.1:8821/v1'

/** The rest of the provider block, verbatim and unchanging. */
const BLOCK: [string, string][] = [
  ['name', '"sglang"'],
  ['api_style', '"openai"'],
  ['backend', '"generic"'],
]

const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'
const SWAP = 4200

const compact = (n: number): string =>
  n >= 1e6
    ? `${(n / 1e6).toFixed(1)} M`
    : n >= 1e3
      ? `${(n / 1e3).toFixed(0)} K`
      : String(n)

export function VibeSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  const [local, setLocal] = useState(true)

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!onStage || still) {
      setLocal(true)
      return
    }
    const id = window.setInterval(() => setLocal((v) => !v), SWAP)
    return () => window.clearInterval(id)
  }, [onStage])

  const done = (events as RunEvent[]).filter((e) => e.type === 'ATTEMPT_DONE')
  const prompt = done.reduce((n, e) => n + (e.attempt_prompt_tokens ?? 0), 0)
  const out = done.reduce((n, e) => n + (e.attempt_completion_tokens ?? 0), 0)
  const calls = done.reduce(
    (n, e) =>
      n +
      Object.values((e.tools ?? {}) as Record<string, number>).reduce(
        (a, b) => a + b,
        0,
      ),
    0,
  )

  const row = (k: string, v: string, hot = false) => (
    <div key={k} className="font-pixel" style={{ display: 'flex', gap: 10 }}>
      <span style={{ color: alpha(NEO4J.cream, 0.75), minWidth: pt(150) }}>
        {k}
      </span>
      <span style={{ color: 'hsl(var(--muted))' }}>=</span>
      <span
        style={{
          color: hot ? ACCENT : NEO4J.lightForest,
          transition: `color ${EASE} 400ms`,
          overflowWrap: 'anywhere',
        }}
      >
        {v}
      </span>
    </div>
  )

  return (
    <SlideChrome
      title="Mistral Vibe"
      accent={ACCENT}
      mark={mistralM}
      badge="self-hosted, by config"
      focused={onStage}
      footer={
        <span>
          harness/vibe-config.template.toml, rendered per agent by render_config()
          in orchestrator/vibe_agent.py · the shape is Mistral's own documented one
          for offline models · the figures are counted on the wire below
        </span>
      }
    >
      <div className="flex h-full" style={{ gap: 26 }}>
        <div
          className="flex min-w-0 flex-1 flex-col justify-center"
          style={{ gap: 20 }}
        >
          {/* The file. One line moves. */}
          <div
            style={{
              background: '#221f3e',
              border: `2px solid ${alpha(ACCENT, 0.45)}`,
              borderRadius: 10,
              padding: '20px 26px',
            }}
          >
            <div
              className="font-pixel"
              style={{ fontSize: pt(26), color: 'hsl(var(--muted))' }}
            >
              [[providers]]
            </div>
            <div style={{ fontSize: pt(30), marginTop: 10 }}>
              {row('name', '"sglang"')}
              {/* The hot line: the only thing that decides where the tokens
                  go, and the only thing on this card that changes. */}
              <div
                className="font-pixel"
                style={{
                  display: 'flex',
                  gap: 10,
                  padding: '8px 10px',
                  margin: '6px -10px',
                  borderRadius: 6,
                  background: alpha(ACCENT, local ? 0.16 : 0.08),
                  transition: `background ${EASE} 400ms`,
                }}
              >
                <span
                  style={{ color: alpha(NEO4J.cream, 0.75), minWidth: pt(150) }}
                >
                  api_base
                </span>
                <span style={{ color: 'hsl(var(--muted))' }}>=</span>
                <span
                  style={{
                    color: local ? ACCENT : 'hsl(var(--muted-fg))',
                    transition: `color ${EASE} 400ms`,
                    overflowWrap: 'anywhere',
                  }}
                >
                  "{local ? LOCAL : HOSTED}"
                </span>
              </div>
              {BLOCK.slice(1).map(([k, v]) => row(k, v))}
            </div>
            <div
              className="font-pixel"
              style={{
                fontSize: pt(23),
                color: 'hsl(var(--muted))',
                marginTop: 14,
              }}
            >
              same file, same five keys, one value
            </div>
          </div>

          {/* The wire every token took. */}
          <div className="flex items-center" style={{ gap: 12, flexWrap: 'wrap' }}>
            {['Vibe', '127.0.0.1', 'SGLang', 'Small 4'].map((n, i) => (
              <div key={n} className="flex items-center" style={{ gap: 12 }}>
                {i > 0 ? (
                  <span
                    className="font-pixel"
                    style={{ fontSize: pt(28), color: alpha(ACCENT, 0.7) }}
                  >
                    →
                  </span>
                ) : null}
                <span
                  className="font-pixel"
                  style={{
                    fontSize: pt(26),
                    color: alpha(NEO4J.cream, 0.9),
                    padding: '6px 14px',
                    borderRadius: 6,
                    border: `2px solid ${alpha(ACCENT, 0.4)}`,
                  }}
                >
                  {n}
                </span>
              </div>
            ))}
          </div>
          <div
            className="font-pixel"
            style={{ fontSize: pt(23), color: 'hsl(var(--muted-fg))' }}
          >
            SGLang ships the matched pair: --reasoning-parser mistral,
            --tool-call-parser mistral
          </div>
        </div>

        {/* What went down that wire. */}
        <aside
          className="flex shrink-0 flex-col justify-center"
          style={{ width: '31%' }}
        >
          {done.length === 0 ? (
            <p
              className="font-pixel"
              style={{ fontSize: pt(26), color: 'hsl(var(--muted))' }}
            >
              Nothing graded yet in this run.
            </p>
          ) : (
            <>
              {(
                [
                  [compact(prompt), 'prompt tokens'],
                  [compact(out), 'tokens generated'],
                  [calls.toLocaleString(), 'tool calls'],
                ] as [string, string][]
              ).map(([n, of]) => (
                <div key={of} style={{ marginBottom: 18 }}>
                  <div
                    className="heading-solid"
                    style={{ fontSize: pt(54), color: ACCENT, lineHeight: 1 }}
                  >
                    {n}
                  </div>
                  <div
                    className="font-pixel"
                    style={{ fontSize: pt(24), color: 'hsl(var(--muted-fg))' }}
                  >
                    {of}
                  </div>
                </div>
              ))}
              <div
                className="font-pixel"
                style={{
                  fontSize: pt(24),
                  color: alpha(NEO4J.cream, 0.85),
                  marginTop: 6,
                }}
              >
                every one of them to a GPU in the next rack
              </div>
            </>
          )}
        </aside>
      </div>
    </SlideChrome>
  )
}
