<script lang="ts">
	import { onMount } from "svelte";
	import SearchableSelect from "$lib/components/searchable-select.svelte";
	import LineChart from "$lib/components/line-chart.svelte";

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
	let dailyPredictions = $state<Record<string, WeatherPrediction>>({});
	let loading = $state(false);
	let metadataLoading = $state(false);
	let predictionLoading = $state(false);
	let error = $state("");
	let predictionError = $state("");
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
	let selectedMetric = $state<
		"temperature" | "precipitationProbability" | "radiation" | "windSpeed"
	>("temperature");

	const cityItems = $derived.by(() =>
		cities.map((city) => ({
			value: city.id,
			label: city.label,
		})),
	);
	const timeline = $derived.by(() => weather?.daily.slice(1, 6) ?? []);
	const metricConfigs = {
		temperature: {
			label: "Temperature",
			unit: "°C",
			color: "var(--theme-accent-strong)",
			bandColor: "var(--theme-soft-45)",
			getValue: (entry: WeatherOverview["daily"][number]) => entry.tempMax,
			minSpread: 1.2,
		},
		precipitationProbability: {
			label: "Rain",
			unit: "%",
			color: "var(--theme-accent)",
			bandColor: "var(--theme-soft-45)",
			getValue: (entry: WeatherOverview["daily"][number]) =>
				entry.precipitationSum,
			minSpread: 8,
		},
		radiation: {
			label: "Radiation",
			unit: "%",
			color: "var(--theme-accent)",
			bandColor: "var(--theme-soft-55)",
			getValue: (entry: WeatherOverview["daily"][number]) => entry.shortwaveRadiationSum,
			minSpread: 6,
		},
		windSpeed: {
			label: "Wind speed",
			unit: "km/h",
			color: "var(--theme-accent-strong)",
			bandColor: "var(--theme-soft-45)",
			getValue: (entry: WeatherOverview["daily"][number]) => entry.windSpeedMax,
			minSpread: 2.5,
		},
	} as const;
	const chartWidth = 720;
	const chartHeight = 280;
	const chartPadding = { top: 16, right: 18, bottom: 34, left: 18 };

	function average(values: number[]) {
		return values.reduce((sum, value) => sum + value, 0) / values.length;
	}

	function stdDev(values: number[]) {
		const mean = average(values);
		const variance =
			values.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
			values.length;
		return Math.sqrt(variance);
	}

	const chartData = $derived.by(() => {
		const config = metricConfigs[selectedMetric];
		const values = timeline.map((entry) => config.getValue(entry));
		if (values.length === 0) {
			return {
				config,
				mean: 0,
				band: 0,
				linePath: "",
				bandPath: "",
				yTicks: [] as number[],
				xTicks: [] as Array<{ label: string; x: number }>,
				domainMin: 0,
				domainMax: 100,
			};
		}

		const mean = average(values);
		const spread = Math.max(stdDev(values) * 0.9, config.minSpread);
		const low = Math.min(...values.map((value) => value - spread));
		const high = Math.max(...values.map((value) => value + spread));
		const domainMin =
			selectedMetric === "precipitationProbability" ||
			selectedMetric === "radiation"
				? Math.max(0, Math.min(low, 0))
				: low;
		const domainMax =
			selectedMetric === "precipitationProbability" ||
			selectedMetric === "radiation"
				? Math.min(100, Math.max(high, 100))
				: high;
		const usableWidth = chartWidth - chartPadding.left - chartPadding.right;
		const usableHeight = chartHeight - chartPadding.top - chartPadding.bottom;
		const xStep = values.length > 1 ? usableWidth / (values.length - 1) : 0;
		const yScale = (value: number) => {
			const span = domainMax - domainMin || 1;
			return (
				chartPadding.top +
				usableHeight -
				((value - domainMin) / span) * usableHeight
			);
		};

		const points = values.map((value, index) => ({
			x: chartPadding.left + index * xStep,
			y: yScale(value),
			upper: yScale(Math.min(value + spread, domainMax)),
			lower: yScale(Math.max(value - spread, domainMin)),
		}));

		const linePath = points
			.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
			.join(" ");
		const upperPath = points
			.map(
				(point, index) =>
					`${index === 0 ? "M" : "L"} ${point.x} ${point.upper}`,
			)
			.join(" ");
		const lowerPath = [...points]
			.reverse()
			.map(
				(point, index) =>
					`${index === 0 ? "L" : "L"} ${point.x} ${point.lower}`,
			)
			.join(" ");
		const bandPath = `${upperPath} ${lowerPath} Z`;
		const yTicks = Array.from({ length: 4 }, (_, index) => {
			const ratio = index / 3;
			return domainMax - (domainMax - domainMin) * ratio;
		});
		const xTicks = timeline
			.filter((_, index) => index % 6 === 0 || index === timeline.length - 1)
			.map((entry) => {
				const sourceIndex = timeline.findIndex(
					(candidate) => candidate.date === entry.date,
				);
				return {
					label: formatTime(entry.date, { day: "numeric", month: "short" }),
					x: chartPadding.left + sourceIndex * xStep,
				};
			});

		return { config, mean, band: spread, linePath, bandPath, yTicks, xTicks, domainMin, domainMax };
	});

	function formatTime(value: string, options: Intl.DateTimeFormatOptions) {
		return new Intl.DateTimeFormat("en", options).format(new Date(value));
	}

	function findCityById(id: string) {
		return cities.find((city) => city.id === id) ?? cities[0] ?? fallbackCity;
	}

	async function loadDailyPredictions(city: LocationPreset, dates: string[]) {
		if (dates.length === 0) {
			dailyPredictions = {};
			return;
		}

		predictionLoading = true;
		predictionError = "";

		try {
			const results = await Promise.all(
				dates.map(async (date) => {
					const payload = (await loadWeatherPrediction({
						city,
						date,
						mode: selectedMode,
					})) as WeatherPrediction;
					return [date, payload] as const;
				}),
			);

			dailyPredictions = Object.fromEntries(results);
		} catch (err) {
			console.error(err);
			dailyPredictions = {};
			predictionError =
				err instanceof Error
					? err.message
					: "5-day anomaly predictions are unavailable right now.";
		} finally {
			predictionLoading = false;
		}
	}

	async function loadPredictionMetadata() {
		metadataLoading = true;

		try {
			const metadata =
				(await loadPredictionMetadataFromApi()) as PredictionMetadata;
			cities = metadata.cities.length > 0 ? metadata.cities : [fallbackCity];
			selectedCity = metadata.defaultCity ?? cities[0] ?? fallbackCity;
			predictionModes = metadata.modes;
		} catch (err) {
			console.error(err);
			cities = [fallbackCity];
			selectedCity = fallbackCity;
			error =
				err instanceof Error
					? err.message
					: "City metadata is unavailable right now.";
		} finally {
			metadataLoading = false;
		}
	}

	async function loadWeather(city: LocationPreset) {
		selectedCity = city;
		loading = true;
		error = metadataLoading ? error : "";
		predictionError = "";
		dailyPredictions = {};

		try {
			weather = (await loadAppWeather(city)) as WeatherOverview;
			await loadDailyPredictions(
				city,
				weather.daily.map((day) => day.date).slice(1, 6),
			);
		} catch (err) {
			console.error(err);
			error =
				"Weather feed is unavailable right now. Check your network or the Open-Meteo upstream.";
		} finally {
			loading = false;
		}
	}

	async function handleCityChange(nextCityId: string) {
		const nextCity = findCityById(nextCityId);
		await loadWeather(nextCity);
	}

	async function handleModeChange(nextMode: string) {
		selectedMode = nextMode;
		if (weather) {
			await loadDailyPredictions(
				selectedCity,
				weather.daily.map((day) => day.date).slice(1, 6),
			);
		}
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
		id="forecast-overview"
		data-testid="dashboard-overview"
		class="grid gap-6 rounded-[2rem] border border-(--theme-border) bg-white/80 p-6 shadow-[0_24px_60px_var(--theme-shadow)] md:grid-cols-[1.6fr_1fr] md:p-8"
	>
		<div class="space-y-5">
			<div
				class="inline-flex rounded-full border border-(--theme-border) bg-(--theme-soft-70) px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-(--theme-accent)"
			>
				Forecast operations
			</div>
			<div class="space-y-3">
				<h1
					class="max-w-3xl text-4xl font-semibold tracking-tight text-(--theme-text) md:text-5xl"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Timeline, alerts, and daily outlook
				</h1>
				<p class="max-w-2xl text-base leading-7 text-(--theme-text) md:text-lg">
					Choose any city to view its live forecast, and next-5-day anomaly
					predictions.
				</p>
			</div>
		</div>

		<div
			class="hidden rounded-[1.8rem] border border-(--theme-border) bg-(--theme-soft-45) p-6 shadow-(--theme-shadow) md:block"
		>
			<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
				Forecast snapshot
			</div>
			<div class="mt-4 grid gap-3 text-sm text-(--theme-text)">
				<div class="flex items-center justify-between gap-4">
					<div id="forcast-city-label" class="text-(--theme-muted)">City</div>
					<div class="font-semibold text-(--theme-text)">
						<SearchableSelect
							triggerId="forecast-city"
							triggerTestId="forecast-city"
							labelledBy="forecast-city-label"
							items={cityItems}
							value={selectedCity.id}
							placeholder="Search city..."
							emptyMessage="No matching cities found."
							inputClass="mt-2 h-auto rounded-2xl border border-(--theme-border) bg-white/90 px-4 py-3 text-sm text-(--theme-text) outline-none transition placeholder:text-(--theme-muted) focus:border-(--theme-accent) focus:ring-4 focus:ring-[var(--theme-soft-45)]"
							contentClass="border border-(--theme-border) bg-white"
							itemClass="text-(--theme-text) data-highlighted:bg-(--theme-soft) data-highlighted:text-(--theme-text)"
							onValueChange={handleCityChange}
						/>
					</div>
				</div>
				<div class="flex items-center justify-between gap-4">
					<div id="forecast-mode-label" class="text-(--theme-muted)">Mode</div>
					<div class="font-semibold text-(--theme-text)">
						<SearchableSelect
							triggerId="forecast-mode"
							triggerTestId="forecast-mode"
							labelledBy="forecast-mode-label"
							items={predictionModes}
							value={selectedMode}
							placeholder="Search mode..."
							emptyMessage="No matching modes found."
							inputClass="mt-2 h-auto rounded-2xl border border-(--theme-border) bg-white/90 px-4 py-3 text-sm text-(--theme-text) outline-none transition placeholder:text-(--theme-muted) focus:border-(--theme-accent) focus:ring-4 focus:ring-[var(--theme-soft-45)]"
							contentClass="border border-(--theme-border) bg-white"
							itemClass="text-(--theme-text) data-highlighted:bg-(--theme-soft) data-highlighted:text-(--theme-text)"
							onValueChange={handleModeChange}
						/>
					</div>
				</div>
				<div class="text-(--theme-muted)">
						{predictionModes.find((mode) => mode.value === selectedMode)
							?.description}
				</div>
			</div>
		</div>
	</section>

	{#if loading}
		<div
			class="rounded-3xl border border-(--theme-accent) bg-(--theme-soft) px-5 py-4 text-sm text-(--theme-text)"
		>
			Loading forecast and anomaly signals...
		</div>
	{/if}

	{#if weather}
		<section
			id="forecast-analysis-grid"
			data-testid="forecast-analysis-grid"
			class="grid gap-6 xl:grid-cols-[1.5fr_1fr]"
		>
			<div
				id="forecast-timeline"
				data-testid="forecast-timeline"
				class="rounded-[2rem] border border-(--theme-border) bg-white/85 p-6 shadow-(--theme-shadow)"
			>
				<div class="flex flex-wrap items-end justify-between gap-3">
					<div>
						<div
							class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)"
						>
							Timeline
						</div>
						<h2
							class="mt-2 text-2xl font-semibold text-(--theme-text)"
							style="font-family: Georgia, 'Times New Roman', serif;"
						>
							Forecast chart
						</h2>
					</div>
					<div class="text-sm text-(--theme-muted)">
						Last refresh {formatTime(weather.current.time, {
							hour: "numeric",
							minute: "2-digit",
							month: "short",
							day: "numeric",
						})}
					</div>
				</div>

				<div class="mt-6 flex flex-wrap gap-3">
					{#each Object.entries(metricConfigs) as [metric, config]}
						<button
							class={`rounded-full border px-4 py-2 text-sm font-medium transition ${
								selectedMetric === metric
									? "border-(--theme-accent) bg-(--theme-soft) text-(--theme-text)"
									: "border-(--theme-border) bg-white/75 text-(--theme-text) hover:border-(--theme-accent) hover:bg-(--theme-soft)"
							}`}
							onclick={() =>
								(selectedMetric = metric as
									| "temperature"
									| "precipitationProbability"
									| "radiation"
									| "windSpeed")}
						>
							{config.label}
						</button>
					{/each}
				</div>

				<div
					class="mt-6 rounded-[1.6rem] border border-(--theme-border) bg-(--theme-soft-45) p-4"
				>
					<div class="h-80 w-full lg:h-88 xl:h-96">
						<LineChart
							data={timeline.map((entry) => ({
								date: new Date(entry.date),
								value: chartData.config.getValue(entry),
							}))}
							yVar="value"
							yDomain={[chartData.domainMin, chartData.domainMax]}
							config={{
								desktop: {
									label: chartData.config.label,
									color: chartData.config.color,
								},
							}}
							formatDate={(v) =>
								v.toLocaleDateString("en-US", { month: "short", day: "numeric" })
							}
						/>
					</div>

					<div class="mt-4 grid gap-4 md:grid-cols-2">
						<div
							class="rounded-3xl border border-(--theme-border) bg-white px-4 py-3"
						>
							<div
								class="text-xs uppercase tracking-[0.18em] text-(--theme-muted)"
							>
								Variable
							</div>
							<div class="mt-2 text-lg font-semibold text-(--theme-text)">
								{chartData.config.label}
							</div>
						</div>
						<div
							class="rounded-3xl border border-(--theme-border) bg-white px-4 py-3"
						>
							<div
								class="text-xs uppercase tracking-[0.18em] text-(--theme-muted)"
							>
								Mean forecast
							</div>
							<div class="mt-2 text-lg font-semibold text-(--theme-text)">
								{chartData.mean.toFixed(1)}{chartData.config.unit}
							</div>
						</div>
					</div>
				</div>
			</div>

			<div
				id="forecast-alerts"
				data-testid="forecast-alerts"
				class="rounded-[2rem] border border-(--theme-border) bg-(--theme-soft-60) p-6 shadow-(--theme-shadow)"
			>
				<div class="flex flex-wrap items-end justify-between gap-3">
					<div>
						<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
							ML Predictions
						</div>
						<h2
							class="mt-2 text-2xl font-semibold text-(--theme-text)"
							style="font-family: Georgia, 'Times New Roman', serif;"
						>
							5-day anomaly risks
						</h2>
					</div>
					{#if predictionLoading}
						<div class="text-sm text-(--theme-muted)">
							Scoring the 5-day forecast...
						</div>
					{:else}
						<div class="text-sm text-(--theme-muted)">
							{selectedMode === "sensitive"
								? "Sensitive mode"
								: "Conservative mode"}
						</div>
					{/if}
				</div>

				<div class="mt-5 grid gap-3">
					{#if predictionLoading}
						<div
							class="rounded-3xl border border-(--theme-border) bg-white/70 p-4 text-sm text-(--theme-text)"
						>
							Evaluating anomalous patterns...
						</div>
					{:else if predictionError}
						<div
							class="rounded-3xl border border-[#e8b6ae] bg-[#fff0ed] p-4 text-sm text-[#8d3f35]"
						>
							{predictionError}
						</div>
					{:else}
						{#each weather.daily.slice(1, 6) as day}
							{@const prediction = dailyPredictions[day.date]}
							{#if prediction && prediction.anomalyPrediction.isAnomaly}
								<div
									class={`rounded-3xl border p-4 ${severityClasses(prediction.anomalyPrediction.severity)}`}
								>
									<div class="flex items-center justify-between gap-3">
										<div class="text-base font-semibold">{prediction.categoryPrediction.label}</div>
										<div
											class="rounded-full bg-white/60 px-3 py-1 text-xs uppercase tracking-[0.18em]"
										>
											{prediction.anomalyPrediction.severity}
										</div>
									</div>
									<div class="mt-2 text-sm opacity-90">
										Anomalous {prediction.categoryPrediction.dominantSignal.toLowerCase()} expected ({Math.round(prediction.anomalyPrediction.probability * 100)}% confidence).
									</div>
									<div
										class="mt-3 text-xs uppercase tracking-[0.18em] opacity-75"
									>
										{formatTime(day.date, {
											weekday: "short",
											month: "short",
											day: "numeric",
										})}
									</div>
								</div>
							{/if}
						{/each}
						
						{#if Object.values(dailyPredictions).length > 0 && Object.values(dailyPredictions).every(p => !p.anomalyPrediction.isAnomaly)}
							<div
								class="rounded-3xl border border-(--theme-border) bg-white/70 p-4 text-sm text-(--theme-text)"
							>
								No major anomalies predicted in the next 5 days.
							</div>
						{/if}
					{/if}
				</div>
			</div>
		</section>

		<section
			id="forecast-daily-outlook"
			data-testid="forecast-daily-outlook"
			class="rounded-[2rem] border border-(--theme-border) bg-white/85 p-6 shadow-(--theme-shadow)"
		>
			<div class="flex flex-wrap items-end justify-between gap-3">
				<div>
					<div
						class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)"
					>
						Daily outlook
					</div>
					<h2
						class="mt-2 text-2xl font-semibold text-(--theme-text)"
						style="font-family: Georgia, 'Times New Roman', serif;"
					>
						5-day operational forecast
					</h2>
				</div>
				<a
					class="text-sm text-(--theme-text) underline decoration-(--theme-accent) underline-offset-4"
					href={weather.source.url}
					target="_blank"
					rel="noreferrer"
				>
					Data source: {weather.source.name}
				</a>
			</div>

			<div class="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
				{#each weather.daily.slice(1, 6) as day}
					<div
						class="rounded-[1.6rem] border border-(--theme-border) bg-(--theme-soft-45) p-5"
					>
						<div class="text-sm text-(--theme-muted)">
							{formatTime(day.date, {
								weekday: "short",
								month: "short",
								day: "numeric",
							})}
						</div>
						<div
							class="mt-3 text-xl font-semibold text-(--theme-text)"
							style="font-family: Georgia, 'Times New Roman', serif;"
						>
							{weatherCodeLabel(day.weatherCode)}
						</div>
						<div class="mt-4 text-sm text-(--theme-text)">
							<span class="font-semibold text-(--theme-text)"
								>{day.tempMax.toFixed(0)}°</span
							>
							<span class="mx-2 text-(--theme-muted)">/</span>
							{day.tempMin.toFixed(0)}°
						</div>
						<div class="mt-3 text-sm text-(--theme-text)">
							{day.precipitationSum.toFixed(1)} mm precipitation
						</div>
						<div class="mt-1 text-sm text-(--theme-text)">
							{day.windSpeedMax.toFixed(0)} km/h max wind
						</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</div>
