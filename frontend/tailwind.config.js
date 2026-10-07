/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0B0D10",
        elevated: "#11141A",
        surface: "#161A22",
        panel: "#161A22",
        line: "#2A303A",
        paper: "#F4F1EA",
        mute: "#9AA3B2",
        tide: "#8FB4C8",
        clay: "#C6A36A",
        fault: "#D37B6E",
        moss: "#7EAE96",
        unknown: "#8E86A8",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "16px",
        control: "12px",
      },
    },
  },
  plugins: [],
};
