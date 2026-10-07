/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#101114",
        panel: "#1a1d24",
        line: "#31353d",
        paper: "#ece8e1",
        mute: "#a39e94",
        tide: "#9bb8c9",
        clay: "#d2b48a",
        fault: "#e07a6a",
        moss: "#8fae96",
      },
      fontFamily: {
        serif: ["Fraunces", "Georgia", "serif"],
        sans: ["Outfit", "sans-serif"],
      },
    },
  },
  plugins: [],
};
