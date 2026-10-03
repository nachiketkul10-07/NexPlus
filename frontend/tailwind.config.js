/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // PulseOps Slate Dark Design System Tokens
        background: "#191919",
        card: {
          DEFAULT: "#1F1F1F",
          foreground: "#F7F7F7",
        },
        muted: {
          DEFAULT: "#262626",
          foreground: "#A7A7A7",
        },
        primary: {
          DEFAULT: "#E50039",
          foreground: "#FFFFFF",
          accent: "#660019",
        },
        border: "#333333",
        text: {
          primary: "#F7F7F7",
          secondary: "#A7A7A7",
        },
        status: {
          green: "#10B981",
          amber: "#F59E0B",
          red: "#EF4444",
          blue: "#3B82F6",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          '"Liberation Mono"',
          '"Courier New"',
          "monospace",
        ],
      },
    },
  },
  plugins: [],
}
