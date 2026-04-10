/**
 * Premium report loading: compact chart, hero %, stage stepper, skeleton KPI strip.
 * Parent owns the top-edge progress bar (role="progressbar"); chart is aria-hidden.
 */

/** Short labels for the horizontal stepper (align with LOADER_STEPS order). */
export const LOADER_STAGE_SHORT_LABELS = ['Resolve', 'Finance', 'Govern', 'Concall', 'Synth'] as const

/** Chart polyline in viewBox 0 0 320 118 */
const LINE_D =
  'M 8 96 L 28 91 L 48 94 L 68 84 L 88 87 L 108 76 L 128 80 L 148 66 L 168 70 L 188 56 L 208 60 L 228 48 L 248 52 L 268 42 L 288 38 L 312 34'

const AREA_D =
  'M 8 102 L 8 96 L 28 91 L 48 94 L 68 84 L 88 87 L 108 76 L 128 80 L 148 66 L 168 70 L 188 56 L 208 60 L 228 48 L 248 52 L 268 42 L 288 38 L 312 34 L 312 102 Z'

const SECONDARY_D =
  'M 8 100 L 40 96 L 72 98 L 104 92 L 136 94 L 168 88 L 200 90 L 232 84 L 264 86 L 296 82 L 312 80'

const SKELETON_TILE_KEYS = ['sk1', 'sk2', 'sk3', 'sk4', 'sk5'] as const

export type ReportLoaderVisualProps = {
  progressPercent: number
  /** Active pipeline step 0..totalStages-1 */
  stageIndex: number
  totalStages: number
  stageLabel: string
}

export function ReportLoaderVisual({
  progressPercent,
  stageIndex,
  totalStages,
  stageLabel,
}: ReportLoaderVisualProps) {
  const pct = Math.max(0, Math.min(100, progressPercent))
  const rounded = Math.round(pct)
  const n = Math.min(totalStages, LOADER_STAGE_SHORT_LABELS.length)
  const active = Math.max(0, Math.min(n - 1, stageIndex))

  return (
    <div className="report-loader-visual report-loader-visual--premium">
      <div className="report-loader-chart-wrap-outer">
        <div className="report-loader-chart-block report-loader-chart-block--compact" aria-hidden>
          <div className="report-loader-terminal-head">
            <span className="report-loader-terminal-title">Multi-agent research</span>
            <span className="report-loader-live">
              <span className="report-loader-live-dot" />
              Live
            </span>
          </div>
          <div className="report-loader-chart-wrap">
            <svg className="report-loader-chart" viewBox="0 0 320 118" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="reportLoaderAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--green)" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="var(--green)" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="reportLoaderScanGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="48" y2="0">
                  <stop offset="0%" stopColor="transparent" />
                  <stop offset="45%" stopColor="var(--accent)" stopOpacity="0.12" />
                  <stop offset="55%" stopColor="var(--accent)" stopOpacity="0.22" />
                  <stop offset="100%" stopColor="transparent" />
                </linearGradient>
              </defs>
              {[22, 46, 70, 94].map((y) => (
                <line key={y} x1="8" y1={y} x2="312" y2={y} vectorEffect="non-scaling-stroke" className="report-loader-gridline" />
              ))}
              <path d={AREA_D} fill="url(#reportLoaderAreaGrad)" className="report-loader-area-path" />
              <path
                d={SECONDARY_D}
                fill="none"
                vectorEffect="non-scaling-stroke"
                className="report-loader-line-secondary"
              />
              <path d={LINE_D} fill="none" vectorEffect="non-scaling-stroke" className="report-loader-line-primary" />
              <g className="report-loader-scan-group">
                <rect x="0" y="12" width="44" height="92" fill="url(#reportLoaderScanGrad)" className="report-loader-scan-rect" />
              </g>
              <circle cx="312" cy="34" r="3.5" className="report-loader-head-dot" />
            </svg>
          </div>
        </div>
      </div>

      <div
        className="report-loader-hero"
        role="status"
        aria-live="polite"
        aria-label={`Report progress ${rounded} percent`}
      >
        <span className="report-loader-hero-pct" aria-hidden>
          {rounded}
          <span className="report-loader-hero-pct-suffix">%</span>
        </span>
        <p className="report-loader-hero-stage">{stageLabel}</p>
      </div>

      <div
        className="report-loader-stepper"
        role="list"
        aria-label="Research pipeline stages"
      >
        {LOADER_STAGE_SHORT_LABELS.map((label, i) => {
          const done = i < active
          const current = i === active
          return (
            <div key={label} className="report-loader-stepper-unit">
              {i > 0 && (
                <div
                  className={`report-loader-step-connector${active > i - 1 ? ' report-loader-step-connector--done' : ''}`}
                  aria-hidden
                />
              )}
              <div className="report-loader-step-item" role="listitem">
                <div
                  className={
                    `report-loader-step-dot${done ? ' report-loader-step-dot--done' : ''}${current ? ' report-loader-step-dot--active' : ''}${!done && !current ? ' report-loader-step-dot--pending' : ''}`
                  }
                />
                <span className="report-loader-step-short-label">{label}</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="report-loader-kpi-skeletons" aria-hidden>
        {SKELETON_TILE_KEYS.map((k) => (
          <div key={k} className="report-loader-kpi-skel">
            <div className="report-loader-kpi-skel-line report-loader-kpi-skel-line--label" />
            <div className="report-loader-kpi-skel-line report-loader-kpi-skel-line--value" />
          </div>
        ))}
      </div>
    </div>
  )
}
