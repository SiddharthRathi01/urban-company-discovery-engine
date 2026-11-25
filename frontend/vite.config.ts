import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend (backend/api) runs on :8000. The home screen does not call it yet;
// the proxy is ready for the later screens so the browser never needs the backend URL or any key.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target: env.VITE_API_TARGET ?? "http://localhost:8000", changeOrigin: true } },
    },
  };
});
