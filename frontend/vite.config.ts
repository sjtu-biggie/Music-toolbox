import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/audio": "http://localhost:8000",
      "/midi": "http://localhost:8000",
      "/ai": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
