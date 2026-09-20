/**
 * The race.
 *
 * Two Mistral Ms lap the board while the run happens: warm in Mistral's own
 * flame, cold in the same artwork at a cold hue. The track lives in the band
 * the stage gives up when race mode is armed — see RACE_BAND in hud/Hud.tsx.
 *
 * ── One drawing, two colourways ──────────────────────────────────────────
 *
 * The cold M is not a second asset. `mistral-M.svg` is imported as source and
 * every fill is rewritten to a single cold hue, keeping each stop's saturation
 * and lightness — so the M stays shaded pixel art instead of a blue silhouette,
 * and re-running the extractor updates both racers at once. Inlined rather than
 * loaded through `<img>`, which is also what lets the fills be rewritten at all.
 *
 * ── What the position means ──────────────────────────────────────────────
 *
 * Distance around the lap is progress, and WHICH NUMBER THAT IS depends on the
 * fixture — decided from the fixture's own data, and printed on the track.
 *
 *   TESTS PASSED, the measure this project trusts (`tests_passed()` in
 *   orchestrator/vibe_agent.py: an error signature changing is not progress).
 *   Used when the suite actually moves, as it does on oapi: 5 -> 9 -> 33.
 *   No test TOTAL is ever emitted, so the lap is scaled between the lowest
 *   anyone reported and the best anyone reached.
 *
 *   V1 SURFACES CLEARED, when the fixture reports them. On x12sdk the suite
 *   does not move — the harness's own note records 70% of 77 graded attempts
 *   scoring exactly 0, because 0 means both "has not migrated it yet" and
 *   "broke the package". A lap made of that is two Ms parked on the line for a
 *   whole talk. Surfaces are counted off the source, are defined even when the
 *   tree does not parse, and come with a real denominator: the untouched
 *   checkout, 383 of them.
 *
 * On the surfaces lap an arm can lead BECAUSE it broke the package, so a racer
 * whose tree no longer parses is haloed in the alarm colour and the track says
 * how many of its files still compile.
 *
 * A leader is held at LEAD_CAP, short of the line. ONLY `FILE_DONE` with
 * `success` puts a racer on the line, because converging is the oracle's call
 * and nothing else. Without that cap the leader would sit pinned at the finish
 * from the first attempt onward, which is not a race and is not true.
 *
 * On the tests lap the denominator is the best result IN THE RUN BEING SHOWN.
 * Replaying a finished run that is known up front, so the ends of the lap stay
 * put and a racer only ever moves forwards. Live it can only be the best so
 * far — so when one arm sets a new record the lap lengthens for both and the
 * other loses ground relative to it. That is what a relative measure means,
 * and it is true: the leader really did pull away.
 *
 * ── Live, or a replay ────────────────────────────────────────────────────
 *
 * A run that is still being written is tracked as it lands: every
 * `ATTEMPT_DONE` moves a racer. A run that has FINISHED arrives as one
 * snapshot, and two Ms that jump once and park are not a race — which is
 * exactly what the deck showed for every rehearsal file, since a rehearsal is
 * over by the time anyone looks at it.
 *
 * So arming a finished run REPLAYS it on the clock, using each event's own `t`
 * (seconds since the run started), compressed so the lap takes about a minute
 * and never runs slower than the run did. The track says `replay` when that is
 * what you are watching, for the same reason the terminal card does.
 *
 * Which of the two it is gets latched when Slay is pressed. A live run that
 * finishes mid-talk keeps being tracked live — it simply stops moving — rather
 * than rewinding itself under the audience.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useRunFeed } from '@/data/RunFeed'
import { ALARM, NEO4J, alpha, withHue } from '@/lib/brand'
import { expand, lapPath, lapPoint, type Oval } from '@/lib/track'
import type { Arm, RunEvent } from '@/lib/types'
import type { Rect } from '@/lib/layout'
import M_SVG from '@/wordmark/glyphs/mistral-M.svg?raw'

/**
 * Cold's hue. A decisive blue, deliberately clear of the deck's periwinkle
 * chrome (231) and of Daytona's cyan (196) — a racer must not read as either.
 */
const COLD_HUE = 212

/** How far a leader may get without the oracle saying they converged. */
const LEAD_CAP = 0.88

/**
 * The lap runs from just AFTER the start line to just BEFORE it.
 *
 * On a closed lap t=0 and t=1 are the same point, so a racer who converged
 * would park on the start line, exactly where a racer who has not started yet
 * sits. Racers therefore leave from `START_T` and finish at `FINISH_T`, a
 * whole lap apart on screen and unmistakable — which is how a real lap works.
 */
const START_T = 0.015
const FINISH_T = 0.985

/**
 * Token height as a fraction of the band, and where the two lane centrelines
 * sit across it.
 *
 * These are coupled and the constraint is the moment both arms are on the same
 * split — at the start, and any time they are level. Lane separation is
 * `(0.74 - 0.26) * band = 0.48 band`; a token is `0.40 band`. That leaves a
 * visible gap between them rather than one M sitting on top of the other,
 * which is exactly what 0.46 / 0.29-0.71 did.
 */
const TOKEN = 0.4
const LANES = { cold: 0.26, warm: 0.74 }

/**
 * Seconds per lap, from no progress to all of it.
 *
 * THE RACERS RUN. Position-as-progress was the first model and it does not
 * survive contact with the data: five graded attempts across a 15-second
 * rehearsal is five small hops and then stillness, and on x12sdk, where the
 * suite never moves, it was two Ms sitting on the start line for a whole talk.
 * A racetrack whose racers do not go round is a diagram.
 *
 * So progress is SPEED, not position. Both arms lap the board while the run is
 * going; the one making more of the measure laps faster and pulls away, and
 * the gap between them — and the lap counts on the track — is the race. An arm
 * that has converged stops at the line, because it is done.
 *
 * A stalled arm still circles, slowly, which is true: it is still burning GPU
 * on attempts that are not landing. It is the LEAD that means progress.
 */
const LAP_SLOW_S = 26
const LAP_FAST_S = 9

const MOVE = '1100ms cubic-bezier(0.22, 1, 0.36, 1)'

/**
 * A run whose file was touched this recently is taken to be still running.
 *
 * SIX MINUTES, because that is what the data demanded. 25 seconds looked
 * generous until the x12sdk run going on right now was measured: cold's first
 * graded attempt landed at t=988 and warm's at t=1196, so the log can be
 * silent for three and a half minutes between events in the middle of a
 * perfectly healthy run. At 25s the deck called that run finished and replayed
 * it — a live race, rewound, on a clock.
 *
 * The error is deliberately asymmetric. A live run misread as finished gets
 * replayed and is wrong; a finished run misread as live just sits there until
 * the window passes, and both the end-of-run signals below cut that short in
 * every case the harness actually emits one. Both clocks are this laptop's —
 * the collector stats the file, the browser reads `Date.now()`.
 */
const LIVE_WITHIN_MS = 6 * 60_000
/**
 * A replay is stretched or compressed to land inside this window.
 *
 * A 20-minute pod run played at 1x is not a race anyone watches; a 15-second
 * rehearsal played at 1x is over before it has been introduced. Both ends are
 * clamped and the RATE IS ON THE TRACK — `replay ×20` and `replay ×0.3` are
 * both honest, `replay` with a hidden rate would not be.
 */
const REPLAY_MIN_S = 40
const REPLAY_MAX_S = 60
/** Replay resolution. Racers move on attempt boundaries; this is far finer. */
const TICK_MS = 250

/** `mistral-M.svg`, sized to its box and optionally re-hued. */
function mSvg(hue?: number): string {
  const body =
    hue == null
      ? M_SVG
      : M_SVG.replace(/fill="(#[0-9a-f]{6})"/gi, (_, hex: string) => {
          return `fill="${withHue(hex, hue)}"`
        })
  // Drop the intrinsic size so the wrapper governs it; viewBox does the rest.
  return body.replace(/^<svg([^>]*)>/, (tag) =>
    tag
      .replace(/\s(width|height)="[^"]*"/g, '')
      .replace('<svg', '<svg width="100%" height="100%"'),
  )
}

const ART: Record<Arm, string> = {
  warm: mSvg(),
  cold: mSvg(COLD_HUE),
}

export interface RacerState {
  arm: Arm
  passed: number
  /** v1 surfaces this arm has cleared, when that is what the lap measures. */
  cleared: number
  /** This arm's progress, 0..1, on whichever measure the race is using. */
  share: number
  /**
   * Pace, 0..1: this arm's progress as a fraction of the LEADER's.
   *
   * Absolute share is the wrong thing to drive speed with. On x12sdk warm
   * cleared 60 of 364 surfaces and cold 8 — shares of 0.16 and 0.02, which as
   * lap times are 23.2s and 25.6s, a difference nobody in a room can see, for
   * a run where one arm did seven times the work of the other. Against the
   * leader those become 1.0 and 0.13, and warm laps the board nearly three
   * times as fast, which is what the numbers actually say. The caption prints
   * the raw counts, so the relative pace never has to be taken on trust.
   */
  pace: number
  /** Is this arm still in the race — run going, and it has not converged? */
  running: boolean
  /**
   * Files that still parse, from this arm's most recent graded attempt.
   * `null` until it has one. A racer whose tree does not compile is marked,
   * because clearing surfaces by breaking the package is not progress and the
   * lap on its own cannot tell the difference.
   */
  parse: { ok: number; total: number } | null
  finished: boolean
  /** Position around the lap, 0..1. */
  t: number
}

/** Which number the lap is made of. Chosen from the data — see below. */
export type Measure = { kind: 'tests' } | { kind: 'surfaces'; baseline: number }

/** What the track is showing, so it can say so. */
export type RaceClock =
  | { mode: 'live'; graded: number; measure: Measure }
  | {
      mode: 'replay'
      graded: number
      measure: Measure
      speed: number
      /** Which time round. A replay loops rather than parking. */
      loop: number
      at: number
      span: number
    }
  /** A finished run, not yet armed: Slay will replay it. */
  | { mode: 'ready'; graded: number; measure: Measure }

/**
 * Read both racers out of the event tail.
 *
 * `armed` is Slay: while it is false nothing is shown, and pressing it is what
 * decides between following a live run and replaying a finished one.
 */
export function useRacers(armed: boolean): {
  warm: RacerState
  cold: RacerState
  clock: RaceClock
} {
  const { events, runs, runId } = useRunFeed()

  /** The run's own time bounds, and whether it has been graded at all. */
  const bounds = useMemo(() => {
    let first = Number.POSITIVE_INFINITY
    let last = 0
    let graded = 0
    let ended = false
    const parked = new Set<string>()
    for (const e of events as RunEvent[]) {
      const t = typeof e.t === 'number' ? e.t : 0
      if (t < first) first = t
      if (t > last) last = t
      if (e.type === 'ATTEMPT_DONE') graded++
      // Two ways a run says it is over. `RUN_END` is the swarm harness's own
      // last line; the rehearsal loop does not write one, but both writers
      // emit one `FILE_DONE` per arm when that arm stops, so both arms done
      // IS the end of the run. Without the second signal a rehearsal that
      // finished two minutes ago would still be treated as live and Slay
      // would show a parked race instead of replaying it.
      if (e.type === 'RUN_END') ended = true
      if (e.type === 'FILE_DONE' && e.swarm) parked.add(e.swarm)
    }
    return {
      first: Number.isFinite(first) ? first : 0,
      last,
      graded,
      ended: ended || (parked.has('warm') && parked.has('cold')),
      any: events.length > 0,
    }
  }, [events])

  /** Is the file still being appended to? */
  const growing = useMemo(() => {
    if (bounds.ended) return false
    const entry = runs.find((r) => r.id === runId)
    return !!entry && Date.now() - entry.mtimeMs < LIVE_WITHIN_MS
  }, [runs, runId, bounds.ended])

  // Read through refs inside the effect below: the replay must be armed by
  // Slay, not restarted every time the collector reports the run index.
  const latest = useRef({ growing, bounds })
  latest.current = { growing, bounds }

  /**
   * Replay position, in run-seconds, or null when following live.
   *
   * `speed` is carried alongside so the track can show it. A rehearsal lasting
   * 30s plays at 1x and takes 30s; a 20-minute pod run plays at 20x and takes
   * the same minute, which is as long as a race can hold a room.
   */
  const [play, setPlay] = useState<{
    at: number
    speed: number
    loop: number
  } | null>(null)

  useEffect(() => {
    if (!armed) {
      setPlay(null)
      return
    }
    const { growing: live, bounds: b } = latest.current
    if (live || !b.any) {
      // Live, or nothing to replay yet. Either way: show what has arrived.
      setPlay(null)
      return
    }
    const from = b.first
    const to = b.last
    const span = Math.max(1, to - from)
    const window_s = Math.min(REPLAY_MAX_S, Math.max(REPLAY_MIN_S, span))
    const speed = span / window_s
    let started = performance.now()
    let loop = 1
    setPlay({ at: from, speed, loop })
    const id = window.setInterval(() => {
      const elapsed = (performance.now() - started) / 1000
      const at = from + elapsed * speed
      if (at >= to) {
        // AND AGAIN. A replay that stops after 60 seconds leaves two Ms parked
        // for the rest of the talk, which is the thing this exists to fix. The
        // loop counter is on the track, so nobody mistakes lap 12 for a run
        // that has been going for twelve laps.
        started = performance.now()
        loop += 1
        setPlay({ at: from, speed, loop })
        return
      }
      setPlay({ at, speed, loop })
    }, TICK_MS)
    return () => window.clearInterval(id)
    // `bounds.any` and not `events`: the replay starts once the snapshot has
    // landed and is not restarted by anything that arrives afterwards.
  }, [armed, runId, bounds.any])

  const { racers, measure } = useMemo(() => {
    let floor: number | null = null
    let target = 0
    /** The untouched checkout's v1 surface count — the most anyone reported. */
    let baseline = 0

    for (const e of events as RunEvent[]) {
      const arm = e.swarm
      if (arm !== 'warm' && arm !== 'cold') continue
      if (e.type === 'ATTEMPT_DONE') {
        const passed = e.tests_passed ?? 0
        // THE LAP IS SCALED TO THE WHOLE RUN BEING SHOWN, not to the prefix
        // replayed so far. During a replay the ends of the lap are therefore
        // fixed and nobody moves backwards; live, the run so far IS the whole
        // run, so this is the same number it always was.
        //
        // The baseline is the LOWEST anyone reported, not the first. Usually
        // the same number — the first graded attempt is generally the worst —
        // but it cannot be swung by which arm happened to be graded first.
        floor = floor === null ? passed : Math.min(floor, passed)
        target = Math.max(target, passed)
        baseline = Math.max(baseline, e.v1_remaining ?? 0)
      }
    }

    // WHICH NUMBER THE LAP IS MADE OF, decided by the fixture's own data.
    //
    // `tests_passed` is the measure this project trusts, and on the oapi
    // fixture it is the right one — the suite moves, 5 -> 9 -> 33. On x12sdk
    // it does not: the harness's own note records 70% of 77 graded attempts
    // scoring exactly 0, because 0 means both "has not migrated it yet" and
    // "broke the package". A lap made of that number is two Ms parked on the
    // line for a whole talk, which says nothing true about what the arms did.
    //
    // So when the fixture reports v1 surfaces left to migrate, the lap is
    // SURFACES CLEARED — counted off the source, defined even when the tree
    // does not parse, and with a real denominator (the untouched checkout).
    // The choice is made from `v1_remaining`, which is a property of the
    // fixture, not of how the run is going, so it cannot flip mid-race.
    const measure: Measure =
      baseline > 0 ? { kind: 'surfaces', baseline } : { kind: 'tests' }

    const best: Record<Arm, number> = { warm: 0, cold: 0 }
    const cleared: Record<Arm, number> = { warm: 0, cold: 0 }
    const parse: Record<Arm, { ok: number; total: number } | null> = {
      warm: null,
      cold: null,
    }
    const done: Record<Arm, boolean> = { warm: false, cold: false }

    for (const e of events as RunEvent[]) {
      // Where each racer had got to by now. During a replay "now" is the
      // replay clock; live it is simply everything that has arrived.
      if (play && (typeof e.t === 'number' ? e.t : 0) > play.at) continue
      const arm = e.swarm
      if (arm !== 'warm' && arm !== 'cold') continue
      if (e.type === 'ATTEMPT_DONE') {
        // max, never latest: a racer does not go backwards because one
        // attempt happened to break more than it fixed.
        best[arm] = Math.max(best[arm], e.tests_passed ?? 0)
        if (typeof e.v1_remaining === 'number') {
          cleared[arm] = Math.max(cleared[arm], baseline - e.v1_remaining)
        }
        // Latest, not best: "does it compile RIGHT NOW" is the question.
        if (typeof e.parse_total === 'number' && typeof e.parse_ok === 'number') {
          parse[arm] = { ok: e.parse_ok, total: e.parse_total }
        }
      } else if (e.type === 'FILE_DONE' && e.success) {
        done[arm] = true
      }
    }

    const base = floor ?? 0
    const span = Math.max(1, target - base)
    const shareOf = (arm: Arm) =>
      Math.max(
        0,
        Math.min(
          1,
          measure.kind === 'surfaces'
            ? cleared[arm] / measure.baseline
            : (best[arm] - base) / span,
        ),
      )
    const leader = Math.max(shareOf('warm'), shareOf('cold'))

    const state = (arm: Arm): RacerState => {
      const share = shareOf(arm)
      // The oracle, and only the oracle, puts a racer on the line.
      const frac = done[arm] ? 1 : share * LEAD_CAP
      return {
        arm,
        passed: best[arm],
        cleared: cleared[arm],
        share,
        pace: leader > 0 ? share / leader : 0,
        // A converged arm stops: it is parked at the line, not still lapping.
        running: !done[arm] && (play != null || growing),
        parse: parse[arm],
        finished: done[arm],
        t: START_T + frac * (FINISH_T - START_T),
      }
    }
    return {
      racers: { warm: state('warm'), cold: state('cold') },
      measure,
    }
  }, [events, play, growing])

  const graded = useMemo(
    () =>
      play
        ? (events as RunEvent[]).filter(
            (e) =>
              e.type === 'ATTEMPT_DONE' &&
              (typeof e.t === 'number' ? e.t : 0) <= play.at,
          ).length
        : bounds.graded,
    [events, play, bounds.graded],
  )

  const clock: RaceClock = play
    ? {
        mode: 'replay',
        graded,
        measure,
        speed: play.speed,
        loop: play.loop,
        at: play.at - bounds.first,
        span: Math.max(1, bounds.last - bounds.first),
      }
    : growing
      ? { mode: 'live', graded, measure }
      : { mode: 'ready', graded, measure }

  return { ...racers, clock }
}

const mmss = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

/** One line saying what the race means and where the numbers come from. */
function caption(
  c: RaceClock,
  warm: RacerState,
  cold: RacerState,
  laps: Record<Arm, number>,
): string {
  const measure =
    c.measure.kind === 'surfaces'
      ? // "of 364 seen", not "of 383": the untouched count is never emitted,
        // because the first graded attempt has already edited the tree. The
        // raw counts are what make the pace checkable from the back of a room.
        `speed = v1 surfaces cleared: warm ${warm.cleared} · cold ${cold.cleared}` +
        ` of ${c.measure.baseline} seen`
      : `speed = tests passing: warm ${warm.passed} · cold ${cold.passed}`
  const graded = c.graded === 0 ? 'no graded attempt yet' : `${c.graded} graded`
  const score = `warm ${laps.warm} laps · cold ${laps.cold}`
  // Clearing surfaces by breaking the package is not progress, and the race
  // cannot tell the difference. Say it where it happens.
  const broken = [warm, cold]
    .filter((r) => r.parse && r.parse.ok < r.parse.total)
    .map((r) => `${r.arm} ${r.parse?.ok}/${r.parse?.total} files parse`)
    .join(' · ')
  const head =
    c.mode === 'replay'
      ? `replay ×${c.speed >= 2 ? Math.round(c.speed) : c.speed.toFixed(1)}` +
        `${c.loop > 1 ? ` loop ${c.loop}` : ''} · ${mmss(c.at)} / ${mmss(c.span)}`
      : c.mode === 'ready'
        ? 'finished run · Slay replays it'
        : 'live'
  return [head, score, graded, measure, broken].filter(Boolean).join(' · ')
}

/**
 * The running itself: distance integrated per frame, written straight to the
 * two elements.
 *
 * NOTHING HERE GOES THROUGH REACT. Sixty state updates a second would re-render
 * the track, the lane paths and the caption sixty times a second, next to a
 * force simulation, a canvas sprite and twenty live cards — the layer budget
 * documented in hud/Hud.tsx. Two transforms written to two refs is what a
 * compositor is for. The only state is the lap COUNT, which changes once a lap
 * and is what the caption needs.
 *
 * Speed comes from `share`: a stalled arm still laps in LAP_SLOW_S, an arm
 * carrying the whole measure laps in LAP_FAST_S, and the ratio of the two is
 * how fast the leader pulls away. Distance resets when the race is armed, so
 * every press of Slay starts both arms on the line.
 */
function useLapping({
  warm,
  cold,
  ovals,
  origin,
  token,
  running,
}: {
  warm: RacerState
  cold: RacerState
  ovals: Record<Arm, Oval>
  origin: Rect
  token: number
  running: boolean
}) {
  const refs = {
    warm: useRef<HTMLDivElement>(null),
    cold: useRef<HTMLDivElement>(null),
  }
  const dist = useRef<Record<Arm, number>>({ warm: 0, cold: 0 })
  const [laps, setLaps] = useState<Record<Arm, number>>({ warm: 0, cold: 0 })

  // The frame loop reads the live values through a ref, so new data changes
  // the speed without restarting the animation.
  const now = useRef({ warm, cold, ovals, origin, token })
  now.current = { warm, cold, ovals, origin, token }

  useEffect(() => {
    if (!running) {
      dist.current = { warm: 0, cold: 0 }
      setLaps({ warm: 0, cold: 0 })
      return
    }
    // Reduced motion: the racers hold the position their progress earns them,
    // which is the old behaviour and still says who is ahead.
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return

    let raf = 0
    let last = performance.now()
    const frame = (t: number) => {
      const dt = Math.min(0.25, (t - last) / 1000)
      last = t
      const s = now.current
      for (const arm of ['cold', 'warm'] as Arm[]) {
        const racer = s[arm]
        if (racer.running) {
          const lapS = LAP_SLOW_S + (LAP_FAST_S - LAP_SLOW_S) * racer.pace
          dist.current[arm] += dt / lapS
        }
        // A converged arm parks on the line; everyone else is somewhere on
        // their lap, offset past the start so a fresh racer is not sitting on
        // the finisher's spot.
        const at = racer.finished
          ? FINISH_T
          : START_T + (dist.current[arm] % 1) * (FINISH_T - START_T)
        const p = lapPoint(s.ovals[arm], at)
        const el = refs[arm].current
        if (el) {
          el.style.transform =
            `translate(${p.x - s.origin.x - s.token * 0.7}px, ` +
            `${p.y - s.origin.y - s.token / 2}px)`
        }
      }
      const counted = {
        warm: Math.floor(dist.current.warm),
        cold: Math.floor(dist.current.cold),
      }
      setLaps((prev) =>
        prev.warm === counted.warm && prev.cold === counted.cold ? prev : counted,
      )
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
    // Geometry is read through `now`, so a resize does not restart the race.
  }, [running])

  return { refs, laps }
}

export interface RacetrackProps {
  /** The hole in the ring — the track's outer bound. */
  outer: Rect
  /** The stage as shrunk for the race — the track's inner bound. */
  inner: Rect
  /** Corner radius of the stage container, so the lanes follow its shape. */
  radius: number
  visible: boolean
}

export function Racetrack({ outer, inner, radius, visible }: RacetrackProps) {
  const { warm, cold, clock } = useRacers(visible)

  const band = Math.max(1, (outer.w - inner.w) / 2)
  const innerOval: Oval = { ...inner, r: radius }
  const laneOval = (f: number) => expand(innerOval, band * f)
  const token = band * TOKEN

  const racers = [
    { s: cold, oval: laneOval(LANES.cold), art: ART.cold },
    { s: warm, oval: laneOval(LANES.warm), art: ART.warm },
  ]

  const { refs, laps } = useLapping({
    warm,
    cold,
    ovals: { cold: laneOval(LANES.cold), warm: laneOval(LANES.warm) },
    origin: outer,
    token,
    running: visible,
  })

  return (
    <div
      className="pointer-events-none absolute"
      style={{
        left: outer.x,
        top: outer.y,
        width: outer.w,
        height: outer.h,
        zIndex: 30,
        opacity: visible ? 1 : 0,
        // Opacity only. The band itself appears by the stage snapping smaller
        // (see Hud), which is a layout change and is taken in one frame rather
        // than animated — twenty cards mid-transition is the layer storm.
        transition: 'opacity 420ms ease-out',
      }}
    >
      <svg
        className="absolute inset-0"
        width={outer.w}
        height={outer.h}
        viewBox={`${outer.x} ${outer.y} ${outer.w} ${outer.h}`}
        aria-hidden
      >
        {racers.map(({ s, oval }) => (
          <path
            key={s.arm}
            d={lapPath(oval)}
            fill="none"
            stroke={alpha(NEO4J.periwinkle, 0.22)}
            strokeWidth={Math.max(1, band * 0.02)}
            strokeDasharray={`${band * 0.22} ${band * 0.22}`}
          />
        ))}
        {/* Start / finish, at the bottom centre where the lap begins. */}
        <line
          x1={inner.x + inner.w / 2}
          y1={inner.y + inner.h + band * 0.06}
          x2={inner.x + inner.w / 2}
          y2={inner.y + inner.h + band * 0.94}
          stroke={alpha(NEO4J.cream, 0.4)}
          strokeWidth={Math.max(1, band * 0.05)}
        />
      </svg>

      {/* What the track is showing, along the top band — opposite the start
          line, and under the racers, who pass over it twice a lap. A lap that
          does not say whether it is live, replayed, or waiting for its first
          graded attempt is just an animation. */}
      <div
        className="font-pixel absolute text-center"
        style={{
          left: 0,
          top: inner.y - outer.y - band,
          width: outer.w,
          height: band,
          lineHeight: `${band}px`,
          fontSize: Math.max(9, band * 0.34),
          letterSpacing: '0.08em',
          color: alpha(NEO4J.cream, 0.5),
        }}
      >
        {caption(clock, warm, cold, laps)}
      </div>

      {racers.map(({ s, oval, art }) => {
        const p = lapPoint(oval, s.t)
        return (
          <div
            key={s.arm}
            ref={refs[s.arm]}
            // Centred on the lane by half its own size; `left/top` stay fixed
            // and only the transform moves, so a lap is composited.
            className="absolute left-0 top-0"
            style={{
              width: token * 1.4,
              height: token,
              // Where it starts, and where it stays under reduced motion.
              // While the race is on, `useLapping` writes this every frame and
              // nothing here re-renders — see the note there.
              transform: `translate(${p.x - outer.x - token * 0.7}px, ${p.y - outer.y - token / 2}px)`,
              transition: s.running ? undefined : `transform ${MOVE}`,
              // A finisher keeps a hot halo, so "parked at the line" reads as
              // won rather than as stopped. A racer whose tree no longer
              // parses is haloed in the alarm colour instead: on the surfaces
              // lap it can be out in front precisely BECAUSE it broke the
              // package, and a race that shows that as winning is a lie.
              filter: `drop-shadow(0 0 ${band * (s.finished ? 0.3 : 0.12)}px ${alpha(
                s.parse && s.parse.ok < s.parse.total
                  ? ALARM
                  : s.arm === 'warm'
                    ? '#ff8205'
                    : withHue('#ff8205', COLD_HUE),
                s.finished ? 0.95 : 0.55,
              )})`,
            }}
            dangerouslySetInnerHTML={{ __html: art }}
          />
        )
      })}
    </div>
  )
}
