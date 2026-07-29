import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    proxy: {
      "/v1": { target: "http://127.0.0.1:18765", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:18765", changeOrigin: true },
    },
  },
});
