/// <reference types="node" />
import { defineConfig } from 'vitest/config';
import solid from 'vite-plugin-solid';
import { fileURLToPath } from 'node:url';

// The Python backend serves the built output as static files, so `base` stays '/' and the build lands
// somewhere server.py can mount directly. During development Vite serves the UI and proxies /api and /ws
// to the running Python server, so the frontend never needs its own copy of the backend.
const BACKEND = process.env.APHELION_BACKEND ?? 'http://127.0.0.1:8765';

export default defineConfig({
	plugins: [solid()],
	resolve: {
		alias: {
			'~': fileURLToPath(new URL('./src', import.meta.url)),
		},
	},
	server: {
		host: '127.0.0.1',
		port: 5173,
		proxy: {
			'/api': { target: BACKEND, changeOrigin: true, configure(proxy) {
				proxy.on('proxyReq', (request, incoming) => {
					if (!incoming.headers.origin || incoming.headers.origin === `http://${incoming.headers.host}`) request.setHeader('Origin', new URL(BACKEND).origin);
				});
			} },
			'/ws': { target: BACKEND, ws: true, changeOrigin: true, configure(proxy) {
				proxy.on('proxyReqWs', (request, incoming) => {
					if (incoming.headers.origin === `http://${incoming.headers.host}`) request.setHeader('Origin', new URL(BACKEND).origin);
				});
			} },
		},
	},
	build: {
		outDir: 'dist',
		emptyOutDir: true,
		sourcemap: false,
	},
	test: {
		environment: 'jsdom',
		globals: true,
		include: ['src/**/*.test.{ts,tsx}'],
	},
});
