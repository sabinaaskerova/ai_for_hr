/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f4fa',
          100: '#dce6f5',
          200: '#b9cceb',
          300: '#88a9d9',
          400: '#5580c2',
          500: '#3360ab',
          600: '#254c90',
          700: '#1e3a5f',
          800: '#1a3052',
          900: '#152745',
        },
        amber: {
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
