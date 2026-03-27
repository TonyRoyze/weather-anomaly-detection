import type { WeatherOverview } from '$lib/types/weather';

const FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';

const currentParams = [
	'temperature_2m',
	'apparent_temperature',
	'relative_humidity_2m',
	'wind_speed_10m',
	'surface_pressure',
	'weather_code'
];

const hourlyParams = [
	'temperature_2m',
	'apparent_temperature',
	'relative_humidity_2m',
	'precipitation_probability',
	'precipitation',
	'wind_speed_10m',
	'cloud_cover'
];

const dailyParams = [
	'weather_code',
	'temperature_2m_max',
	'temperature_2m_min',
	'precipitation_sum',
	'wind_speed_10m_max'
];

interface OpenMeteoResponse {
	latitude: number;
	longitude: number;
	elevation: number;
	timezone: string;
	current: {
		time: string;
		temperature_2m: number;
		apparent_temperature: number;
		relative_humidity_2m: number;
		wind_speed_10m: number;
		surface_pressure: number;
		weather_code: number;
	};
	hourly: {
		time: string[];
		temperature_2m: number[];
		apparent_temperature: number[];
		relative_humidity_2m: number[];
		precipitation_probability: number[];
		precipitation: number[];
		wind_speed_10m: number[];
		cloud_cover: number[];
	};
	daily: {
		time: string[];
		weather_code: number[];
		temperature_2m_max: number[];
		temperature_2m_min: number[];
		precipitation_sum: number[];
		wind_speed_10m_max: number[];
	};
}

function average(values: number[]) {
	return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function stdDev(values: number[]) {
	const mean = average(values);
	const variance =
		values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
	return Math.sqrt(variance);
}

function scoreSeverity(score: number, absoluteValue: number, thresholds: [number, number]) {
	if (score >= thresholds[1] || absoluteValue >= thresholds[1]) return 'high' as const;
	if (score >= thresholds[0] || absoluteValue >= thresholds[0]) return 'medium' as const;
	return 'low' as const;
}

function buildAnomalies(hourly: WeatherOverview['hourly']): WeatherOverview['anomalies'] {
	const relevantWindow = hourly.slice(0, 48);
	if (relevantWindow.length === 0) return [];

	const tempValues = relevantWindow.map((entry) => entry.temperature);
	const windValues = relevantWindow.map((entry) => entry.windSpeed);
	const rainValues = relevantWindow.map((entry) => entry.precipitationProbability);

	const tempMean = average(tempValues);
	const tempStd = Math.max(stdDev(tempValues), 0.8);
	const windMean = average(windValues);
	const windStd = Math.max(stdDev(windValues), 1.5);
	const rainMean = average(rainValues);
	const rainStd = Math.max(stdDev(rainValues), 5);

	return relevantWindow
		.flatMap((entry, index) => {
			const anomalies: WeatherOverview['anomalies'] = [];
			const tempScore = Math.abs((entry.temperature - tempMean) / tempStd);
			const windScore = Math.abs((entry.windSpeed - windMean) / windStd);
			const rainScore = Math.abs(
				(entry.precipitationProbability - rainMean) / rainStd
			);

			if (tempScore >= 1.8 && Math.abs(entry.temperature - tempMean) >= 3) {
				const trend = entry.temperature > tempMean ? 'Temperature spike' : 'Temperature dip';
				anomalies.push({
					id: `temp-${index}`,
					time: entry.time,
					title: trend,
					reason: `${entry.temperature.toFixed(1)}°C versus ${tempMean.toFixed(1)}°C short-range baseline`,
					severity: scoreSeverity(tempScore, Math.abs(entry.temperature - tempMean), [2.4, 4.5]),
					metric: 'Temperature',
					value: entry.temperature,
					unit: '°C'
				});
			}

			if (windScore >= 1.7 && entry.windSpeed >= 22) {
				anomalies.push({
					id: `wind-${index}`,
					time: entry.time,
					title: 'Wind surge',
					reason: `${entry.windSpeed.toFixed(1)} km/h with a ${windMean.toFixed(1)} km/h baseline`,
					severity: scoreSeverity(windScore, entry.windSpeed, [26, 34]),
					metric: 'Wind speed',
					value: entry.windSpeed,
					unit: 'km/h'
				});
			}

			if (rainScore >= 1.6 && entry.precipitationProbability >= 70) {
				anomalies.push({
					id: `rain-${index}`,
					time: entry.time,
					title: 'Rain risk jump',
					reason: `${entry.precipitationProbability.toFixed(0)}% probability with ${entry.precipitation.toFixed(1)} mm expected`,
					severity: scoreSeverity(rainScore, entry.precipitationProbability, [80, 92]),
					metric: 'Precipitation probability',
					value: entry.precipitationProbability,
					unit: '%'
				});
			}

			return anomalies;
		})
		.sort((left, right) => {
			const severityWeight = { high: 3, medium: 2, low: 1 };
			return severityWeight[right.severity] - severityWeight[left.severity];
		})
		.slice(0, 6);
}

export async function getWeatherOverview(
	latitude: number,
	longitude: number,
	label: string
): Promise<WeatherOverview> {
	const url = new URL(FORECAST_URL);
	url.searchParams.set('latitude', latitude.toString());
	url.searchParams.set('longitude', longitude.toString());
	url.searchParams.set('timezone', 'auto');
	url.searchParams.set('current', currentParams.join(','));
	url.searchParams.set('hourly', hourlyParams.join(','));
	url.searchParams.set('daily', dailyParams.join(','));
	url.searchParams.set('past_days', '1');
	url.searchParams.set('forecast_days', '5');

	const response = await fetch(url);
	if (!response.ok) {
		throw new Error(`Open-Meteo request failed with status ${response.status}`);
	}

	const data = (await response.json()) as OpenMeteoResponse;

	const hourly = data.hourly.time.map((time, index) => ({
		time,
		temperature: data.hourly.temperature_2m[index],
		apparentTemperature: data.hourly.apparent_temperature[index],
		humidity: data.hourly.relative_humidity_2m[index],
		precipitationProbability: data.hourly.precipitation_probability[index],
		precipitation: data.hourly.precipitation[index],
		windSpeed: data.hourly.wind_speed_10m[index],
		cloudCover: data.hourly.cloud_cover[index]
	}));

	const now = new Date(data.current.time).getTime();
	const currentIndex = Math.max(
		hourly.findIndex((entry) => new Date(entry.time).getTime() >= now),
		0
	);
	const anomalySliceStart = Math.max(currentIndex - 6, 0);

	const normalized: WeatherOverview = {
		location: {
			label,
			latitude: data.latitude,
			longitude: data.longitude,
			timezone: data.timezone,
			elevation: data.elevation
		},
		current: {
			time: data.current.time,
			temperature: data.current.temperature_2m,
			apparentTemperature: data.current.apparent_temperature,
			humidity: data.current.relative_humidity_2m,
			windSpeed: data.current.wind_speed_10m,
			pressure: data.current.surface_pressure,
			weatherCode: data.current.weather_code
		},
		hourly: hourly.slice(anomalySliceStart, anomalySliceStart + 30),
		daily: data.daily.time.map((date, index) => ({
			date,
			weatherCode: data.daily.weather_code[index],
			tempMax: data.daily.temperature_2m_max[index],
			tempMin: data.daily.temperature_2m_min[index],
			precipitationSum: data.daily.precipitation_sum[index],
			windSpeedMax: data.daily.wind_speed_10m_max[index]
		})),
		anomalies: buildAnomalies(hourly.slice(currentIndex, currentIndex + 48)),
		source: {
			name: 'Open-Meteo Weather Forecast API',
			url: 'https://open-meteo.com/en/docs'
		}
	};

	return normalized;
}

