// Vite config: Tailwind v4 plugin, and a dev proxy so the browser only ever talks to its own origin.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 1201,
    proxy: {
      '/api': { target: 'http://localhost:1200', ws: true },
    },
  },
  build: {
    // Small fonts would otherwise be inlined as data: URIs, which the CSP's font-src 'self' blocks.
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 700,
  },
});
