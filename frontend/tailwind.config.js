/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  important: '#root',
  corePlugins: { preflight: false },
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#123B50', light: '#1a5270', dark: '#0d2b3a' },
        teal: { DEFAULT: '#087E8B', light: '#0a9cad', dark: '#066670' },
        background: '#F2F6F8',
      },
    },
  },
  plugins: [],
};
