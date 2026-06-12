/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './frontend/templates/**/*.html',
    './frontend/static/js/**/*.js',
  ],
  // Classes applied dynamically via JS (classList.add/toggle) must be
  // safelisted so they are not purged from the compiled output.
  safelist: ['hidden', 'text-orange-500'],
  theme: {
    extend: {
      fontFamily: {
        serif: ['Georgia', 'Cambria', 'Times New Roman', 'serif'],
        sans: [
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: ['Consolas', 'Monaco', 'Courier New', 'monospace'],
      },
      colors: {
        mmci: {
          cyan: '#53c0d7',
          orange: '#f04600',
          blue: '#007fc8',
          yellow: '#fbeebc',
          dark: '#1a2332',
          'cyan-light': '#e8f7fb',
          'cyan-border': '#9ddcea',
          'orange-light': '#fdeee7',
          'orange-border': '#f9bfa8',
          'blue-light': '#e0f0fb',
          'blue-border': '#6dc0eb',
        },
        'page-bg': '#f8f9fa',
        'outer-bg': '#eef2f7',
        'site-border': '#e5e7eb',
        layer1: '#f3f4f6',
        'layer1-border': '#e5e7eb',
        layer2: '#e8f7fb',
        'layer2-border': '#9ddcea',
        txt: '#374151',
        'txt-muted': '#4b5563',
      },
    },
  },
  plugins: [],
};
