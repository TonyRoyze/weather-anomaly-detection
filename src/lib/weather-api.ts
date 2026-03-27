import { getWeatherOverview } from '$lib/open-meteo';

import type {
	LocationPreset,
	PredictionMetadata,
	WeatherOverview,
	WeatherPrediction
} from '$lib/types/weather';

const isTauriBuild = import.meta.env.VITE_TAURI_BUILD === '1';
const defaultPythonBaseUrl = 'http://127.0.0.1:8000';
const pythonApiBaseUrl =
	(import.meta.env.VITE_ANOMALIZE_PYTHON_API_URL as string | undefined) ??
	defaultPythonBaseUrl;

let tauriBackendBaseUrlPromise: Promise<string> | null = null;

async function getTauriBackendBaseUrl() {
	if (!isTauriBuild) return pythonApiBaseUrl;
	if (tauriBackendBaseUrlPromise) return tauriBackendBaseUrlPromise;

	tauriBackendBaseUrlPromise = (async () => {
		try {
			const { invoke } = await import('@tauri-apps/api/core');
			const url = await invoke<string>('backend_base_url');
			return url || pythonApiBaseUrl;
		} catch {
			return pythonApiBaseUrl;
		}
	})();

	return tauriBackendBaseUrlPromise;
}

async function readErrorMessage(response: Response) {
	try {
		const payload = (await response.json()) as { message?: string; detail?: string };
		return payload.detail || payload.message || `Request failed with status ${response.status}`;
	} catch {
		return `Request failed with status ${response.status}`;
	}
}

export async function loadAppWeather(city: LocationPreset): Promise<WeatherOverview> {
	if (isTauriBuild) {
		return getWeatherOverview(city.latitude, city.longitude, city.label);
	}

	const params = new URLSearchParams({
		latitude: city.latitude.toString(),
		longitude: city.longitude.toString(),
		label: city.label
	});

	const response = await fetch(`/api/weather?${params.toString()}`);
	if (!response.ok) {
		throw new Error(await readErrorMessage(response));
	}

	return (await response.json()) as WeatherOverview;
}

export async function loadPredictionMetadata(): Promise<PredictionMetadata> {
	const url = isTauriBuild
		? new URL(
				'/api/weather/prediction-metadata',
				await getTauriBackendBaseUrl()
			).toString()
		: '/api/weather/prediction-metadata';

	let response: Response;
	try {
		response = await fetch(url);
	} catch (error) {
		if (isTauriBuild) {
			const baseUrl = await getTauriBackendBaseUrl();
			throw new Error(
				`Unable to reach the Python prediction service at ${baseUrl}.`
			);
		}
		throw error;
	}
	if (!response.ok) {
		throw new Error(await readErrorMessage(response));
	}

	return (await response.json()) as PredictionMetadata;
}

export async function loadWeatherPrediction(options: {
	city: LocationPreset;
	date: string;
	mode: string;
}): Promise<WeatherPrediction> {
	const params = new URLSearchParams({
		latitude: options.city.latitude.toString(),
		longitude: options.city.longitude.toString(),
		label: options.city.label,
		date: options.date,
		mode: options.mode
	});

	const url = isTauriBuild
		? new URL(
				`/api/weather/prediction?${params.toString()}`,
				await getTauriBackendBaseUrl()
			).toString()
		: `/api/weather/predict?${params.toString()}`;

	let response: Response;
	try {
		response = await fetch(url);
	} catch (error) {
		if (isTauriBuild) {
			const baseUrl = await getTauriBackendBaseUrl();
			throw new Error(
				`Unable to reach the Python prediction service at ${baseUrl}.`
			);
		}
		throw error;
	}
	if (!response.ok) {
		throw new Error(await readErrorMessage(response));
	}

	return (await response.json()) as WeatherPrediction;
}
