import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

const base = import.meta.env.BASE_URL
const faviconHref = `${base}favicon.svg`
let faviconLink = document.querySelector("link[rel='icon']") as HTMLLinkElement | null
if (!faviconLink) {
  faviconLink = document.createElement('link')
  faviconLink.rel = 'icon'
  faviconLink.type = 'image/svg+xml'
  document.head.appendChild(faviconLink)
}
faviconLink.href = faviconHref

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
