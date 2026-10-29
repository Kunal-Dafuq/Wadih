import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // Forward API calls to the FastAPI backend in development (override with VITE_API_PROXY).
    proxy: { '/api': process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000' },
  },
  // three.js is lazy-loaded with the hero scene, so its size does not block first paint.
  build: { chunkSizeWarningLimit: 600 },
});
