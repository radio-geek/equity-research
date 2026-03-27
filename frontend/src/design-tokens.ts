/**
 * Maximalism design system: accent rotation and shared constants.
 * Use accentByIndex(i) for section/card color rotation (index % 5).
 */

export const ACCENT_COLORS = [
  '#FF3AF2', // 0: Magenta
  '#00F5D4', // 1: Cyan
  '#FFE600', // 2: Yellow
  '#FF6B35', // 3: Orange
  '#7B2FFF', // 4: Purple
] as const

export type AccentIndex = 0 | 1 | 2 | 3 | 4

export function accentByIndex(index: number): string {
  return ACCENT_COLORS[Number(index) % 5]
}

export const COLORS = {
  background: '#0D0D1A',
  foreground: '#FFFFFF',
  muted: '#2D1B4E',
  borderBase: '#FF3AF2',
  accent: ACCENT_COLORS[0],
  secondary: ACCENT_COLORS[1],
  tertiary: ACCENT_COLORS[2],
  quaternary: ACCENT_COLORS[3],
  quinary: ACCENT_COLORS[4],
  green: '#22c55e',
  red: '#ef4444',
  amber: '#f59e0b',
} as const
