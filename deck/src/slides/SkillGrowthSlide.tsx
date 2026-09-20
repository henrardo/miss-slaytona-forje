/**
 * Every version of the skill, by size.
 *
 * Eighty-one rewrites of the same procedure, each one the agent's own. The
 * shape of this line is the story: it grows while the agent is learning, and a
 * sharp DROP is the thing to watch for, because one accepted version collapsed
 * the booklet from 3,439 words to 686 and the warm arm promptly stopped editing
 * files. The validator had nothing to object to.
 *
 * Bytes on disk rather than the harness's token estimate: it is the number
 * that cannot drift from what is actually there, and the shape is identical.
 */
import { useEffect, useMemo, useState } from 'react'
import { SlideChrome } from '@/hud/SlideChrome'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, NEO4J, alpha } from '@/lib/brand'
import type { SlideProps } from './types'

const W = 1700
const H = 700
const PAD = { l: 140, r: 40, t: 30, b: 90 }

/** A fall this steep between versions is worth a mark on the chart. */
const COLLAPSE = 0.6
/**
 * How many collapses to actually LABEL.
 *
 * The real series sawtooths — the procedure is rewritten from scratch each
 * time, so it routinely halves and regrows — and marking every drop put forty
 * overlapping labels across the chart, which is the same as marking none. The
 * count goes in the footer; the three deepest get named.
 */
const LABEL_WORST = 3

export function SkillGrowthSlide({ onStage }: SlideProps) {
  const { events } = useRunFeed()
  const [versions, setVersions] = useState<{ version: number; bytes: number }[]>([])
  const [dir, setDir] = useState<string | null>(null)

  const distillations = useMemo(
    () => events.filter((e) => e.type === 'DISTILLED').length,
    [events],
  )
  useEffect(() => {
    void fetch('/api/skills')
      .then((r) => r.json())
      .then((j: { dir: string | null; versions: typeof versions }) => {
        setVersions(j.versions ?? [])
        setDir(j.dir)
      })
      .catch(() => undefined)
  }, [distillations])

  const geom = useMemo(() => {
    if (versions.length < 2) return null
    const maxV = Math.max(...versions.map((v) => v.version))
    const minV = Math.min(...versions.map((v) => v.version))
    const maxB = Math.max(...versions.map((v) => v.bytes))
    const X = (v: number) =>
      PAD.l + ((v - minV) / Math.max(1, maxV - minV)) * (W - PAD.l - PAD.r)
    // From zero: this is a magnitude, and a truncated axis would make an
    // ordinary rewrite look like a collapse.
    const Y = (b: number) => PAD.t + (1 - b / maxB) * (H - PAD.t - PAD.b)
    const all = versions
      .map((v, i) => ({ v, drop: i > 0 ? v.bytes / versions[i - 1].bytes : 1 }))
      .filter((x) => x.drop < COLLAPSE)
    const collapses = [...all]
      .sort((a, b) => a.drop - b.drop)
      .slice(0, LABEL_WORST)
      .map((x) => x.v)
    return { X, Y, maxV, minV, maxB, collapses, collapseCount: all.length }
  }, [versions])

  return (
    <SlideChrome
      title="Skill growth"
      accent={NEO4J.marigold}
      badge={
        versions.length
          ? `v${versions[versions.length - 1].version} · ${versions.length} versions`
          : 'no versions'
      }
      focused={onStage}
      footer={
        <span>
          {dir ?? 'skills/versions*'} · bytes on disk · {geom?.collapseCount ?? 0}{' '}
          collapse(s), deepest labelled
        </span>
      }
    >
      {!geom ? (
        <div
          className="font-pixel flex h-full items-center justify-center"
          style={{ fontSize: 48, color: 'hsl(var(--muted-fg))' }}
        >
          one version so far — the line needs two
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-full w-full"
          role="img"
          aria-label="Skill size by version"
        >
          {[0, 0.5, 1].map((f) => (
            <g key={f}>
              <line
                x1={PAD.l}
                x2={W - PAD.r}
                y1={geom.Y(geom.maxB * f)}
                y2={geom.Y(geom.maxB * f)}
                stroke={alpha(NEO4J.periwinkle, 0.16)}
                strokeWidth={2}
              />
              <text
                x={PAD.l - 16}
                y={geom.Y(geom.maxB * f) + 10}
                textAnchor="end"
                fontSize={26}
                fill="hsl(var(--muted-fg))"
                fontFamily="'VT323', monospace"
              >
                {Math.round((geom.maxB * f) / 1024)}k
              </text>
            </g>
          ))}

          <path
            d={versions
              .map(
                (v, i) =>
                  `${i ? 'L' : 'M'} ${geom.X(v.version)} ${geom.Y(v.bytes)}`,
              )
              .join(' ')}
            fill="none"
            stroke={NEO4J.marigold}
            strokeWidth={4}
            strokeLinejoin="round"
          />
          {versions.map((v) => (
            <circle
              key={v.version}
              cx={geom.X(v.version)}
              cy={geom.Y(v.bytes)}
              r={4}
              fill={NEO4J.marigold}
            />
          ))}

          {/* Collapses, named. This is the whole reason the card exists. */}
          {geom.collapses.map((v) => (
            <g key={`c${v.version}`}>
              <circle
                cx={geom.X(v.version)}
                cy={geom.Y(v.bytes)}
                r={16}
                fill="none"
                stroke={ALARM}
                strokeWidth={4}
              />
              <text
                x={geom.X(v.version)}
                y={geom.Y(v.bytes) + 46}
                textAnchor="middle"
                fontSize={26}
                fill={ALARM}
                fontFamily="'VT323', monospace"
              >
                v{v.version} collapsed
              </text>
            </g>
          ))}

          {[geom.minV, Math.round((geom.minV + geom.maxV) / 2), geom.maxV].map(
            (v) => (
              <text
                key={`x${v}`}
                x={geom.X(v)}
                y={H - PAD.b + 40}
                textAnchor="middle"
                fontSize={26}
                fill="hsl(var(--muted-fg))"
                fontFamily="'VT323', monospace"
              >
                v{v}
              </text>
            ),
          )}
          <text
            x={(W + PAD.l) / 2}
            y={H - 16}
            textAnchor="middle"
            fontSize={28}
            fill="hsl(var(--muted-fg))"
            fontFamily="'VT323', monospace"
          >
            skill version
          </text>
        </svg>
      )}
    </SlideChrome>
  )
}
