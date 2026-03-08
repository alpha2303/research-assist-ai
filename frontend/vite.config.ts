import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
// VITE_BASE_PATH can be set at build time for sub-path deployments
// (e.g. GitHub Pages: "/research-assist-ai/").  Defaults to "/" for local dev.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH ?? '/',
})
