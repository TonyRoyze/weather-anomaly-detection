import { getWeatherOverview } from '$lib/server/open-meteo';
import { json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';

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

export const GET: RequestHandler = async ({ url }) => {
	const latitude = parseCoordinate(url.searchParams.get('latitude'), defaults.latitude);
	const longitude = parseCoordinate(url.searchParams.get('longitude'), defaults.longitude);
	const label = url.searchParams.get('label')?.trim() || defaults.label;

	try {
		const overview = await getWeatherOverview(latitude, longitude, label);
		return json(overview);
	} catch (error) {
		console.error('weather proxy failed', error);
		return json(
			{
				message: 'Unable to load weather data from Open-Meteo right now.'
			},
			{ status: 502 }
		);
	}
};
