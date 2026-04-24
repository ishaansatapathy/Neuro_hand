/** Shared landing-page anchors (Hero, Footer) — one source of truth */
export const LANDING_ANCHOR_LINKS = [
  { label: 'Problem', href: '#problem' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Features', href: '#features' },
  { label: 'Stack', href: '#tech' },
  { label: 'Impact', href: '#stats' },
] as const

/** Hero top nav: subset with optional chevron (product-marketing style) */
export const HERO_NAV_ITEMS: {
  label: string
  href: string
  chevron?: boolean
}[] = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Features', href: '#features', chevron: true },
  { label: 'Stack', href: '#tech', chevron: true },
  { label: 'Impact', href: '#stats' },
]
