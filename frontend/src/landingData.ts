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
    quote: "Finally, equity research that doesn't drown you in PDFs. The PDF download is a nice touch.",
    author: 'Anita S.',
    role: 'Portfolio Advisor',
  },
]

export interface Feature {
  icon: string
  title: string
  description: string
}

export const FEATURES: Feature[] = [
  {
    icon: '🏢',
    title: 'Company Overview',
    description:
      'Comprehensive business profile with promoter holdings, sector context, and competitive positioning sourced from NSE filings.',
  },
  {
    icon: '📊',
    title: 'QoQ Financials',
    description:
      'Quarter-over-quarter revenue, profit, and margin trends with variance commentary, auto-generated from Yahoo Finance data.',
  },
  {
    icon: '⚠️',
    title: 'Financial Risk Analysis',
    description:
      'Debt-to-equity, interest coverage, contingent liabilities, and cash flow stress indicators flagged automatically.',
  },
  {
    icon: '🔍',
    title: 'Auditor Flag Detection',
    description:
      'Scans annual reports for qualified opinions, emphasis of matter, related-party red flags, and going-concern notes.',
  },
  {
    icon: '🎙️',
    title: 'Concall Evaluation',
    description:
      'Earnings call transcript analysis for management tone, forward guidance, capex signals, and strategic shifts.',
  },
  {
    icon: '📈',
    title: 'Sectoral & Peer View',
    description:
      'Industry headwinds, tailwinds, regulatory changes, and peer benchmarking within the sector landscape.',
  },
]

export interface Step {
  number: string
  title: string
  description: string
}

export const HOW_IT_WORKS: Step[] = [
  {
    number: '01',
    title: 'Search a Stock',
    description: 'Type any NSE-listed company name or symbol. Our engine resolves it instantly.',
  },
  {
    number: '02',
    title: 'AI Analyzes in Parallel',
    description:
      '7 specialized research agents run simultaneously — financials, management, risk, concalls, and more.',
  },
  {
    number: '03',
    title: 'Get Your Report',
    description:
      'A comprehensive equity report is generated in under 2 minutes. Download as PDF or view online.',
  },
]

export interface Stat {
  value: string
  label: string
}

export const STATS: Stat[] = [
  { value: '4,000+', label: 'NSE-Listed Companies' },
  { value: '7', label: 'Research Modules' },
  { value: '<2 min', label: 'Report Generation' },
  { value: '15+', label: 'Report Sections' },
]

export const POPULAR_STOCKS = [
  'RELIANCE',
  'TCS',
  'HDFCBANK',
  'INFY',
  'ICICIBANK',
  'BHARTIARTL',
  'ITC',
  'SBIN',
]
