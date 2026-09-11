import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The console talks to the control plane over the same API any other client
// uses. In development Vite proxies /api to the local control plane so the
// browser never needs a second origin; in the container, nginx does the same.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.FSSAI_API_URL ?? "http://127.0.0.1:8080",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
