/**
 * The two prompts, verbatim, and where they stop being the same.
 *
 * `_task_prompt` in orchestrator/vibe_agent.py builds one list of steps and
 * inserts three more when memory is on. Three cards render that: Cold shows
 * the cold branch, Warm the warm branch, and RadixAttention shows the point
 * where the two diverge — which is the point below which the prefix cache
 * cannot be shared between the arms.
 *
 * ONE COPY, because the third card MEASURES the other two. A divergence
 * index computed from a second, hand-kept copy of the text would be a number
 * about this file rather than about the harness, and it would go stale the
 * first time a step was reworded on one card and not the other.
 */

export const PROMPT_HEAD =
  'Please migrate this codebase from Pydantic v1 to Pydantic v2.'

/** The steps both arms get, in order, with warm's insertions marked below. */
export const COLD_STEPS = [
  'Review the entire codebase, so you understand how everything is connected.',
  'Use web_lookup to review the Pydantic docs, specifically those about migration.',
  'Plan the migration before you change any code.',
  'Edit the plan in accordance with that new information.',
  'Make your edits.',
  'When you are finished, your code will be validated externally. You will receive the errors from the test suite.',
  'Review any errors.',
  'Now research those errors with web_lookup.',
  'Review the codebase again.',
  'Make a new plan to fix only these errors.',
  'Continue iteratively until the migration is complete.',
]

export const WARM_STEPS = [
  'Review the entire codebase, so you understand how everything is connected.',
  'Use web_lookup to review the Pydantic docs, specifically those about migration.',
  'Plan the migration before you change any code.',
  'Use your memory tools to see what other agents have attempted before and what they failed on.',
  "Review your plan in light of previous agents' mistakes.",
  'Edit the plan in accordance with that new information.',
  'Make your edits.',
  'When you are finished, your code will be validated externally. You will receive the errors from the test suite.',
  'Review any errors.',
  'Now research those errors with web_lookup.',
  'Use your memory tools to understand if any previous agent has received similar errors.',
  'Review the codebase again.',
  'Make a new plan to fix only these errors.',
  'Continue iteratively until the migration is complete.',
]

/** The steps cold never sees, by warm's numbering. Marked, not left to be spotted. */
export const WARM_ONLY = [4, 5, 11]

export const WARM_CLOSING =
  'Note: throughout your work, based on what you say and do, you will ' +
  "receive information about other agents' past attempts. You do not have " +
  'to follow them. They are additional information for you to consider in ' +
  'light of your current actions.'

/** The prompt as the harness assembles it: head, blank line, numbered steps. */
export const assemble = (steps: string[]): string =>
  `${PROMPT_HEAD}\n\n${steps.map((s, i) => `${i + 1}. ${s}`).join('\n')}`

/**
 * How many leading steps are identical in both arms.
 *
 * Three, at the time of writing — warm's first insertion is its step 4. This
 * is counted rather than stated so the diagram cannot drift from the text
 * above it.
 */
export const SHARED_STEPS = (() => {
  let n = 0
  while (
    n < COLD_STEPS.length &&
    n < WARM_STEPS.length &&
    COLD_STEPS[n] === WARM_STEPS[n]
  )
    n++
  return n
})()

/**
 * The longest common leading string of the two assembled prompts, in
 * characters.
 *
 * This is the trunk of the radix tree, near enough: SGLang matches on tokens,
 * not characters, and the tokeniser is not in the browser — so the deck says
 * "characters" and means it. The ratio it produces is what the picture is
 * about, and that ratio does not change materially between the two units.
 */
export const SHARED_PREFIX = (() => {
  const a = assemble(COLD_STEPS)
  const b = assemble(WARM_STEPS)
  let i = 0
  while (i < a.length && i < b.length && a[i] === b[i]) i++
  return a.slice(0, i)
})()

export const COLD_PROMPT_CHARS = assemble(COLD_STEPS).length
export const WARM_PROMPT_CHARS = `${assemble(WARM_STEPS)}\n\n${WARM_CLOSING}`.length
