/**
 * Race mode, as context rather than props.
 *
 * The Slay button lives on the home CARD, so a card needs to be able to arm
 * the race — but `SlideProps` is the contract every one of the twenty cards
 * signs, and threading HUD chrome state through it would put two fields about
 * a racetrack on a card that renders a log tail. Same shape as `RunFeed`:
 * whoever needs it asks for it.
 */
import { createContext, useContext, type ReactNode } from 'react'

export interface RaceMode {
  racing: boolean
  slay: () => void
}

const RaceContext = createContext<RaceMode>({ racing: false, slay: () => {} })

export function RaceProvider({
  value,
  children,
}: {
  value: RaceMode
  children: ReactNode
}) {
  return <RaceContext.Provider value={value}>{children}</RaceContext.Provider>
}

export function useRace(): RaceMode {
  return useContext(RaceContext)
}
