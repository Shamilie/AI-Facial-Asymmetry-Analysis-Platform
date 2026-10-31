import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

const reactPlugins = react().map((plugin) => {
  if (plugin && typeof plugin === 'object' && 'options' in plugin) {
    const copy = { ...plugin };
    delete (copy as Record<string, unknown>).options;
    return copy;
  }
  return plugin;
});

export default defineConfig({
  plugins: [...reactPlugins, tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  build: {
    chunkSizeWarningLimit: 2000,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
});
