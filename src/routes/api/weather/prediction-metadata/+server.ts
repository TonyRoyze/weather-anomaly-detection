import { env } from '$env/dynamic/private';
import { json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';

const PYTHON_API_BASE_URL = env.ANOMALIZE_PYTHON_API_URL ?? 'http://127.0.0.1:8000';

export const GET: RequestHandler = async ({ fetch }) => {
	try {
		const target = new URL('/api/weather/prediction-metadata', PYTHON_API_BASE_URL);
		const response = await fetch(target);
		const payload = (await response.json()) as Record<string, unknown>;
		return json(payload, { status: response.status });
	} catch (error) {
		console.error('prediction metadata proxy failed', error);
		return json(
			{
				message: 'Unable to load prediction metadata from the Python sidecar right now.'
			},
			{ status: 502 }
		);
	}
};
