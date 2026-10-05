from __future__ import annotations

import re
import secrets
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_WEBSOCKET_BYTES = 4096
LOOPBACK_HOST = re.compile(r'(127\.0\.0\.1|localhost|\[::1\])(?::([0-9]{1,5}))?')


class LocalSessionMiddleware:
	"""One per-launch authorization boundary for every tool's HTTP and live routes.

	The browser receives an HttpOnly, Strict SameSite session cookie from the same-origin
	bootstrap or SPA navigation. Exact Origin checks also reject other loopback ports.
	Cookies are port-scoped by name, so simultaneous app instances do not replace each other.
	This protects the browser boundary; it is not an OS sandbox against the logged-in user.
	"""

	def __init__(self, app: ASGIApp, *, token: str, trusted_origin: str | None = None) -> None:
		self.app = app
		self.token = token
		self.trusted_origin = trusted_origin

	async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
		if scope['type'] not in ('http', 'websocket'):
			await self.app(scope, receive, send)
			return
		headers = Headers(scope=scope)
		hosts = headers.getlist('host')
		host = hosts[0].lower() if len(hosts) == 1 else ''
		match = LOOPBACK_HOST.fullmatch(host)
		origin = f"{'https' if scope.get('scheme') in ('https', 'wss') else 'http'}://{host}"
		origins = headers.getlist('origin')
		valid = bool(match and (match[2] is None or 0 < int(match[2]) <= 65535))
		valid = valid and (self.trusted_origin is None or origin == self.trusted_origin)
		valid = valid and (not origins or origins == [origin])
		# A WS handshake from a browser must identify its origin, even with a valid cookie.
		if scope['type'] == 'websocket' and origins != [origin]:
			valid = False
		if not valid:
			await self._reject(scope, receive, send, 403, 'Request origin is not authorized.')
			return
		port = urlsplit(origin).port or (443 if origin.startswith('https:') else 80)
		cookie_name = f'aphelion-session-{port}'
		credential = HTTPConnection(scope).cookies.get(cookie_name, '')
		authorized = secrets.compare_digest(credential, self.token)
		path = scope['path']
		safe_method = scope.get('method') in ('GET', 'HEAD', 'OPTIONS')
		public = safe_method and path in ('/api/health', '/api/session')
		if (not safe_method or (path.startswith('/api/') and not public)) and not authorized:
			await self._reject(scope, receive, send, 401, 'Open the application to establish a local session.')
			return
		if scope['type'] == 'websocket':
			async def bounded_receive() -> Message:
				message = await receive()
				data = message.get('bytes') or str(message.get('text') or '').encode('utf-8')
				if len(data) > MAX_WEBSOCKET_BYTES:
					await send({'type': 'websocket.close', 'code': 1009})
					return {'type': 'websocket.disconnect', 'code': 1009}
				return message
			await self.app(scope, bounded_receive, send)
			return
		if scope['method'] not in ('GET', 'HEAD', 'OPTIONS'):
			body = bytearray()
			while True:
				message = await receive()
				if message['type'] == 'http.disconnect':
					return
				body.extend(message.get('body', b''))
				if len(body) > MAX_REQUEST_BYTES:
					await self._reject(scope, receive, send, 413, 'Request body is too large.')
					return
				if not message.get('more_body', False):
					break
			original_receive = receive
			delivered = False
			async def buffered_receive() -> Message:
				nonlocal delivered
				if delivered:
					return await original_receive()
				delivered = True
				return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
			receive = buffered_receive
		bootstrap = scope['method'] == 'GET' and (path == '/api/session' or not path.startswith(('/api/', '/assets/')))
		async def session_send(message: Message) -> None:
			if message['type'] == 'http.response.start' and bootstrap:
				cookie = Response()
				cookie.set_cookie(cookie_name, self.token, httponly=True, samesite='strict', secure=origin.startswith('https:'))
				message['headers'] = [*message.get('headers', []), *[(key, value) for key, value in cookie.raw_headers if key == b'set-cookie'], (b'cache-control', b'no-store')]
			await send(message)
		await self.app(scope, receive, session_send)

	@staticmethod
	async def _reject(scope: Scope, receive: Receive, send: Send, status: int, message: str) -> None:
		if scope['type'] == 'websocket':
			await send({'type': 'websocket.close', 'code': 1008})
		else:
			await JSONResponse({'error': message, 'code': 'local_authorization' if status in (401, 403) else 'request_too_large'}, status_code=status)(scope, receive, send)
