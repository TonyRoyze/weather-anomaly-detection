<script lang="ts">
	import { onMount } from "svelte";
	import SearchableSelect from "$lib/components/searchable-select.svelte";

	import type {
		LocationPreset,
		PredictionMetadata,
		WeatherOverview,
		WeatherPrediction,
	} from "$lib/types/weather";
	import { severityClasses, weatherCodeLabel } from "$lib/weather-utils";
	import {
		loadAppWeather,
		loadPredictionMetadata as loadPredictionMetadataFromApi,
		loadWeatherPrediction,
	} from "$lib/weather-api";

	const fallbackCity: LocationPreset = {
		id: "colombo",
		label: "Colombo",
		latitude: 6.9271,
		longitude: 79.8612,
		elevation: 16,
	};

	let cities = $state<LocationPreset[]>([fallbackCity]);
	let selectedCity = $state<LocationPreset>(fallbackCity);
	let weather = $state<WeatherOverview | null>(null);
	let prediction = $state<WeatherPrediction | null>(null);
	let loading = $state(false);
	let predictionLoading = $state(false);
	let metadataLoading = $state(false);
	let error = $state("");
	let predictionError = $state("");
	let selectedDate = $state("");
	let predictionModes = $state<
		Array<{ value: string; label: string; description: string }>
	>([
		{
			value: "conservative",
			label: "Conservative",
			description: "XGBoost with fewer false alarms",
		},
		{
			value: "sensitive",
			label: "Sensitive",
			description: "Balanced Random Forest with higher anomaly recall",
		},
	]);
	let selectedMode = $state("conservative");
	let datasetDateRange = $state({ min: "", max: "" });

	const cityItems = $derived.by(() =>
		cities.map((city) => ({
			value: city.id,
			label: city.label,
		})),
	);
	const availableDates = $derived.by(
		() => weather?.daily.map((entry) => entry.date) ?? [],
	);
	const forecastMinDate = $derived.by(() => availableDates[0] ?? "");
	const forecastMaxDate = $derived.by(
		() => availableDates[availableDates.length - 1] ?? "",
	);
	const isForecastDate = $derived.by(() =>
		availableDates.includes(selectedDate),
	);

	const humidityAverage = $derived.by(() => {
		if (!weather) return 0;
		const total = weather.hourly.reduce(
			(sum, entry) => sum + entry.humidity,
			0,
		);
		return total / weather.hourly.length;
	});

	function formatDate(value: string) {
		return new Intl.DateTimeFormat("en", {
			weekday: "short",
			month: "short",
			day: "numeric",
		}).format(new Date(value));
	}

	function findCityById(id: string) {
		return cities.find((city) => city.id === id) ?? cities[0] ?? fallbackCity;
	}

	async function loadPredictionMetadata() {
		metadataLoading = true;

		try {
			const metadata = (await loadPredictionMetadataFromApi()) as PredictionMetadata;
			cities = metadata.cities.length > 0 ? metadata.cities : [fallbackCity];
			selectedCity = metadata.defaultCity ?? cities[0] ?? fallbackCity;
			predictionModes = metadata.modes;
			datasetDateRange = metadata.datasetDateRange;
			selectedDate = metadata.datasetDateRange.max;
		} catch (err) {
			console.error(err);
			cities = [fallbackCity];
			selectedCity = fallbackCity;
			datasetDateRange = { min: "", max: "" };
			error =
				err instanceof Error
					? err.message
					: "Prediction metadata is unavailable right now.";
		} finally {
			metadataLoading = false;
		}
	}

	async function loadPrediction(city: LocationPreset, date: string) {
		if (!date) return;

		predictionLoading = true;
		predictionError = "";

		try {
			prediction = (await loadWeatherPrediction({
				city,
				date,
				mode: selectedMode,
			})) as WeatherPrediction;
		} catch (err) {
			console.error(err);
			prediction = null;
			predictionError =
				err instanceof Error
					? err.message
					: "Prediction service is unavailable right now.";
		} finally {
			predictionLoading = false;
		}
	}

	async function loadWeather(city: LocationPreset) {
		selectedCity = city;
		loading = true;
		error = "";
		predictionError = "";
		prediction = null;

		try {
			weather = (await loadAppWeather(city)) as WeatherOverview;
			if (!selectedDate) {
				selectedDate = datasetDateRange.max || weather.daily[0]?.date || "";
			}
			if (selectedDate) {
				selectedDate = coercePredictionDate(selectedDate);
			}
			if (selectedDate) {
				await loadPrediction(city, selectedDate);
			}
		} catch (err) {
			console.error(err);
			error =
				"Weather feed is unavailable right now. Check your network or the Open-Meteo upstream.";
		} finally {
			loading = false;
		}
	}

	async function handleDateChange(event: Event) {
		const nextDate = (event.currentTarget as HTMLInputElement).value;
		selectedDate = nextDate;
		const coercedDate = coercePredictionDate(nextDate);
		if (coercedDate !== nextDate) {
			selectedDate = coercedDate;
		}
		await loadPrediction(selectedCity, selectedDate);
	}

	async function handleCityChange(nextCityId: string) {
		const nextCity = findCityById(nextCityId);
		await loadWeather(nextCity);
	}

	async function handleModeChange(nextMode: string) {
		selectedMode = nextMode;
		if (selectedDate) {
			const coercedDate = coercePredictionDate(selectedDate);
			if (coercedDate !== selectedDate) {
				selectedDate = coercedDate;
			}
			await loadPrediction(selectedCity, selectedDate);
		}
	}

	function coercePredictionDate(value: string) {
		if (!value) return value;

		// Allowed set: historical dataset range OR current forecast window.
		const datasetMin = datasetDateRange.min;
		const datasetMax = datasetDateRange.max;
		const forecastMin = forecastMinDate;
		const forecastMax = forecastMaxDate;

		if (availableDates.includes(value)) return value;

		if (
			datasetMin &&
			datasetMax &&
			value >= datasetMin &&
			value <= datasetMax
		) {
			return value;
		}

		// If user selects a "gap" date (after dataset max but before forecast min),
		// snap to the nearest valid date (forecastMin when available, else datasetMax).
		if (
			datasetMax &&
			forecastMin &&
			value > datasetMax &&
			value < forecastMin
		) {
			return forecastMin || datasetMax;
		}

		// If it's after dataset max and outside forecast window, snap to forecastMin.
		if (
			datasetMax &&
			forecastMin &&
			value > datasetMax &&
			value > forecastMax
		) {
			return forecastMin;
		}

		// If it's before dataset min (should be blocked by the input), snap to datasetMin.
		if (datasetMin && value < datasetMin) return datasetMin;

		return value;
	}

	onMount(() => {
		void (async () => {
			await loadPredictionMetadata();
			await loadWeather(selectedCity);
		})();
	});
</script>

<div class="flex flex-col gap-8">
	<section
		id="dashboard-overview"
		data-testid="dashboard-overview"
		class="grid gap-6 rounded-[2rem] border border-(--theme-border) bg-white/80 p-6 shadow-[0_24px_60px_var(--theme-shadow)] md:grid-cols-[1.6fr_1fr] md:p-8"
	>
		<div class="space-y-5">
			<div
				class="inline-flex rounded-full border border-(--theme-border) bg-(--theme-soft-70) px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-(--theme-accent)"
			>
				Anomaly prediction
			</div>
			<div class="space-y-3">
				<h1
					class="max-w-3xl text-4xl font-semibold tracking-tight text-(--theme-text) md:text-5xl"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Predict anomalies from the full Sri Lanka weather dataset.
				</h1>
				<p class="max-w-2xl text-base leading-7 text-(--theme-text) md:text-lg">
					Choose any city in the dataset and score past dates from the
					historical rows or future dates from the available forecast window.
				</p>
			</div>
		</div>

		<div
			class="hidden rounded-[1.8rem] border border-(--theme-border) bg-(--theme-soft-45) p-6 shadow-(--theme-shadow) md:block"
		>
			<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
				Workspace snapshot
			</div>
			<div class="mt-4 grid gap-3 text-sm text-(--theme-text)">
				<div class="flex items-center justify-between gap-4">
					<div class="text-(--theme-muted)">City</div>
					<div class="font-semibold text-(--theme-text)">
						{selectedCity.label}
					</div>
				</div>
				<div class="flex items-center justify-between gap-4">
					<div class="text-(--theme-muted)">Mode</div>
					<div class="font-semibold text-(--theme-text)">
						{predictionModes.find((mode) => mode.value === selectedMode)
							?.label ?? selectedMode}
					</div>
				</div>
				{#if selectedDate}
					<div class="flex items-center justify-between gap-4">
						<div class="text-(--theme-muted)">Date</div>
						<div class="font-semibold text-(--theme-text)">
							{formatDate(selectedDate)}
						</div>
					</div>
				{/if}
				{#if datasetDateRange.min}
					<div class="text-(--theme-muted)">
						Dataset: {datasetDateRange.min} → {datasetDateRange.max}
					</div>
				{/if}
				<div class="mt-2 flex flex-col gap-2">
					<!-- <a
						href="/dashboard/forecast"
						class="inline-flex items-center justify-center rounded-full border border-(--theme-border) bg-white/80 px-4 py-2 text-sm font-semibold text-(--theme-text) transition hover:border-(--theme-accent) hover:bg-(--theme-soft)"
					>
						Open forecast operations
					</a> -->
					<a
						href="/dashboard/dataset"
						class="inline-flex items-center justify-center rounded-full border border-(--theme-border) bg-white/70 px-4 py-2 text-sm font-semibold text-(--theme-text) transition hover:border-(--theme-accent) hover:bg-(--theme-soft)"
					>
						Browse dataset
					</a>
				</div>
			</div>
		</div>
	</section>

	{#if error}
		<div
			class="rounded-3xl border border-(--theme-accent) bg-(--theme-soft) px-5 py-4 text-sm text-(--theme-text)"
		>
			{error}
		</div>
	{/if}

	{#if metadataLoading && !weather}
		<div
			class="rounded-[2rem] border border-(--theme-border) bg-white/80 p-10 text-center text-(--theme-text) shadow-(--theme-shadow)"
		>
			Loading dataset cities and prediction controls...
		</div>
	{:else if weather}
		<section
			id="dashboard-summary"
			data-testid="dashboard-summary"
			class="grid gap-4 grid-cols-3"
		>
			<div
				id="dashboard-summary-temperature"
				data-testid="dashboard-summary-temperature"
				class="rounded-[1.8rem] border border-(--theme-border) bg-white/85 p-5 shadow-(--theme-shadow)"
			>
				<div class="text-sm text-(--theme-muted)">Current temperature</div>
				<div
					class="mt-3 text-4xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					{weather.current.temperature.toFixed(1)}°C
				</div>
				<div class="mt-2 text-sm text-(--theme-text)">
					Feels like {weather.current.apparentTemperature.toFixed(1)}°C
				</div>
			</div>
			<div
				id="dashboard-summary-wind"
				data-testid="dashboard-summary-wind"
				class="rounded-[1.8rem] border border-(--theme-border) bg-white/85 p-5 shadow-(--theme-shadow)"
			>
				<div class="text-sm text-(--theme-muted)">Wind and pressure</div>
				<div
					class="mt-3 text-2xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					{weather.current.windSpeed.toFixed(1)} km/h
				</div>
				<div class="mt-2 text-sm text-(--theme-text)">
					{weather.current.pressure.toFixed(0)} hPa surface pressure
				</div>
			</div>
			<div
				id="dashboard-summary-humidity"
				data-testid="dashboard-summary-humidity"
				class="rounded-[1.8rem] border border-(--theme-border) bg-white/85 p-5 shadow-(--theme-shadow)"
			>
				<div class="text-sm text-(--theme-muted)">Humidity trend</div>
				<div
					class="mt-3 text-2xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					{humidityAverage.toFixed(0)}%
				</div>
				<div class="mt-2 text-sm text-(--theme-text)">
					Average over the 30-hour dashboard window
				</div>
			</div>
		</section>

		<section
			id="dashboard-prediction-grid"
			data-testid="dashboard-prediction-grid"
			class="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]"
		>
			<div
				id="dashboard-prediction-controls"
				data-testid="dashboard-prediction-controls"
				class="rounded-[2rem] border border-(--theme-border) bg-(--theme-soft-60) p-6 shadow-(--theme-shadow)"
			>
				<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
					Prediction controls
				</div>
				<h2
					class="mt-2 text-2xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Choose any city and date
				</h2>
				<p class="mt-2 text-sm leading-6 text-(--theme-text)">
					Past dates use the dataset directly. Dates inside the current forecast
					window use the live forecast for that city.
				</p>

				<div
					class="mt-5 block text-sm font-medium text-(--theme-text)"
					id="prediction-city-label"
				>
					City
				</div>
				<SearchableSelect
					triggerId="prediction-city"
					triggerTestId="prediction-city"
					labelledBy="prediction-city-label"
					items={cityItems}
					value={selectedCity.id}
					placeholder="Search city..."
					emptyMessage="No matching cities found."
					inputClass="mt-2 h-auto rounded-2xl border border-(--theme-border) bg-white px-4 py-3 text-sm text-(--theme-text) outline-none transition placeholder:text-(--theme-muted) focus:border-(--theme-accent) focus:ring-4 focus:ring-[var(--theme-soft-45)]"
					contentClass="border border-(--theme-border) bg-white"
					itemClass="text-(--theme-text) data-highlighted:bg-(--theme-soft) data-highlighted:text-(--theme-text)"
					onValueChange={handleCityChange}
				/>

				<label
					class="mt-5 block text-sm font-medium text-(--theme-text)"
					for="prediction-date"
				>
					Date
				</label>
				<input
					id="prediction-date"
					data-testid="prediction-date"
					type="date"
					class="mt-2 w-full rounded-2xl border border-(--theme-border) bg-white px-4 py-3 text-sm text-(--theme-text) outline-none transition focus:border-(--theme-accent)"
					bind:value={selectedDate}
					min={datasetDateRange.min || undefined}
					max={availableDates[availableDates.length - 1] ||
						datasetDateRange.max ||
						undefined}
					onchange={handleDateChange}
				/>

				{#if selectedDate}
					<div class="mt-3 text-sm text-(--theme-text)">
						Selected: {formatDate(selectedDate)}
					</div>
				{/if}

				{#if datasetDateRange.min}
					<div class="mt-2 text-sm text-(--theme-muted)">
						Dataset range: {datasetDateRange.min} to {datasetDateRange.max}
					</div>
				{/if}

				<div class="mt-2 text-sm text-(--theme-muted)">
					Current source: {isForecastDate
						? "Live forecast"
						: "Historical dataset"}
				</div>

				<div
					class="mt-5 block text-sm font-medium text-(--theme-text)"
					id="prediction-mode-label"
				>
					Prediction mode
				</div>
				<SearchableSelect
					triggerId="prediction-mode"
					triggerTestId="prediction-mode"
					labelledBy="prediction-mode-label"
					items={predictionModes}
					value={selectedMode}
					placeholder="Search mode..."
					emptyMessage="No matching modes found."
					inputClass="mt-2 h-auto rounded-2xl border border-(--theme-border) bg-white px-4 py-3 text-sm text-(--theme-text) outline-none transition placeholder:text-(--theme-muted) focus:border-(--theme-accent) focus:ring-4 focus:ring-[var(--theme-soft-45)]"
					contentClass="border border-(--theme-border) bg-white"
					itemClass="text-(--theme-text) data-highlighted:bg-(--theme-soft) data-highlighted:text-(--theme-text)"
					onValueChange={handleModeChange}
				/>
				<div class="mt-2 text-sm text-(--theme-muted)">
					{predictionModes.find((mode) => mode.value === selectedMode)
						?.description}
				</div>

				<div
					id="dashboard-model-summary"
					data-testid="dashboard-model-summary"
					class="mt-5 rounded-3xl border border-(--theme-border) bg-white p-4 text-sm text-(--theme-text)"
				>
					<div class="font-semibold text-(--theme-text)">Models in use</div>
					<div class="mt-2">
						Binary anomaly prediction: {selectedMode === "sensitive"
							? "Balanced Random Forest"
							: "XGBoost"}
					</div>
					<div class="mt-1">Category prediction: XGBoost</div>
				</div>
			</div>

			<div
				id="dashboard-prediction-results"
				data-testid="dashboard-prediction-results"
				class="rounded-[2rem] border border-(--theme-border) bg-white/80 p-6 shadow-(--theme-shadow)"
			>
				<div class="flex flex-wrap items-end justify-between gap-3">
					<div>
						<div
							class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)"
						>
							Python prediction
						</div>
						<h2
							class="mt-2 text-2xl font-semibold text-(--theme-text)"
							style="font-family: Georgia, 'Times New Roman', serif;"
						>
							Selected date anomaly result
						</h2>
					</div>
					{#if prediction}
						<div
							class={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.18em] ${severityClasses(prediction.anomalyPrediction.severity)}`}
						>
							{prediction.anomalyPrediction.severity}
						</div>
					{/if}
				</div>

				{#if predictionError}
					<div
						class="mt-5 rounded-3xl border border-(--theme-accent) bg-(--theme-soft) px-5 py-4 text-sm text-(--theme-text)"
					>
						{predictionError}
					</div>
				{:else if predictionLoading}
					<div
						class="mt-5 rounded-3xl border border-(--theme-border) bg-(--theme-soft) px-5 py-4 text-sm text-(--theme-text)"
					>
						Scoring the selected date with the Python models...
					</div>
				{:else if prediction}
					<div class="mt-5 grid gap-4 md:grid-cols-3">
						<div
							class="rounded-[1.6rem] border border-(--theme-border) bg-(--theme-soft-45) p-5"
						>
							<div class="text-sm text-(--theme-muted)">Anomaly status</div>
							<div
								class="mt-3 text-2xl font-semibold text-(--theme-text)"
								style="font-family: Georgia, 'Times New Roman', serif;"
							>
								{prediction.anomalyPrediction.isAnomaly
									? "Anomaly"
									: "Normal pattern"}
							</div>
							<div class="mt-2 text-sm text-(--theme-text)">
								Probability {(
									prediction.anomalyPrediction.probability * 100
								).toFixed(1)}%
							</div>
						</div>
						<div
							class="rounded-[1.6rem] border border-(--theme-border) bg-(--theme-soft-45) p-5"
						>
							<div class="text-sm text-(--theme-muted)">Predicted category</div>
							<div
								class="mt-3 text-2xl font-semibold text-(--theme-text)"
								style="font-family: Georgia, 'Times New Roman', serif;"
							>
								{prediction.categoryPrediction.label}
							</div>
							<div class="mt-2 text-sm text-(--theme-text)">
								Confidence {(
									prediction.categoryPrediction.confidence * 100
								).toFixed(1)}%
							</div>
						</div>
						<div
							class="rounded-[1.6rem] border border-(--theme-border) bg-(--theme-soft-45) p-5"
						>
							<div class="text-sm text-(--theme-muted)">Dominant signal</div>
							<div
								class="mt-3 text-2xl font-semibold text-(--theme-text)"
								style="font-family: Georgia, 'Times New Roman', serif;"
							>
								{prediction.categoryPrediction.dominantSignal}
							</div>
							<div class="mt-2 text-sm text-(--theme-text)">
								{prediction.predictionSource === "forecast"
									? "Forecast-based inference"
									: "Historical dataset"}
							</div>
						</div>
					</div>

					<div class="mt-5 grid gap-4 md:grid-cols-3">
						{#each prediction.signals as signal}
							<div
								class="rounded-3xl border border-(--theme-border) bg-(--theme-soft-30) p-4"
							>
								<div class="text-sm font-semibold text-(--theme-text)">
									{signal.metric}
								</div>
								<div class="mt-2 text-sm text-(--theme-text)">
									Deviation score {signal.zScore.toFixed(2)}
								</div>
							</div>
						{/each}
					</div>

					<div
						class="mt-5 rounded-3xl border border-(--theme-border) bg-(--theme-soft-30) p-5"
					>
						<div class="text-sm font-semibold text-(--theme-text)">
							Features used for this prediction
						</div>
						<div
							class="mt-3 grid gap-3 text-sm text-(--theme-text) md:grid-cols-2 xl:grid-cols-4"
						>
							<div>
								Mean temp: {prediction.features.temperatureMean.toFixed(1)}°C
							</div>
							<div>
								Rain: {prediction.features.precipitationSum.toFixed(1)} mm
							</div>
							<div>
								Rain hours: {prediction.features.precipitationHours.toFixed(1)} h
							</div>
							<div>
								Wind max: {prediction.features.windSpeedMax.toFixed(1)} km/h
							</div>
							<div>
								Wind dir: {prediction.features.windDirectionDominant.toFixed(
									0,
								)}°
							</div>
							<div>
								Radiation: {prediction.features.shortwaveRadiationSum.toFixed(
									1,
								)}
							</div>
							<div>
								ET0: {prediction.features.et0FaoEvapotranspiration.toFixed(2)}
							</div>
							<!-- <div>
								{prediction.modelSummary.anomalyModel} / {prediction.modelSummary.categoryModel}
							</div> -->
						</div>
					</div>
				{/if}
			</div>
		</section>
	{:else if loading}
		<div
			class="rounded-[2rem] border border-(--theme-border) bg-white/80 p-10 text-center text-(--theme-text) shadow-(--theme-shadow)"
		>
			Loading forecast and anomaly signals...
		</div>
	{/if}
</div>
