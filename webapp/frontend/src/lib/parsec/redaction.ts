const MAX_TECHNICAL_DETAIL_LENGTH = 8_000;

const AUTHORIZATION_ASSIGNMENT = /\b(authorization)(\s*[:=]\s*)([^;,\r\n]+)/gi;
const SECRET_ASSIGNMENT = /\b(token|password|secret|api[_-]?key|apikey|cookie)(\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;&]+)/gi;

export function redactTechnicalDetail(value: string): string;
export function redactTechnicalDetail(value: string | null | undefined): string | null;
export function redactTechnicalDetail(value: string | null | undefined): string | null {
	if (value === null || value === undefined) return null;
	return value
		.replace(AUTHORIZATION_ASSIGNMENT, '$1$2[REDACTED]')
		.replace(SECRET_ASSIGNMENT, '$1$2[REDACTED]')
		.slice(0, MAX_TECHNICAL_DETAIL_LENGTH);
}
