import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Local dev without Docker: `npm run dev` proxies API calls to a
    // locally running FastAPI (uvicorn) on :8000. In Docker/Kubernetes,
    // nginx does this proxying instead (see nginx.conf).
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
