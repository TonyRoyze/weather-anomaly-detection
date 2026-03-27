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
		"temperature" | "precipitationProbability" | "humidity" | "windSpeed"
	>("temperature");

	const cityItems = $derived.by(() =>
		cities.map((city) => ({
			value: city.id,
			label: city.label,
		})),
	);
	const timeline = $derived.by(() => weather?.hourly ?? []);
	const metricConfigs = {
		temperature: {
			label: "Temperature",
			unit: "°C",
			color: "var(--theme-accent-strong)",
			bandColor: "var(--theme-soft-45)",
			getValue: (entry: WeatherOverview["hourly"][number]) => entry.temperature,
			minSpread: 1.2,
		},
		precipitationProbability: {
			label: "Rain probability",
			unit: "%",
			color: "var(--theme-accent)",
			bandColor: "var(--theme-soft-45)",
			getValue: (entry: WeatherOverview["hourly"][number]) =>
				entry.precipitationProbability,
			minSpread: 8,
		},
		humidity: {
			label: "Humidity",
			unit: "%",
			color: "var(--theme-accent)",
			bandColor: "var(--theme-soft-55)",
			getValue: (entry: WeatherOverview["hourly"][number]) => entry.humidity,
			minSpread: 6,
		},
		windSpeed: {
			label: "Wind speed",
			unit: "km/h",
			color: "var(--theme-accent-strong)",
			bandColor: "var(--theme-soft-45)",
			getValue: (entry: WeatherOverview["hourly"][number]) => entry.windSpeed,
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
			};
		}

		const mean = average(values);
		const spread = Math.max(stdDev(values) * 0.9, config.minSpread);
		const low = Math.min(...values.map((value) => value - spread));
		const high = Math.max(...values.map((value) => value + spread));
		const domainMin =
			selectedMetric === "precipitationProbability" ||
			selectedMetric === "humidity"
				? Math.max(0, Math.min(low, 0))
				: low;
		const domainMax =
			selectedMetric === "precipitationProbability" ||
			selectedMetric === "humidity"
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
					(candidate) => candidate.time === entry.time,
				);
				return {
					label: formatTime(entry.time, { hour: "numeric" }),
					x: chartPadding.left + sourceIndex * xStep,
				};
			});

		return { config, mean, band: spread, linePath, bandPath, yTicks, xTicks };
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
					const params = new URLSearchParams({
						latitude: city.latitude.toString(),
						longitude: city.longitude.toString(),
						label: city.label,
						date,
						mode: selectedMode,
					});
					const response = await fetch(
						`/api/weather/predict?${params.toString()}`,
					);
					const payload = (await response.json()) as
						| WeatherPrediction
						| { message?: string; detail?: string };
					if (!response.ok) {
						throw new Error(
							("detail" in payload && payload.detail) ||
								("message" in payload && payload.message) ||
								`Failed to load prediction for ${date}`,
						);
					}
					return [date, payload as WeatherPrediction] as const;
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
			const response = await fetch("/api/weather/prediction-metadata");
			const payload = (await response.json()) as
				| PredictionMetadata
				| { message?: string; detail?: string };

			if (!response.ok) {
				throw new Error(
					("detail" in payload && payload.detail) ||
						("message" in payload && payload.message) ||
						"Failed to load city metadata",
				);
			}

			const metadata = payload as PredictionMetadata;
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

		const params = new URLSearchParams({
			latitude: city.latitude.toString(),
			longitude: city.longitude.toString(),
			label: city.label,
		});

		try {
			const response = await fetch(`/api/weather?${params.toString()}`);
			if (!response.ok) {
				throw new Error("Failed to load forecast");
			}

			weather = (await response.json()) as WeatherOverview;
			await loadDailyPredictions(
				city,
				weather.daily.map((day) => day.date).slice(0, 5),
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
				weather.daily.map((day) => day.date).slice(0, 5),
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
		data-testid="forecast-overview"
		class="rounded-[2rem] border border-(--theme-border) bg-(--theme-soft-75) p-6 shadow-(--theme-shadow) md:p-8"
	>
		<div class="grid gap-6 lg:grid-cols-[1.35fr_0.65fr] lg:items-start">
			<div>
				<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
					Forecast operations
				</div>
				<h1
					class="mt-2 text-3xl font-semibold text-(--theme-text) md:text-4xl"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Timeline, alerts, and daily outlook
				</h1>
				<p class="mt-3 max-w-2xl text-sm leading-6 text-(--theme-text)">
					Use this page for the live operational view while the main dashboard
					stays focused on date-based anomaly prediction. Choose any city from
					the dataset to inspect its live forecast, alerts, and next-5-day
					anomaly predictions.
				</p>
			</div>

			<div
				class="w-full rounded-[1.8rem] border border-(--theme-border) bg-white/80 p-5 shadow-(--theme-shadow) lg:max-w-sm lg:justify-self-end"
			>
				<div
					class="text-sm font-medium text-(--theme-text)"
					id="forecast-city-label"
				>
					City
				</div>
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
				<div
					class="mt-4 text-sm font-medium text-(--theme-text)"
					id="forecast-mode-label"
				>
					Binary mode
				</div>
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
				<div class="mt-3 text-sm text-(--theme-muted)">
					{predictionModes.find((mode) => mode.value === selectedMode)
						?.description}
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

	{#if loading}
		<div
			class="rounded-3xl border border-(--theme-accent) bg-(--theme-soft) px-5 py-4 text-sm text-(--theme-text)"
		>
			Loading forecast and anomaly signals...
		</div>
	{/if}

	{#if predictionError}
		<div
			class="rounded-3xl border border-(--theme-accent) bg-(--theme-soft) px-5 py-4 text-sm text-(--theme-text)"
		>
			{predictionError}
		</div>
	{/if}

	{#if weather}
		<section
			id="forecast-model-predictions"
			data-testid="forecast-model-predictions"
			class="rounded-[2rem] border border-(--theme-border) bg-white/85 p-6 shadow-(--theme-shadow)"
		>
			<div class="flex flex-wrap items-end justify-between gap-3">
				<div>
					<div
						class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)"
					>
						Model forecast
					</div>
					<h2
						class="mt-2 text-2xl font-semibold text-(--theme-text)"
						style="font-family: Georgia, 'Times New Roman', serif;"
					>
						Next 5 days anomaly predictions
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

			<div class="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
				{#each weather.daily.slice(0, 5) as day}
					{@const forecastPrediction = dailyPredictions[day.date]}
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
						<div class="mt-3 flex items-center justify-between gap-3">
							<div
								class="text-lg font-semibold text-(--theme-text)"
								style="font-family: Georgia, 'Times New Roman', serif;"
							>
								{forecastPrediction?.categoryPrediction.label ?? "Scoring..."}
							</div>
							{#if forecastPrediction}
								<div
									class={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${severityClasses(forecastPrediction.anomalyPrediction.severity)}`}
								>
									{forecastPrediction.anomalyPrediction.severity}
								</div>
							{/if}
						</div>
						<div class="mt-3 text-sm text-(--theme-text)">
							{forecastPrediction?.anomalyPrediction.isAnomaly
								? "Anomaly"
								: "Normal pattern"}
						</div>
						{#if forecastPrediction}
							<div class="mt-2 text-sm text-(--theme-text)">
								Probability {(
									forecastPrediction.anomalyPrediction.probability * 100
								).toFixed(1)}%
							</div>
							<div class="mt-1 text-sm text-(--theme-text)">
								Dominant: {forecastPrediction.categoryPrediction.dominantSignal}
							</div>
						{:else}
							<div class="mt-2 text-sm text-(--theme-text)">
								Waiting for model output...
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</section>

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
							Forecast chart with confidence band
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
									| "humidity"
									| "windSpeed")}
						>
							{config.label}
						</button>
					{/each}
				</div>

				<div
					class="mt-6 rounded-[1.6rem] border border-(--theme-border) bg-(--theme-soft-45) p-4"
				>
					<svg
						viewBox={`0 0 ${chartWidth} ${chartHeight}`}
						class="h-80 w-full overflow-visible lg:h-88 xl:h-96"
						role="img"
						aria-label={`${chartData.config.label} forecast chart`}
					>
						{#each chartData.yTicks as tick}
							{@const y =
								chartPadding.top +
								(chartHeight - chartPadding.top - chartPadding.bottom) *
									(1 -
										(tick - chartData.yTicks[chartData.yTicks.length - 1]) /
											(chartData.yTicks[0] -
												chartData.yTicks[chartData.yTicks.length - 1] || 1))}
							<line
								x1={chartPadding.left}
								x2={chartWidth - chartPadding.right}
								y1={y}
								y2={y}
								stroke="var(--theme-border)"
								stroke-dasharray="4 6"
							/>
							<text
								x={chartPadding.left}
								y={y - 6}
								fill="var(--theme-muted)"
								font-size="11"
							>
								{tick.toFixed(0)}{chartData.config.unit}
							</text>
						{/each}

						<path d={chartData.bandPath} fill={chartData.config.bandColor} />
						<path
							d={chartData.linePath}
							fill="none"
							stroke={chartData.config.color}
							stroke-width="4"
							stroke-linecap="round"
							stroke-linejoin="round"
						/>

						{#each chartData.xTicks as tick}
							<text
								x={tick.x}
								y={chartHeight - 10}
								fill="var(--theme-muted)"
								font-size="11"
								text-anchor="middle"
							>
								{tick.label}
							</text>
						{/each}
					</svg>

					<div class="mt-4 grid gap-4 md:grid-cols-3">
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
						<div
							class="rounded-3xl border border-(--theme-border) bg-white px-4 py-3"
						>
							<div
								class="text-xs uppercase tracking-[0.18em] text-(--theme-muted)"
							>
								Confidence band
							</div>
							<div class="mt-2 text-lg font-semibold text-(--theme-text)">
								+/- {chartData.band.toFixed(1)}{chartData.config.unit}
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
				<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
					Alerts
				</div>
				<h2
					class="mt-2 text-2xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Detected anomalies
				</h2>
				<p class="mt-2 text-sm leading-6 text-(--theme-text)">
					Initial rule-based flags using the short-range Open-Meteo forecast
					window.
				</p>

				<div class="mt-5 grid gap-3">
					{#if weather.anomalies.length === 0}
						<div
							class="rounded-3xl border border-(--theme-border) bg-white/70 p-4 text-sm text-(--theme-text)"
						>
							No major anomalies in the current 48-hour forecast slice.
						</div>
					{:else}
						{#each weather.anomalies as anomaly}
							<div
								class={`rounded-3xl border p-4 ${severityClasses(anomaly.severity)}`}
							>
								<div class="flex items-center justify-between gap-3">
									<div class="text-base font-semibold">{anomaly.title}</div>
									<div
										class="rounded-full bg-white/60 px-3 py-1 text-xs uppercase tracking-[0.18em]"
									>
										{anomaly.severity}
									</div>
								</div>
								<div class="mt-2 text-sm opacity-90">{anomaly.reason}</div>
								<div
									class="mt-3 text-xs uppercase tracking-[0.18em] opacity-75"
								>
									{formatTime(anomaly.time, {
										weekday: "short",
										hour: "numeric",
									})}
									· {anomaly.metric}
								</div>
							</div>
						{/each}
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

			<div class="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
				{#each weather.daily as day}
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
