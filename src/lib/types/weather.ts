export type Severity = 'low' | 'medium' | 'high';

export interface LocationPreset {
	id: string;
	label: string;
	latitude: number;
	longitude: number;
	elevation?: number;
}

export interface PredictionMetadata {
	cities: LocationPreset[];
	datasetDateRange: {
		min: string;
		max: string;
	};
	defaultCity: LocationPreset | null;
	modes: Array<{
		value: string;
		label: string;
		description: string;
	}>;
}

export interface WeatherOverview {
	location: {
		label: string;
		latitude: number;
		longitude: number;
		timezone: string;
		elevation: number;
	};
	current: {
		time: string;
		temperature: number;
		apparentTemperature: number;
		humidity: number;
		windSpeed: number;
		pressure: number;
		weatherCode: number;
	};
	hourly: Array<{
		time: string;
		temperature: number;
		apparentTemperature: number;
		humidity: number;
		precipitationProbability: number;
		precipitation: number;
		windSpeed: number;
		cloudCover: number;
	}>;
	daily: Array<{
		date: string;
		weatherCode: number;
		tempMax: number;
		tempMin: number;
		precipitationSum: number;
		windSpeedMax: number;
		shortwaveRadiationSum: number;
	}>;
	anomalies: Array<{
		id: string;
		time: string;
		title: string;
		reason: string;
		severity: Severity;
		metric: string;
		value: number;
		unit: string;
	}>;
	source: {
		name: string;
		url: string;
	};
}

export interface WeatherPrediction {
	location: {
		label: string;
		latitude: number;
		longitude: number;
		elevation: number;
	};
	selectedDate: string;
	predictionSource: string;
	supportedCities: string[];
	modelSummary: {
		mode: string;
		anomalyModel: string;
		anomalyModelMetric: string;
		categoryModel: string;
		categoryModelMetric: string;
	};
	anomalyPrediction: {
		isAnomaly: boolean;
		probability: number;
		severity: Severity;
	};
	categoryPrediction: {
		label: string;
		confidence: number;
		dominantSignal: string;
	};
	signals: Array<{
		metric: string;
		zScore: number;
	}>;
	features: {
		temperatureMean: number;
		precipitationSum: number;
		precipitationHours: number;
		windSpeedMax: number;
		windDirectionDominant: number;
		shortwaveRadiationSum: number;
		et0FaoEvapotranspiration: number;
	};
}
