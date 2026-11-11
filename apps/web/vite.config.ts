import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the API runs on :8000; the proxy avoids CORS and keeps one origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", globals: true, setupFiles: ["src/test/setup.ts"] },
});
