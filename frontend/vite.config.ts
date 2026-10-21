import path from "node:path"
import { fileURLToPath } from "node:url"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

const rootDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(rootDir, "..")

export default defineConfig({
  // Load VITE_* vars from the monorepo root .env (same file Django uses).
  envDir: repoRoot,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
})
