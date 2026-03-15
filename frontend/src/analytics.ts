/**
 * Umami analytics integration (optional).
 * Free: self-host or use cloud hobby tier (10K events/month, 3 websites).
 * Set VITE_UMAMI_URL and VITE_UMAMI_WEBSITE_ID to enable.
 */

const UMAMI_URL = import.meta.env.VITE_UMAMI_URL as string | undefined
const WEBSITE_ID = import.meta.env.VITE_UMAMI_WEBSITE_ID as string | undefined

declare global {
  interface Window {
    umami?: {
      track: (payloadOrEvent?: object | string, eventData?: Record<string, string | number>) => void
    }
  }
}

let scriptLoaded = false
let scriptTagAdded = false

type QueuedPageview = { type: 'pageview'; url: string }
type QueuedEvent = { type: 'event'; name: string; data?: Record<string, string> }
const queue: (QueuedPageview | QueuedEvent)[] = []

function flushQueue(): void {
  if (typeof window === 'undefined' || !window.umami) return
  while (queue.length > 0) {
    const item = queue.shift()
    if (!item) break
    if (item.type === 'pageview') {
      window.umami.track({ website: WEBSITE_ID!, url: item.url })
    } else {
      window.umami.track(item.name, item.data)
    }
  }
}

function loadScript(): void {
  if (!UMAMI_URL || !WEBSITE_ID) return
  if (scriptTagAdded) return
  scriptTagAdded = true
  const script = document.createElement('script')
  script.async = true
  script.src = UMAMI_URL.replace(/\/$/, '') + '/script.js'
  script.setAttribute('data-website-id', WEBSITE_ID)
  script.setAttribute('data-auto-track', 'false')
  script.onload = () => {
    scriptLoaded = true
    flushQueue()
  }
  document.head.appendChild(script)
}

/**
 * Call once on app mount so the script starts loading immediately.
 */
export function initAnalytics(): void {
  loadScript()
}

/**
 * Track a page view (for SPA route changes). Uses Umami pageview API:
 * umami.track() = current URL, or umami.track({ url }) for custom path.
 * Queued until script loads so nothing is dropped.
 */
export function trackPageView(path: string): void {
  if (!UMAMI_URL || !WEBSITE_ID) return
  loadScript()
  if (scriptLoaded && typeof window !== 'undefined' && window.umami) {
    window.umami.track({ website: WEBSITE_ID!, url: path })
  } else {
    queue.push({ type: 'pageview', url: path })
  }
}

/**
 * Track a custom event (e.g. "Report Downloaded", "Feedback").
 * Queued until script loads so nothing is dropped.
 */
export function trackEvent(name: string, data?: Record<string, string>): void {
  if (!UMAMI_URL || !WEBSITE_ID) return
  loadScript()
  if (scriptLoaded && typeof window !== 'undefined' && window.umami) {
    window.umami.track(name, data)
  } else {
    queue.push({ type: 'event', name, data })
  }
}

export function isAnalyticsEnabled(): boolean {
  return Boolean(UMAMI_URL && WEBSITE_ID)
}
