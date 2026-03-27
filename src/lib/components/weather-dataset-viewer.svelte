<script lang="ts">
	import Input from "$lib/components/ui/input/input.svelte";
	import SearchableSelect from "$lib/components/searchable-select.svelte";
	import { weatherCodeLabel } from "$lib/weather-utils";
	import datasetRaw from "../../SriLanka_Weather_Dataset_V1.csv?raw";

	type DatasetRow = {
		date: string;
		year: number;
		weatherCode: number;
		tempMax: number;
		tempMin: number;
		tempMean: number;
		apparentTempMax: number;
		apparentTempMin: number;
		apparentTempMean: number;
		sunrise: string;
		sunset: string;
		shortwaveRadiationSum: number;
		precipitationSum: number;
		rainSum: number;
		snowfallSum: number;
		precipitationHours: number;
		windSpeedMax: number;
		windGustsMax: number;
		windDirectionDominant: number;
		evapotranspiration: number;
		latitude: number;
		longitude: number;
		elevation: number;
		country: string;
		city: string;
		searchText: string;
	};

	const pageSize = 25;

	function toNumber(value: string) {
		const parsed = Number(value);
		return Number.isFinite(parsed) ? parsed : 0;
	}

	function normalizeDate(value: string) {
		const [month = "1", day = "1", year = "1970"] = value.split("/");
		return `${year.padStart(4, "0")}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
	}

	function formatDate(value: string) {
		return new Intl.DateTimeFormat("en", {
			month: "short",
			day: "numeric",
			year: "numeric",
		}).format(new Date(`${value}T00:00:00`));
	}

	function formatNumber(value: number, digits = 1) {
		return new Intl.NumberFormat("en", {
			maximumFractionDigits: digits,
			minimumFractionDigits: digits,
		}).format(value);
	}

	const datasetRows: DatasetRow[] = datasetRaw
		.trim()
		.split(/\r?\n/)
		.slice(1)
		.map((line) => {
			const [
				time,
				weathercode,
				temperature_2m_max,
				temperature_2m_min,
				temperature_2m_mean,
				apparent_temperature_max,
				apparent_temperature_min,
				apparent_temperature_mean,
				sunrise,
				sunset,
				shortwave_radiation_sum,
				precipitation_sum,
				rain_sum,
				snowfall_sum,
				precipitation_hours,
				windspeed_10m_max,
				windgusts_10m_max,
				winddirection_10m_dominant,
				et0_fao_evapotranspiration,
				latitude,
				longitude,
				elevation,
				country,
				city,
			] = line.split(",");
			const date = normalizeDate(time);
			const year = Number(date.slice(0, 4));
			const weatherCode = toNumber(weathercode);

			return {
				date,
				year,
				weatherCode,
				tempMax: toNumber(temperature_2m_max),
				tempMin: toNumber(temperature_2m_min),
				tempMean: toNumber(temperature_2m_mean),
				apparentTempMax: toNumber(apparent_temperature_max),
				apparentTempMin: toNumber(apparent_temperature_min),
				apparentTempMean: toNumber(apparent_temperature_mean),
				sunrise,
				sunset,
				shortwaveRadiationSum: toNumber(shortwave_radiation_sum),
				precipitationSum: toNumber(precipitation_sum),
				rainSum: toNumber(rain_sum),
				snowfallSum: toNumber(snowfall_sum),
				precipitationHours: toNumber(precipitation_hours),
				windSpeedMax: toNumber(windspeed_10m_max),
				windGustsMax: toNumber(windgusts_10m_max),
				windDirectionDominant: toNumber(winddirection_10m_dominant),
				evapotranspiration: toNumber(et0_fao_evapotranspiration),
				latitude: toNumber(latitude),
				longitude: toNumber(longitude),
				elevation: toNumber(elevation),
				country,
				city,
				searchText: [
					city,
					country,
					time,
					date,
					weatherCodeLabel(weatherCode),
					weathercode,
				]
					.join(" ")
					.toLowerCase(),
			};
		});

	const cityOptions = [...new Set(datasetRows.map((row) => row.city))].sort(
		(a, b) => a.localeCompare(b),
	);
	const citySelectItems = [
		{ value: "all", label: "All cities" },
		...cityOptions.map((city) => ({ value: city, label: city })),
	];
	const yearOptions = [...new Set(datasetRows.map((row) => row.year))].sort(
		(a, b) => b - a,
	);
	const minDate = datasetRows[0]?.date ?? "";
	const maxDate = datasetRows[datasetRows.length - 1]?.date ?? "";

	let search = $state("");
	let cityFilter = $state("all");
	let startDate = $state(minDate);
	let endDate = $state(maxDate);
	let currentPage = $state(1);

	const filteredRows = $derived.by(() => {
		const query = search.trim().toLowerCase();

		return datasetRows.filter((row) => {
			if (cityFilter !== "all" && row.city !== cityFilter) return false;
			if (startDate && row.date < startDate) return false;
			if (endDate && row.date > endDate) return false;
			if (query && !row.searchText.includes(query)) return false;
			return true;
		});
	});

	const totalPages = $derived.by(() =>
		Math.max(1, Math.ceil(filteredRows.length / pageSize)),
	);
	const paginatedRows = $derived.by(() => {
		const start = (currentPage - 1) * pageSize;
		return filteredRows.slice(start, start + pageSize);
	});
	const summary = $derived.by(() => {
		if (filteredRows.length === 0) {
			return {
				cities: 0,
				averageMeanTemp: 0,
				totalRainfall: 0,
				maxWind: 0,
			};
		}

		const cityCount = new Set(filteredRows.map((row) => row.city)).size;
		const totalMeanTemp = filteredRows.reduce(
			(sum, row) => sum + row.tempMean,
			0,
		);
		const totalRainfall = filteredRows.reduce(
			(sum, row) => sum + row.precipitationSum,
			0,
		);
		const maxWind = filteredRows.reduce(
			(max, row) => Math.max(max, row.windSpeedMax),
			0,
		);

		return {
			cities: cityCount,
			averageMeanTemp: totalMeanTemp / filteredRows.length,
			totalRainfall,
			maxWind,
		};
	});

	$effect(() => {
		search;
		cityFilter;
		startDate;
		endDate;
		currentPage = 1;
	});

	$effect(() => {
		if (currentPage > totalPages) {
			currentPage = totalPages;
		}
	});
</script>

<div class="flex flex-col gap-8">
	<section
		id="dataset-overview"
		data-testid="dataset-overview"
		class="grid gap-6 rounded-[2rem] border border-(--theme-border) bg-white/80 p-6 shadow-[0_24px_60px_var(--theme-shadow)] md:grid-cols-[1.45fr_1fr] md:p-8"
	>
		<div class="space-y-5">
			<div
				class="inline-flex rounded-full border border-(--theme-border) bg-(--theme-soft-70) px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-(--theme-accent)"
			>
				Dataset explorer
			</div>
			<div class="space-y-3">
				<h1
					class="max-w-3xl text-4xl font-semibold tracking-tight text-(--theme-text) md:text-5xl"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Search and filter Sri Lanka weather records without leaving the
					dashboard.
				</h1>
				<p class="max-w-2xl text-base leading-7 text-(--theme-text) md:text-lg">
					Browse 2010 to 2023 daily observations across 30 cities, narrow the
					dataset by city and date range, and inspect the rows that matter most.
				</p>
			</div>
		</div>

		<div
			class="grid gap-3 rounded-[1.6rem] border border-(--theme-border) bg-(--theme-soft-55) p-5"
		>
			<div class="rounded-3xl border border-(--theme-border) bg-white p-4">
				<div class="text-sm text-(--theme-muted)">Rows available</div>
				<div
					class="mt-2 text-3xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					{datasetRows.length.toLocaleString()}
				</div>
			</div>
			<div class="grid gap-3 sm:grid-cols-2">
				<div class="rounded-3xl border border-(--theme-border) bg-white p-4">
					<div class="text-sm text-(--theme-muted)">Cities covered</div>
					<div
						class="mt-2 text-2xl font-semibold text-(--theme-text)"
						style="font-family: Georgia, 'Times New Roman', serif;"
					>
						{cityOptions.length}
					</div>
				</div>
				<div class="rounded-3xl border border-(--theme-border) bg-white p-4">
					<div class="text-sm text-(--theme-muted)">Year span</div>
					<div
						class="mt-2 text-2xl font-semibold text-(--theme-text)"
						style="font-family: Georgia, 'Times New Roman', serif;"
					>
						{yearOptions.at(-1)}-{yearOptions[0]}
					</div>
				</div>
			</div>
		</div>
	</section>

	<section
		id="dataset-filters"
		data-testid="dataset-filters"
		class="rounded-[2rem] border border-(--theme-border) bg-white/80 p-6 shadow-(--theme-shadow)"
	>
		<div class="flex flex-wrap items-end justify-between gap-3">
			<div>
				<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
					Filters
				</div>
				<h2
					class="mt-2 text-2xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Refine the dataset view
				</h2>
			</div>
			<div class="text-sm text-(--theme-muted)">
				Showing {filteredRows.length.toLocaleString()} matching rows
			</div>
		</div>

		<div class="mt-6 grid gap-4 xl:grid-cols-[2fr_1fr_1fr_1fr]">
			<div class="space-y-2">
				<label
					class="text-sm font-medium text-(--theme-text)"
					for="dataset-search">Search</label
				>
				<Input
					id="dataset-search"
					data-testid="dataset-search"
					bind:value={search}
					placeholder="Search by city, date, or condition"
					class="h-11 border-(--theme-border) bg-white text-(--theme-text) placeholder:text-(--theme-muted) focus-visible:border-(--theme-accent) focus-visible:ring-(--theme-soft-45)"
				/>
			</div>

			<div class="space-y-2">
				<div
					class="text-sm font-medium text-(--theme-text)"
					id="city-filter-label"
				>
					City
				</div>
				<SearchableSelect
					bind:value={cityFilter}
					triggerId="city-filter"
					triggerTestId="city-filter"
					labelledBy="city-filter-label"
					items={citySelectItems}
					placeholder="Search city..."
					emptyMessage="No matching cities found."
					inputClass="h-11 rounded-4xl border border-(--theme-border) bg-white px-4 text-sm text-(--theme-text) outline-none transition placeholder:text-(--theme-muted) focus:border-(--theme-accent) focus:ring-4 focus:ring-[var(--theme-soft-45)]"
					contentClass="border border-(--theme-border) bg-white"
					itemClass="text-(--theme-text) data-highlighted:bg-(--theme-soft)data-highlighted:text-(--theme-text)"
				/>
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium text-(--theme-text)" for="start-date"
					>Start date</label
				>
				<Input
					id="start-date"
					type="date"
					data-testid="start-date"
					bind:value={startDate}
					min={minDate}
					max={endDate || maxDate}
					class="h-11 border-(--theme-border) bg-white text-(--theme-text) focus-visible:border-(--theme-accent) focus-visible:ring-(--theme-soft-45)"
				/>
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium text-(--theme-text)" for="end-date"
					>End date</label
				>
				<Input
					id="end-date"
					type="date"
					data-testid="end-date"
					bind:value={endDate}
					min={startDate || minDate}
					max={maxDate}
					class="h-11 border-(--theme-border) bg-white text-(--theme-text) focus-visible:border-(--theme-accent) focus-visible:ring-(--theme-soft-45)"
				/>
			</div>
		</div>
	</section>

	<section
		id="dataset-summary"
		data-testid="dataset-summary"
		class="grid gap-4 md:grid-cols-2 xl:grid-cols-4"
	>
		<div
			id="summary-matching-rows"
			data-testid="summary-matching-rows"
			class="rounded-[1.8rem] border border-(--theme-border) bg-white/85 p-5 shadow-(--theme-shadow)"
		>
			<div class="text-sm text-(--theme-muted)">Matching rows</div>
			<div
				class="mt-3 text-4xl font-semibold text-(--theme-text)"
				style="font-family: Georgia, 'Times New Roman', serif;"
			>
				{filteredRows.length.toLocaleString()}
			</div>
		</div>
		<div
			id="summary-cities"
			data-testid="summary-cities"
			class="rounded-[1.8rem] border border-(--theme-border) bg-white/85 p-5 shadow-(--theme-shadow)"
		>
			<div class="text-sm text-(--theme-muted)">Cities in result</div>
			<div
				class="mt-3 text-4xl font-semibold text-(--theme-text)"
				style="font-family: Georgia, 'Times New Roman', serif;"
			>
				{summary.cities}
			</div>
		</div>
		<div
			id="summary-average-temp"
			data-testid="summary-average-temp"
			class="rounded-[1.8rem] border border-(--theme-border) bg-white/85 p-5 shadow-(--theme-shadow)"
		>
			<div class="text-sm text-(--theme-muted)">Average mean temp</div>
			<div
				class="mt-3 text-4xl font-semibold text-(--theme-text)"
				style="font-family: Georgia, 'Times New Roman', serif;"
			>
				{formatNumber(summary.averageMeanTemp)}°C
			</div>
		</div>
		<div
			id="summary-highest-wind"
			data-testid="summary-highest-wind"
			class="rounded-[1.8rem] border border-(--theme-border) bg-white/85 p-5 shadow-(--theme-shadow)"
		>
			<div class="text-sm text-(--theme-muted)">Highest wind</div>
			<div
				class="mt-3 text-4xl font-semibold text-(--theme-text)"
				style="font-family: Georgia, 'Times New Roman', serif;"
			>
				{formatNumber(summary.maxWind)} km/h
			</div>
		</div>
	</section>

	<section
		id="dataset-table-section"
		data-testid="dataset-table-section"
		class="rounded-[2rem] border border-(--theme-border) bg-white/80 p-6 shadow-(--theme-shadow)"
	>
		<div class="flex flex-wrap items-end justify-between gap-3">
			<div>
				<div class="text-sm uppercase tracking-[0.18em] text-(--theme-accent)">
					Dataset table
				</div>
				<h2
					class="mt-2 text-2xl font-semibold text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Daily weather records
				</h2>
			</div>
			<div class="text-sm text-(--theme-muted)">
				Total precipitation in view: {formatNumber(summary.totalRainfall)} mm
			</div>
		</div>

		{#if paginatedRows.length === 0}
			<div
				class="mt-6 rounded-3xl border border-(--theme-accent) bg-(--theme-soft) px-5 py-4 text-sm text-(--theme-text)"
			>
				No records matched those filters. Try a wider year range, another city,
				or clear the search term.
			</div>
		{:else}
			<div
				id="dataset-table-wrapper"
				data-testid="dataset-table-wrapper"
				class="mt-6 overflow-hidden rounded-[1.5rem] border border-(--theme-border)"
			>
				<div class="overflow-x-auto">
					<table
						id="dataset-table"
						data-testid="dataset-table"
						class="min-w-full divide-y divide-(--theme-border) bg-white"
					>
						<thead
							class="bg-(--theme-soft-60) text-left text-xs uppercase tracking-[0.18em] text-(--theme-muted)"
						>
							<tr>
								<th class="px-4 py-3 font-medium">Date</th>
								<th class="px-4 py-3 font-medium">City</th>
								<th class="px-4 py-3 font-medium">Condition</th>
								<th class="px-4 py-3 font-medium">Mean temp</th>
								<th class="px-4 py-3 font-medium">Min / Max</th>
								<th class="px-4 py-3 font-medium">Rain</th>
								<th class="px-4 py-3 font-medium">Wind</th>
								<th class="px-4 py-3 font-medium">Sun window</th>
							</tr>
						</thead>
						<tbody
							class="divide-y divide-(--theme-soft) text-sm text-(--theme-text)"
						>
							{#each paginatedRows as row}
								<tr class="align-top transition hover:bg-(--theme-soft-30)">
									<td class="px-4 py-4">
										<div class="font-medium text-(--theme-text)">
											{formatDate(row.date)}
										</div>
										<div class="mt-1 text-xs text-(--theme-muted)">
											{row.year}
										</div>
									</td>
									<td class="px-4 py-4">
										<div class="font-medium text-(--theme-text)">
											{row.city}
										</div>
										<div class="mt-1 text-xs text-(--theme-muted)">
											{row.country}
										</div>
									</td>
									<td class="px-4 py-4">
										<div class="font-medium text-(--theme-text)">
											{weatherCodeLabel(row.weatherCode)}
										</div>
										<div class="mt-1 text-xs text-(--theme-muted)">
											Code {row.weatherCode}
										</div>
									</td>
									<td class="px-4 py-4">{formatNumber(row.tempMean)}°C</td>
									<td class="px-4 py-4"
										>{formatNumber(row.tempMin)}° / {formatNumber(
											row.tempMax,
										)}°</td
									>
									<td class="px-4 py-4">
										<div>{formatNumber(row.precipitationSum)} mm</div>
										<div class="mt-1 text-xs text-(--theme-muted)">
											{formatNumber(row.precipitationHours)} hrs
										</div>
									</td>
									<td class="px-4 py-4">
										<div>{formatNumber(row.windSpeedMax)} km/h</div>
										<div class="mt-1 text-xs text-(--theme-muted)">
											Gusts {formatNumber(row.windGustsMax)} km/h
										</div>
									</td>
									<td class="px-4 py-4">
										<div>{row.sunrise}</div>
										<div class="mt-1 text-xs text-(--theme-muted)">
											{row.sunset}
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			<div
				id="dataset-pagination"
				data-testid="dataset-pagination"
				class="mt-5 flex flex-wrap items-center justify-between gap-3"
			>
				<div class="text-sm text-(--theme-text)">
					Page {currentPage} of {totalPages}
				</div>
				<div class="flex items-center gap-2">
					<button
						id="dataset-pagination-prev"
						data-testid="dataset-pagination-prev"
						class="rounded-full border border-(--theme-accent) bg-white px-4 py-2 text-sm font-medium text-(--theme-text) transition hover:border-(--theme-accent) hover:bg-(--theme-soft) disabled:cursor-not-allowed disabled:opacity-50"
						onclick={() => (currentPage = Math.max(1, currentPage - 1))}
						disabled={currentPage === 1}
					>
						Previous
					</button>
					<button
						id="dataset-pagination-next"
						data-testid="dataset-pagination-next"
						class="rounded-full border border-(--theme-accent) bg-white px-4 py-2 text-sm font-medium text-(--theme-text) transition hover:border-(--theme-accent) hover:bg-(--theme-soft) disabled:cursor-not-allowed disabled:opacity-50"
						onclick={() =>
							(currentPage = Math.min(totalPages, currentPage + 1))}
						disabled={currentPage === totalPages}
					>
						Next
					</button>
				</div>
			</div>
		{/if}
	</section>
</div>
