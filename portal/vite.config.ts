import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import { defineConfig } from "vite";
import viteReact from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";

// Nitro's dev worker can stall the SSR environment on current Vite 8.
// Production builds (including Vercel) still go through Nitro.
const building = process.env.npm_lifecycle_event === "build";

export default defineConfig({
  server: {
    port: 3000,
  },
  resolve: {
    tsconfigPaths: true,
  },
  plugins: [tanstackStart(), building ? nitro() : null, viteReact()].filter(
    (plugin) => plugin != null,
  ),
});
