/**
 * The repo under test. Three questions, answered in order.
 *
 *   WHAT IT IS       x12sdk — typed Pydantic models and a streaming SDK for
 *                    HIPAA ASC X12 health care transactions.
 *   WHAT IT IS FOR   turning EDI wire format into typed objects and back,
 *                    byte for byte.
 *   WHY IT MUST GO   it is BUILT on Pydantic v1. On v2 it does not import,
 *                    and its own release is blocked on the port.
 *
 * This replaced "What is in the way", which grouped error signatures by
 * frequency. That card said what the agents were tripping over and never
 * said what they were working on — so an audience three cards in still did
 * not know what the codebase was.
 *
 * ── The middle panel is the whole card ───────────────────────────────────
 *
 * A REAL SEGMENT, A REAL MODEL, AND THE ROUND TRIP. The string is line 9 of
 * `fixtures/x12sdk/demo-file/demo.270`; the model is `Nm1Segment` from
 * `x12sdk/v4010/segments.py:2226`, and the field names and order are that
 * class's, not a paraphrase. The three empty delimiters between ROBERT and
 * MI are the three optional name fields — checked against the class, which
 * is what makes the mapping demonstrable rather than illustrative.
 *
 * Every constraint on those fields is a `Field(min_length=…, max_length=…)`.
 * That is why this repo is a Pydantic migration and not a rename: the
 * library IS the type system here.
 *
 * ── Where the figures come from ──────────────────────────────────────────
 *
 * `runs/x12sdk-report.md` §3, which recorded them before any GPU was spent:
 * 383 v1 surfaces across 11 of 21 kinds, the per-kind breakdown, a 261-test
 * oracle at 78% sensitivity, and `scripts/grade_fixture.py` in a real
 * Daytona sandbox measuring baseline 0 passing / 383 surfaces against answer
 * key 261 passing / 2 surfaces. Constants here rather than a parse: the
 * report is a checked-in document, and the footer names the section so any
 * figure on the card can be chased to the line that produced it.
 *
 * The blocker quote is the package's own README, verbatim.
 */
import type { ReactNode } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { NEO4J, alpha } from '@/lib/brand'
import { pt } from '@/lib/type'
import type { SlideProps } from './types'

const ACCENT = NEO4J.hibiscus
const CODE_BG = '#221f3e'

/** Line 9 of demo-file/demo.270. A subscriber, on the wire. */
const SEGMENT = 'NM1*IL*1*SMITH*ROBERT****MI*11122333301~'

/** `Nm1Segment`, x12sdk/v4010/segments.py:2226 — its own field names. */
const MODEL: [string, string][] = [
  ['entity_identifier_code', '"IL"'],
  ['entity_type_qualifier', 'PERSON'],
  ['name_last_or_organization_name', '"SMITH"'],
  ['name_first', '"ROBERT"'],
  ['identification_code_qualifier', '"MI"'],
  ['identification_code', '"11122333301"'],
]

/** runs/x12sdk-report.md §3, "Surface breakdown at baseline". */
const SURFACES: [string, number][] = [
  ['Field(const/regex/items)', 256],
  ['@root_validator', 59],
  ['conint/constr/…', 42],
  ['__fields__', 7],
  ['.dict() / .json()', 6],
  ['@validator', 6],
  ['class Config', 3],
  ['BaseSettings, Extra, ModelField, schema()', 4],
]
const TOTAL_SURFACES = SURFACES.reduce((n, [, v]) => n + v, 0)

const ORACLE_TESTS = 261
/** The answer key does not reach zero. See the report: the floor is 2. */
const ANSWER_KEY_FLOOR = 2

function Panel({
  label,
  grow,
  children,
}: {
  label: string
  grow: number
  children: ReactNode
}) {
  return (
    <section
      className="flex min-w-0 flex-col"
      style={{
        flex: `${grow} 1 0`,
        background: alpha(NEO4J.periwinkle, 0.07),
        border: `2px solid ${alpha(NEO4J.periwinkle, 0.3)}`,
        borderRadius: 10,
        padding: '16px 20px',
      }}
    >
      <h3
        className="font-pixel shrink-0"
        style={{
          fontSize: pt(24),
          color: ACCENT,
          letterSpacing: '0.14em',
          marginBottom: 12,
        }}
      >
        {label}
      </h3>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </section>
  )
}

export function RepoSlide({ onStage }: SlideProps) {
  return (
    <SlideChrome
      title="The repo under test"
      accent={ACCENT}
      badge={`${TOTAL_SURFACES} v1 surfaces · ${ORACLE_TESTS} tests · floor ${ANSWER_KEY_FLOOR}`}
      focused={onStage}
      footer={
        <span>
          fixtures/x12sdk — owgreen-dev/x12sdk#8 · the segment is its own
          demo-file/demo.270, the model is Nm1Segment in v4010/segments.py · the
          figures are runs/x12sdk-report.md §3, measured before any GPU was spent
        </span>
      }
    >
      <div className="flex h-full" style={{ gap: 18 }}>
        <Panel label="WHAT IT IS" grow={27}>
          <div
            className="heading-solid"
            style={{ fontSize: pt(52), color: alpha(NEO4J.cream, 0.95) }}
          >
            x12sdk
          </div>
          <div
            className="font-pixel"
            style={{
              fontSize: pt(26),
              color: 'hsl(var(--muted-fg))',
              marginTop: 4,
            }}
          >
            owgreen-dev/x12sdk
          </div>
          <p
            className="font-pixel"
            style={{
              fontSize: pt(27),
              lineHeight: 1.35,
              color: alpha(NEO4J.cream, 0.92),
              marginTop: 16,
            }}
          >
            Typed Pydantic models and a streaming SDK for HIPAA ASC X12 health care
            transactions.
          </p>
          <div style={{ marginTop: 18 }}>
            {(
              [
                ['837P / 837I', 'professional & institutional claims'],
                ['835', 'claim payment / remittance'],
                ['834', 'benefit enrolment'],
                ['270 / 271', 'eligibility inquiry & response'],
                ['276 / 277', 'claim status'],
              ] as [string, string][]
            ).map(([set, what]) => (
              <div
                key={set}
                className="flex items-baseline"
                style={{ gap: 12, marginBottom: 6 }}
              >
                <span
                  className="font-pixel"
                  style={{
                    fontSize: pt(26),
                    color: ACCENT,
                    minWidth: pt(150),
                  }}
                >
                  {set}
                </span>
                <span
                  className="font-pixel"
                  style={{ fontSize: pt(23), color: 'hsl(var(--muted-fg))' }}
                >
                  {what}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel label="WHAT IT IS FOR" grow={39}>
          {/* The wire. */}
          <div
            className="font-pixel shrink-0"
            style={{
              fontSize: pt(25),
              color: NEO4J.lightForest,
              background: CODE_BG,
              border: `2px solid ${alpha(NEO4J.lightForest, 0.4)}`,
              borderRadius: 8,
              padding: '10px 12px',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {SEGMENT}
          </div>
          <div
            className="font-pixel shrink-0"
            style={{
              fontSize: pt(24),
              color: 'hsl(var(--muted-fg))',
              padding: '6px 0',
            }}
          >
            ↓ parse
          </div>

          {/* The model. Its real field names, in its own order. */}
          <div
            style={{
              background: CODE_BG,
              border: `2px solid ${alpha(ACCENT, 0.45)}`,
              borderRadius: 8,
              padding: '10px 12px',
              overflow: 'hidden',
            }}
          >
            <div className="font-pixel" style={{ fontSize: pt(25), color: ACCENT }}>
              Nm1Segment(
            </div>
            {MODEL.map(([k, v]) => (
              <div
                key={k}
                className="font-pixel"
                style={{
                  fontSize: pt(23),
                  color: alpha(NEO4J.cream, 0.9),
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  paddingLeft: 18,
                }}
              >
                {k} = <span style={{ color: NEO4J.lightPeriwinkle }}>{v}</span>
              </div>
            ))}
            <div className="font-pixel" style={{ fontSize: pt(25), color: ACCENT }}>
              )
            </div>
          </div>
          <div
            className="font-pixel shrink-0"
            style={{
              fontSize: pt(24),
              color: 'hsl(var(--muted-fg))',
              padding: '6px 0',
            }}
          >
            ↓ serialise
          </div>
          <div
            className="font-pixel shrink-0"
            style={{
              fontSize: pt(25),
              color: NEO4J.lightForest,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {SEGMENT}
          </div>
          <div
            className="font-pixel shrink-0"
            style={{
              fontSize: pt(23),
              color: alpha(NEO4J.cream, 0.85),
              marginTop: 8,
            }}
          >
            the suite asserts that round trip byte for byte
          </div>
        </Panel>

        <Panel label="WHY IT MUST BE MIGRATED" grow={34}>
          <div
            className="heading-solid"
            style={{ fontSize: pt(46), color: ACCENT, lineHeight: 1.05 }}
          >
            On Pydantic v2 it does not import
          </div>
          <div
            className="font-pixel"
            style={{
              fontSize: pt(24),
              lineHeight: 1.3,
              color: alpha(NEO4J.cream, 0.9),
              background: CODE_BG,
              border: `2px solid ${alpha(ACCENT, 0.45)}`,
              borderRadius: 8,
              padding: '10px 12px',
              marginTop: 12,
              overflowWrap: 'anywhere',
            }}
          >
            PydanticImportError: `BaseSettings` has been moved to the
            `pydantic-settings` package
          </div>

          {/* Every v1 construct in the package, by kind, to one scale. */}
          <div style={{ marginTop: 16 }}>
            <div
              className="font-pixel"
              style={{ fontSize: pt(24), color: 'hsl(var(--muted-fg))' }}
            >
              {TOTAL_SURFACES} v1 surfaces, 11 of 21 kinds
            </div>
            {SURFACES.map(([kind, n]) => (
              <div
                key={kind}
                className="flex items-center"
                style={{ gap: 10, marginTop: 5 }}
              >
                <span
                  className="font-pixel tabular-nums"
                  style={{
                    fontSize: pt(23),
                    color: alpha(NEO4J.cream, 0.9),
                    minWidth: pt(56),
                    textAlign: 'right',
                  }}
                >
                  {n}
                </span>
                <span
                  style={{
                    height: pt(16),
                    width: `${(n / SURFACES[0][1]) * 34}%`,
                    background: alpha(ACCENT, 0.75),
                    borderRadius: 3,
                    flexShrink: 0,
                  }}
                />
                <span
                  className="font-pixel"
                  style={{
                    fontSize: pt(22),
                    color: 'hsl(var(--muted-fg))',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {kind}
                </span>
              </div>
            ))}
          </div>

          <div
            className="font-pixel"
            style={{
              fontSize: pt(25),
              lineHeight: 1.35,
              color: alpha(NEO4J.cream, 0.92),
              marginTop: 16,
              borderLeft: `4px solid ${alpha(ACCENT, 0.7)}`,
              paddingLeft: 14,
            }}
          >
            “The first x12sdk release will ship once the Pydantic v2 port is
            complete.”
            <div
              style={{
                color: 'hsl(var(--muted-fg))',
                fontSize: pt(22),
                marginTop: 4,
              }}
            >
              its own README · 0 of {ORACLE_TESTS} tests pass today
            </div>
          </div>
        </Panel>
      </div>
    </SlideChrome>
  )
}
