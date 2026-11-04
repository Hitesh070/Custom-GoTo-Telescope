import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        night: {
          bg: "#000000",
          card: "#080101",
          cardAlt: "#100202",
          border: "#2E0505",
          borderLight: "#4D0A0A",
          red: "#FF3333",
          redBright: "#FF4D4D",
          redDim: "#991F1F",
          redLight: "#FFAAAA",
          crimson: "#5C0B0B",
          crimsonDark: "#1A0303",
        },
        slateCustom: {
          bg: "#0D1117",
          card: "#161B22",
          cardAlt: "#21262D",
          border: "#30363D",
          text: "#E6EDF3",
          accent: "#58A6FF",
          green: "#238636",
          red: "#DA3633",
        }
      },
      fontFamily: {
        mono: ["Consolas", "JetBrains Mono", "Courier New", "monospace"],
      }
    },
  },
  plugins: [],
};

export default config;
