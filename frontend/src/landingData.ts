/** Indices and reviews for landing page. Replace with live API when available. */

export interface IndexTick {
  name: string
  value: string
  change: string
  positive: boolean
}

export const INDICES: IndexTick[] = [
  { name: 'Nifty 50', value: '24,512.30', change: '+0.42%', positive: true },
  { name: 'Sensex', value: '80,245.60', change: '+0.38%', positive: true },
  { name: 'Nifty Bank', value: '52,100.40', change: '-0.12%', positive: false },
]

export interface Review {
  quote: string
  author: string
  role: string
}

export const REVIEWS: Review[] = [
  {
    quote: 'Saves me hours every week. The concall summaries and financial highlights are exactly what I need.',
    author: 'Priya M.',
    role: 'Fund Manager',
  },
  {
    quote: 'Clean reports with ROE, ROCE and sectoral view in one place. Great for quick screening.',
    author: 'Rahul K.',
    role: 'Research Analyst',
  },
  {
    quote: 'Finally, equity research that doesn’t drown you in PDFs. The PDF download is a nice touch.',
    author: 'Anita S.',
    role: 'Portfolio Advisor',
  },
]
