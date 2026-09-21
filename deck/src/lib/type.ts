/**
 * A floor on type size, in what the audience actually sees.
 *
 * Cards are authored in canonical units and then CSS-scaled to whatever slot
 * they are given, so a size written here is not a size on the glass: 26 units
 * is 16px on a full board, 8px in a quarter slot and 3.7px on a ring tile.
 * Measured across the twenty cards on stage, every one of them was rendering
 * body text between 8px and 15px. That is not small, it is unreadable.
 *
 * `pt(26)` compiles to `max(26px, var(--type-floor))`, and the Hud sets
 * `--type-floor` on each staged card to `16px / scale` — the canonical size
 * that lands at exactly 12pt once the transform is applied. So a card renders
 * at its designed proportions while there is room, and stops shrinking at
 * 12pt. What gives instead is CONTENT: a card in a small slot shows less of
 * itself, clipped, which is the trade this deck already makes everywhere else.
 *
 * ── Tiles are exempt, and that is a physical limit, not a preference ─────
 *
 * The floor is 0 at home. A ring tile is 276x155px on a 1920 screen — at 12pt
 * it holds about seven words. Enforcing it there would replace twenty
 * miniature cards with twenty fragments of a sentence. A tile is a texture
 * that says "something is happening over here"; the board is where reading
 * happens.
 */

/** 12pt, in CSS pixels. 1pt = 4/3px. */
export const MIN_TYPE_PX = 16

/** A font size that never renders smaller than 12pt on stage. */
export const pt = (units: number): string =>
  `max(${units}px, var(--type-floor, 0px))`

/**
 * Same floor, for a box that has to hold floored type — a header bar, a row.
 * `units` is the designed height; `lines` how many lines of 12pt must fit.
 */
export const ptBox = (units: number, lines = 1.4): string =>
  `max(${units}px, calc(var(--type-floor, 0px) * ${lines}))`
