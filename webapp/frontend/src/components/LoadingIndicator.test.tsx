import { render } from 'solid-js/web';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { appState } from '~/store/appStore';
import { dismissParsec } from '~/lib/parsec/coordinator';
import LoadingIndicator from './LoadingIndicator';

afterEach(() => {
	dismissParsec();
	vi.useRealTimers();
	document.body.replaceChildren();
});

describe('LoadingIndicator Parsec lifecycle', () => {
	it('does not flash Parsec feedback for a short completed load', async () => {
		vi.useFakeTimers();
		const host = document.createElement('div');
		const dispose = render(() => (
			<LoadingIndicator label="Loading Radio" tool="lore-editor" reportThroughParsec feedbackKey="entry:radio" />
		), host);

		await vi.advanceTimersByTimeAsync(200);
		dispose();
		await vi.advanceTimersByTimeAsync(500);

		expect(appState.parsecFeedback).toBeNull();
	});

	it('shows delayed Parsec feedback while a slow load remains mounted', async () => {
		vi.useFakeTimers();
		const host = document.createElement('div');
		const dispose = render(() => (
			<LoadingIndicator label="Loading Radio" tool="lore-editor" reportThroughParsec feedbackKey="entry:radio" />
		), host);

		await vi.advanceTimersByTimeAsync(351);

		expect(appState.parsecFeedback?.animation).toBe('fetch');
		expect(appState.parsecFeedback?.text).toContain('Still fetching');
		dispose();
	});
});
