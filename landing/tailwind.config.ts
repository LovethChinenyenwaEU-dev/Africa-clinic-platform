import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: { extend: { fontFamily: { sans: ["Arial", "Helvetica", "sans-serif"] }, colors: { med: { navy: "#173b58", blue: "#1977cc", pale: "#eaf5ff", teal: "#18a6a0" } }, boxShadow: { soft: "0 18px 50px rgba(23,59,88,.10)" } } },
  plugins: [require("daisyui")],
  daisyui: { themes: [{ medilab: { primary: "#1977cc", secondary: "#18a6a0", accent: "#52c7c0", neutral: "#173b58", "base-100": "#ffffff", "base-200": "#f5f9fc", "base-300": "#e4edf4", info: "#1977cc", success: "#18a6a0", warning: "#f2b544", error: "#d9534f" } }] }
};
export default config;
