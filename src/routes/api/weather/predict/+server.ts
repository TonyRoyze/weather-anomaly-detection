import { env } from '$env/dynamic/private';
import { json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';

const PYTHON_API_BASE_URL = env.ANOMALIZE_PYTHON_API_URL ?? 'http://127.0.0.1:8000';

const defaults = {
	latitude: 6.9271,
	longitude: 79.8612,
	label: 'Colombo'
};

function parseCoordinate(value: string | null, fallback: number) {
	if (!value) return fallback;
	const parsed = Number.parseFloat(value);
	return Number.isFinite(parsed) ? parsed : fallback;
}

export const GET: RequestHandler = async ({ url, fetch }) => {
	const latitude = parseCoordinate(url.searchParams.get('latitude'), defaults.latitude);
	const longitude = parseCoordinate(url.searchParams.get('longitude'), defaults.longitude);
	const label = url.searchParams.get('label')?.trim() || defaults.label;
	const date = url.searchParams.get('date')?.trim();
	const mode = url.searchParams.get('mode')?.trim() || 'conservative';

	if (!date) {
		return json({ message: 'A date query parameter is required.' }, { status: 400 });
	}

	const target = new URL('/api/weather/prediction', PYTHON_API_BASE_URL);
	target.searchParams.set('latitude', latitude.toString());
	target.searchParams.set('longitude', longitude.toString());
	target.searchParams.set('label', label);
	target.searchParams.set('date', date);
	target.searchParams.set('mode', mode);

	try {
		const response = await fetch(target);
		const payload = (await response.json()) as Record<string, unknown>;
		return json(payload, { status: response.status });
	} catch (error) {
		console.error('weather prediction proxy failed', error);
		return json(
			{
				message: 'Unable to load weather predictions from the Python sidecar right now.'
			},
			{ status: 502 }
		);
	}
};
