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
 * ── What the racing means ────────────────────────────────────────────────
 *
 * The lap is the journey each arm has left, and the speed is how close it has
 * got: both are `closeness`, and the arithmetic is under CLOSENESS_PER_SECOND
 * below. Nothing here interpolates, smooths or invents — every number on the
 * track came out of an `ATTEMPT_DONE` line.
 *
 * A racer whose latest attempt left files not parsing is haloed in the alarm
 * colour, and the track says how many still compile. Closeness can be earned
 * by an edit that does not compile, and a race that shows that as winning is
 * a lie.
 *
 * ONLY `FILE_DONE` with `success` stops a racer, on the line, because
 * converging is the oracle's call and nothing else.
 *
 * FIXTURES WITHOUT AN ANSWER KEY report no closeness at all — `_closeness`
 * returns None, and the harness's own chart document omits the panel rather
 * than drawing zeroes. oapi, which the rehearsal loop runs, is one of them. On
 * those the race falls back to tests passing (or v1 surfaces, if the fixture
 * counts them) paced against the leader, and the track says so in those words.
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
 * THE BINDING CONSTRAINT IS THE TOKEN'S WIDTH, NOT ITS HEIGHT. The M is 1.4
 * as wide as it is tall, and on the left and right stretches of the lap the
 * lanes are separated ACROSS that width. The first tuning compared lane
 * separation (0.48 band) against token HEIGHT (0.40) and looked fine; the real
 * comparison is against width, 0.56 — wider than the separation, so the two Ms
 * overlapped by 0.08 band every time they were level, and worse, `2 x 0.56 =
 * 1.12` band meant they could not both fit across the track at all. It only
 * became obvious once they lapped continuously and met constantly.
 *
 *   separation  (0.76 - 0.24) = 0.52 band
 *   token width  1.4 * 0.30   = 0.42 band
 *   clearance                   0.10 band, and 0.03 spare at each edge
 *
 * The band grew to 8% of the stage to pay for the smaller token — see
 * RACE_BAND in hud/Hud.tsx.
 */
const TOKEN = 0.3
const LANES = { cold: 0.24, warm: 0.76 }

/**
 * ── The lap is the journey left; the speed is how close they are ─────────
 *
 * Both come from `closeness`, the harness's own measure of how far along the
 * v1 -> v2 path a tree is: 0.0 is the untouched checkout, 1.0 is the human's
 * merged PR, and negative means the attempt moved AWAY from the answer. It is
 * what the harness itself now judges progress on (`moved = closeness > prior`
 * in vibe_agent.py), where `prior` is the previous attempt's closeness.
 *
 *   TRACK LENGTH  `1 - closeness of the previous attempt` — the journey still
 *                 to run as of where that arm last stood. An arm that was
 *                 nearly there has a short lap and whips round it; one still
 *                 at the start line has the whole distance to cover.
 *
 *   SPEED         `closeness of the latest attempt`, in closeness-units per
 *                 second. Closer to the answer, faster.
 *
 *   laps/second = closeness_now / (1 - closeness_prev)
 *
 * On the run going as this was written that is warm 0.054 over a lap of 0.942
 * — 17s a lap — against cold 0.084 over 0.925, 11s a lap. No display constant
 * in either number: one closeness-unit is one second, and the arithmetic is
 * the whole model.
 *
 * NEGATIVE CLOSENESS RUNS BACKWARDS, because that is what it means. Warm's
 * second attempt in `swarm-1789980175` scored -0.4267: it did not fail to
 * progress, it took the tree further from the answer than the untouched
 * checkout, and a racer that reverses says so better than any caption.
 */
const CLOSENESS_PER_SECOND = 1
/** The shortest a lap may get, so a near-finished arm does not blur. */
const LAP_FAST_S = 6
/**
 * And the slowest. An arm at closeness 0.001 would take twenty minutes a lap,
 * which on stage is indistinguishable from the racer being broken — the fault
 * this whole thing exists to fix. It crawls instead, and its closeness is
 * printed on the track so the crawl is never mistaken for progress.
 */
const LAP_SLOW_S = 45

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
   * Closeness of this arm's latest graded attempt, and of the one before it.
   * `now` is null until it has been graded once; `prev` falls back to 0.0,
   * the untouched checkout, which is the same floor the harness judges the
   * first attempt against.
   */
  closeness: { now: number | null; prev: number }
  /** Seconds to complete one lap. Negative when the arm is going backwards. */
  lapSeconds: number
  /**
   * Fallback pace, 0..1, used only when the fixture reports no closeness:
   * this arm's progress as a fraction of the LEADER's.
   *
   * Absolute share is the wrong thing to drive speed with. On x12sdk warm
   * cleared 60 of 364 surfaces and cold 8 — shares of 0.16 and 0.02, which as
   * lap times are a difference nobody in a room can see, for a run where one
   * arm did seven times the work of the other. Against the leader those
   * become 1.0 and 0.13. The caption prints the raw counts either way.
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

/**
 * Which number the race is made of, in the order it is preferred.
 *
 * `closeness` is the model — see the note at the top. The other two exist
 * because a fixture that ships NO REFERENCE ANSWER reports no closeness at
 * all: `_closeness` returns None, and the harness's own chart document omits
 * the panel rather than drawing zeroes. The rehearsal fixture (oapi) is one of
 * those, so on REHEARSAL the race falls back to what that fixture does report,
 * and the track says which number it is running on.
 */
export type Measure =
  { kind: 'closeness' } | { kind: 'tests' } | { kind: 'surfaces'; baseline: number }

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
    /** Does this fixture have an answer key at all? */
    let hasCloseness = false

    for (const e of events as RunEvent[]) {
      const arm = e.swarm
      if (arm !== 'warm' && arm !== 'cold') continue
      if (e.type === 'ATTEMPT_DONE') {
        const passed = e.tests_passed ?? 0
        // The fallback scales are read from the WHOLE run being shown, not
        // from the prefix replayed so far, so a replay's ends stay put.
        //
        // The floor is the LOWEST anyone reported, not the first. Usually the
        // same number — the first graded attempt is generally the worst — but
        // it cannot be swung by which arm happened to be graded first.
        floor = floor === null ? passed : Math.min(floor, passed)
        target = Math.max(target, passed)
        baseline = Math.max(baseline, e.v1_remaining ?? 0)
        if (typeof e.closeness === 'number') hasCloseness = true
      }
    }

    // SURFACES FIRST, and the reason is what the racers did without it.
    //
    // `closeness` used to win this choice whenever the fixture reported any,
    // which on x12sdk is always. Two things followed, and both were visible
    // on stage. POSITION came from `shareOf`, which under the closeness
    // measure is the TESTS share -- and on swarm-1789987670 warm's best is
    // 64 of 261 against cold's 61, so the two racers sat on top of each
    // other. SPEED came from closeness, which is SIGNED, so warm (positive
    // on nine of ten attempts) ran forward while cold (negative on all ten)
    // ran backwards. Near-identical positions, opposite directions: the
    // race read as arbitrary because neither number was the one the run is
    // judged on.
    //
    // Surfaces cleared is that number, it is monotonic by construction
    // above (`Math.max`), and it separates the arms the way the run does:
    // warm 337 of 383 cleared, cold 160. Both racers then move forward,
    // warm roughly twice as fast, and the gap on the track IS the gap in
    // the data.
    //
    // Closeness has not gone anywhere -- it is on its own card, where a
    // signed number belongs, and the alarm halo below still reads the parse
    // count so clearing surfaces by breaking the package cannot look like
    // winning.
    const measure: Measure =
      baseline > 0
        ? { kind: 'surfaces', baseline }
        : hasCloseness
          ? { kind: 'closeness' }
          : { kind: 'tests' }

    const best: Record<Arm, number> = { warm: 0, cold: 0 }
    const cleared: Record<Arm, number> = { warm: 0, cold: 0 }
    /** Every graded closeness so far, in order: the last two are the model. */
    const close: Record<Arm, number[]> = { warm: [], cold: [] }
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
        // LATEST, not max, and this one has to be. `Math.max` here put a
        // racer at its best-ever position and left it there: on
        // swarm-1789998106 cold cleared all 383 surfaces at attempt 4 with
        // 18 files unimportable, then REVERTED to 365 remaining at attempt
        // 9 to make the package compile -- and the track still showed it
        // parked at the finish line, lapping away into the distance. The
        // run's own story is that it gave the migration back; a race that
        // cannot show that is not showing the data.
        if (typeof e.v1_remaining === 'number') {
          cleared[arm] = baseline - e.v1_remaining
        }
        // Closeness is kept LATEST, not best, and that is the point of it:
        // it is where the tree stands now, and an attempt that made things
        // worse has to be allowed to show as worse.
        if (typeof e.closeness === 'number') close[arm].push(e.closeness)
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
    /**
     * How far along the track an arm is, in ONE unit for both of them.
     *
     * Surfaces cleared, DISCOUNTED BY WHAT IS BROKEN -- the same
     * composition the harness scores a skill run on
     * (cognee_layer.score_from_verdict). Each half alone was gamed today
     * and the track showed it:
     *
     *   surfaces alone   cold reached 0 of 383 with 18 files unimportable
     *                    and sat at the finish line, lapping, while its
     *                    package could not be imported at all.
     *   parsing alone    an untouched v1 tree scores 65/65 having migrated
     *                    nothing.
     *
     * Multiplied, a racer only advances by work that leaves the code
     * standing, which is what both arms are actually being asked to do.
     */
    const shareOf = (arm: Arm) => {
      if (measure.kind !== 'surfaces') {
        return Math.max(0, Math.min(1, (best[arm] - base) / span))
      }
      const done = cleared[arm] / measure.baseline
      const p = parse[arm]
      const intact = p && p.total > 0 ? p.ok / p.total : 1
      return Math.max(0, Math.min(1, done * intact))
    }
    const leader = Math.max(shareOf('warm'), shareOf('cold'))

    /** Seconds per lap, signed. The model, and then the two fallbacks. */
    const lapSecondsFor = (arm: Arm, share: number): number => {
      const c = close[arm]
      let perSecond: number
      if (measure.kind === 'closeness') {
        const now = c.length ? c[c.length - 1] : null
        if (now === null) return LAP_SLOW_S // not graded yet: a crawl
        const prev = c.length > 1 ? c[c.length - 2] : 0
        // Track length: the journey left as of the previous attempt.
        const lapWork = Math.max(0.05, 1 - prev)
        // Speed: how close this attempt got. Both in closeness units.
        perSecond = (CLOSENESS_PER_SECOND * now) / lapWork
      } else {
        // No answer key for this fixture. Pace against the leader instead,
        // which still ranks the arms; the caption names the number.
        const pace = leader > 0 ? share / leader : 0
        perSecond = pace / LAP_FAST_S
      }
      if (perSecond === 0) return LAP_SLOW_S
      const secs = 1 / perSecond
      const clamped = Math.min(LAP_SLOW_S, Math.max(LAP_FAST_S, Math.abs(secs)))
      return secs < 0 ? -clamped : clamped
    }

    const state = (arm: Arm): RacerState => {
      const share = shareOf(arm)
      // The oracle, and only the oracle, puts a racer on the line.
      const frac = done[arm] ? 1 : share * LEAD_CAP
      const c = close[arm]
      return {
        arm,
        passed: best[arm],
        cleared: cleared[arm],
        share,
        closeness: {
          now: c.length ? c[c.length - 1] : null,
          prev: c.length > 1 ? c[c.length - 2] : 0,
        },
        lapSeconds: lapSecondsFor(arm, share),
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

/**
 * What the race says about itself: the standings, then the rule.
 *
 * TWO LINES, because one did not fit. The band is as wide as the stage — 1149
 * canonical units on a 1920 viewport — and the single line this replaced
 * measured 1553, so it hung off both ends of the track.
 */
function caption(
  c: RaceClock,
  warm: RacerState,
  cold: RacerState,
  laps: Record<Arm, number>,
): { top: string; sub: string } {
  const signed = (n: number) => (n >= 0 ? '+' : '−') + Math.abs(n).toFixed(3)
  /** One racer's numbers: what it scored, what that makes it, where it is. */
  const line = (r: RacerState) => {
    const rate = `${Math.round(Math.abs(r.lapSeconds))}s/lap${r.lapSeconds < 0 ? ' BACK' : ''}`
    const score =
      c.measure.kind === 'closeness'
        ? r.closeness.now === null
          ? 'ungraded'
          : `c=${signed(r.closeness.now)}`
        : c.measure.kind === 'surfaces'
          ? `${r.cleared} cleared`
          : `${r.passed} passing`
    // `net`, because a racer that went backwards has a negative lap count and
    // the sign is the point: it is behind where it started.
    const net = laps[r.arm]
    return `${r.arm} ${score} · ${rate} · net ${net < 0 ? '−' : ''}${Math.abs(net)}`
  }
  const measure =
    c.measure.kind === 'closeness'
      ? 'lap = 1−closeness(prev) · speed = closeness(now)'
      : c.measure.kind === 'surfaces'
        ? // "of 364 seen", not "of 383": the untouched count is never emitted,
          // because the first graded attempt has already edited the tree.
          //
          // It no longer says "no closeness on this fixture" -- x12sdk
          // reports closeness and the race simply is not run on it, because
          // it is signed and would send an arm backwards. See the measure
          // choice above.
          `lap = v1 surfaces cleared, of ${c.measure.baseline} seen`
        : 'no closeness on this fixture · tests passing, paced against the leader'
  const graded = c.graded === 0 ? 'no graded attempt yet' : `${c.graded} graded`
  // Closeness can be earned by an edit that does not compile, and the race
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
  return {
    top: [head, line(warm), line(cold)].join(' · '),
    sub: [graded, measure, broken].filter(Boolean).join(' · '),
  }
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
 * AND THE TRANSFORM IS WRITTEN *ONLY* HERE. It was in the JSX too, at the
 * position each arm's progress earned it, and the two writers fought: every
 * re-render — the replay clock ticks four times a second, and a live run's
 * index lands once a second — snapped both tokens back to a fixed spot, and
 * the frame loop crawled away from it again. On screen that is two Ms
 * twitching near two fixed points. Which one looked faster had nothing to do
 * with either arm's progress; it was whichever had the further-round anchor.
 * A ref written from one place, always, is the fix.
 *
 * Speed comes from `pace`: a stalled arm still laps in LAP_SLOW_S, the leader
 * laps in LAP_FAST_S, and the ratio is how fast it pulls away. Distance resets
 * when the race is armed, so every press of Slay starts both on the line.
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

  /** The one place a token's transform is ever written. */
  const place = (arm: Arm, at: number) => {
    const s = now.current
    const p = lapPoint(s.ovals[arm], at)
    const el = refs[arm].current
    if (el) {
      el.style.transform =
        `translate(${p.x - s.origin.x - s.token * 0.7}px, ` +
        `${p.y - s.origin.y - s.token / 2}px)`
    }
  }

  const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    if (!running) {
      dist.current = { warm: 0, cold: 0 }
      setLaps({ warm: 0, cold: 0 })
      return
    }
    // Reduced motion: the racers hold the position their progress earns them,
    // which is the old behaviour and still says who is ahead.
    if (still()) return

    let raf = 0
    let last = performance.now()
    const frame = (t: number) => {
      const dt = Math.min(0.25, (t - last) / 1000)
      last = t
      const s = now.current
      for (const arm of ['cold', 'warm'] as Arm[]) {
        const racer = s[arm]
        // `lapSeconds` is signed: an arm whose latest attempt scored negative
        // closeness took the tree further from the answer, and runs backwards.
        if (racer.running) dist.current[arm] += dt / racer.lapSeconds
        // A converged arm parks on the line. A running one uses the WHOLE lap,
        // 0..1, deliberately: squeezing it into START_T..FINISH_T left a 3% gap
        // at the line that the token hopped across once a lap — measured at
        // ~104px. That inset exists to separate a finisher from a non-starter,
        // and neither is a thing that is moving.
        place(arm, racer.finished ? FINISH_T : dist.current[arm] % 1)
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

  // Parked, or reduced motion, or a resize while parked: place them from their
  // progress. Deliberately on EVERY render rather than on a dependency list —
  // it is two DOM writes, and the alternative is enumerating every value the
  // geometry is derived from and being wrong once.
  useEffect(() => {
    if (running && !still()) return
    place('cold', cold.t)
    place('warm', warm.t)
  })

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

  const says = caption(clock, warm, cold, laps)

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
        className="font-pixel absolute flex flex-col items-center justify-center text-center"
        style={{
          left: 0,
          top: inner.y - outer.y - band,
          width: outer.w,
          height: band,
          lineHeight: 1.15,
          fontSize: Math.max(8, band * 0.29),
          letterSpacing: '0.06em',
          color: alpha(NEO4J.cream, 0.5),
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ color: alpha(NEO4J.cream, 0.72) }}>{says.top}</span>
        <span>{says.sub}</span>
      </div>

      {racers.map(({ s, art }) => {
        return (
          <div
            key={s.arm}
            ref={refs[s.arm]}
            // Centred on the lane by half its own size; `left/top` stay fixed
            // and only the transform moves, so a lap is composited.
            //
            // NO `transform` HERE. `useLapping` owns it — see the note there
            // for what happened when this element set one too.
            className="absolute left-0 top-0"
            style={{
              width: token * 1.4,
              height: token,
              transition: s.running ? 'none' : `transform ${MOVE}`,
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
