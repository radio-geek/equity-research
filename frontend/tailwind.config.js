/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0D0D1A',
        foreground: '#FFFFFF',
        muted: '#2D1B4E',
        accent: '#FF3AF2',
        secondary: '#00F5D4',
        tertiary: '#FFE600',
        quaternary: '#FF6B35',
        quinary: '#7B2FFF',
      },
      fontFamily: {
        heading: ['Outfit', 'system-ui', 'sans-serif'],
        body: ['DM Sans', 'system-ui', 'sans-serif'],
        display: ['Bangers', 'cursive'],
      },
      borderRadius: {
        card: '1.5rem',
        container: '1rem',
      },
    },
  },
  plugins: [],
}
