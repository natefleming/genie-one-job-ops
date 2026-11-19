import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds into ../static, which the FastAPI app serves. In dev, /api is proxied to a local uvicorn.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../static", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8000" } },
});
