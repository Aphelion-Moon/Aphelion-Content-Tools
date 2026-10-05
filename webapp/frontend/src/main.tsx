/* @refresh reload */
import { render } from 'solid-js/web';
import App from './App';
import './app.css';
import { api } from './lib/api';

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element.');

// Establish the same per-launch session for both the production SPA and Vite proxy
// before mounting API resources or opening the live socket.
async function start() {
	try {
		await api.get('/api/session');
		render(() => <App />, root!);
	} catch (error) {
		root!.textContent = `Unable to connect to Content Tools. ${error instanceof Error ? error.message : 'Please reload to retry.'}`;
		const retry = document.createElement('button');
		retry.textContent = 'Retry connection';
		retry.onclick = () => { root!.replaceChildren(); void start(); };
		root!.append(retry);
	}
}
void start();
