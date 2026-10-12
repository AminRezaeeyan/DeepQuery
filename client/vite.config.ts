import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Django API runs on :8000. Proxying keeps the app same-origin in
// development, so no CORS configuration is needed.
const API_TARGET = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": API_TARGET,
      "/auth": API_TARGET,
    },
  },
});
