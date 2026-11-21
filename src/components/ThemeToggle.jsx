import { useEffect, useState } from 'react'

export default function ThemeToggle() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('rg_theme', theme)
  }, [theme])
  const dark = theme === 'dark'
  return (
    <button
      className="theme-sw"
      role="switch"
      aria-checked={dark}
      aria-label="Dark mode"
      title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={() => setTheme(dark ? 'light' : 'dark')}
    >
      <span className="thumb">
        {dark ? (
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
            <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" fill="currentColor" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
            <circle cx="12" cy="12" r="4.5" fill="currentColor" />
            <g stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" />
            </g>
          </svg>
        )}
      </span>
    </button>
  )
}
