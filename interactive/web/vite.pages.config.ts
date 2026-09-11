import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/postcss';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

// GitHub Pages serves this project below the repository name and an unlisted
// route. The workflow supplies the full route as PAGES_BASE_PATH; local builds
// continue to work at the web root.
export default defineConfig({
  base: process.env.PAGES_BASE_PATH ?? '/',
  css: { postcss: { plugins: [tailwindcss()] } },
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
    },
  },
  build: {
    outDir: 'dist/pages',
    emptyOutDir: true,
    sourcemap: false,
  },
});
