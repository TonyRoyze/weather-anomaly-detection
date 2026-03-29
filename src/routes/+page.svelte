<script lang="ts">
	// import GitHubStarButton from '$lib/components/github-star-button.svelte';
	import logo from "$lib/assets/logo.svg";
	import ThemePaletteSwitcher from "$lib/components/theme-palette-switcher.svelte";

	const githubOwner = "your-org";
	const githubRepo = "anomalize";

	const detectVars = [
		"temperature_2m_mean",
		"shortwave_radiation_sum",
		"precipitation_sum",
		"windspeed_10m_max",
		"apparent_temperature_mean",
		"weathercode",
		"time",
		"windgusts_10m_max",
		"temperature_2m_min",
		"apparent_temperature_min",
		"temperature_2m_max",
		"apparent_temperature_max",
		"anomaly",
		"rain_sum",
		"snowfall_sum",
		"is_anomaly",
	];

	const features = [
		{
			eyebrow: "Beautiful monitoring",
			title: "Give every important signal a place on screen.",
			description:
				"Temperature, apparent temperature, gusts, max wind, precipitation, and weather codes become readable cards, timelines, and anomaly summaries that are easy to scan.",
			points: [
				"Lightweight visual summaries",
				"Location-by-location comparisons",
				"Built for weather-sensitive decisions",
			],
		},
		{
			eyebrow: "Signal confidence",
			title: "Track the variables that actually matter to anomaly detection.",
			description:
				"Your monitored variables stay visible on the landing page so the product story matches the dashboard logic from the start.",
			points: [
				"Mean, min, and max temperature bands",
				"Wind speed and gust extremes",
				"Rain, snowfall, and shortwave radiation",
			],
		},
	];

	const spotlightVars = [
		"temperature_2m_mean",
		"temperature_2m_min",
		"temperature_2m_max",
		"apparent_temperature_mean",
		"windspeed_10m_max",
		"windgusts_10m_max",
		"precipitation_sum",
		"rain_sum",
		"snowfall_sum",
		"shortwave_radiation_sum",
		"weathercode",
		"is_anomaly",
	];
</script>

<svelte:head>
	<title>Anomalize</title>
	<meta
		name="description"
		content="Anomalize is a light, focused weather anomaly dashboard for tracking unusual changes across temperature, wind, rain, snowfall, and radiation signals."
	/>
</svelte:head>

<div class="min-h-screen bg-(--theme-bg) text-(--theme-text)">
	<div style="background: var(--theme-landing-gradient);">
		<div
			class="mx-auto flex max-w-7xl flex-col gap-16 px-6 py-8 lg:px-10 lg:py-12"
		>
			<header
				id="landing-header"
				data-testid="landing-header"
				class="flex items-center justify-between gap-4"
			>
				<a
					href="/"
					id="landing-home-link"
					data-testid="landing-home-link"
					class="flex items-center gap-3 text-xl font-semibold tracking-tight"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					<img src={logo} alt="Anomalize logo" class="h-7 w-auto" />
					<span>Anomalize</span>
				</a>
				<nav
					id="landing-nav"
					data-testid="landing-nav"
					class="flex items-center gap-3 text-sm text-(--theme-muted)"
				>
					<a
						id="landing-nav-dashboard"
						data-testid="landing-nav-dashboard"
						href="/dashboard"
						class="rounded-full px-3 py-2 transition hover:bg-white/60 hover:text-(--theme-text)"
						>Dashboard</a
					>
					<a
						id="landing-nav-downloads"
						data-testid="landing-nav-downloads"
						href="#downloads"
						class="rounded-full px-3 py-2 transition hover:bg-white/60 hover:text-(--theme-text)"
						>Downloads</a
					>
				</nav>
				<ThemePaletteSwitcher />
			</header>

			<section
				id="landing-hero"
				data-testid="landing-hero"
				class="grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-center"
			>
				<div class="space-y-7">
					<div
						class="inline-flex rounded-full border border-(--theme-border) bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-(--theme-accent)"
					>
						Weather anomaly dashboard
					</div>
					<div class="space-y-5">
						<h1
							class="max-w-4xl text-5xl font-semibold tracking-tight md:text-7xl"
							style="font-family: Georgia, 'Times New Roman', serif;"
						>
							Spot unusual weather faster than a forecast table ever could.
						</h1>
						<p
							class="max-w-2xl text-base leading-8 text-(--theme-text) md:text-lg"
						>
							Anomalize turns daily weather variables into a calm, readable
							monitoring surface. See abnormal swings in temperature, wind,
							precipitation, and radiation before they become missed signals.
						</p>
					</div>
					<div class="flex flex-wrap gap-3">
						<a
							href="/dashboard"
							id="landing-open-dashboard"
							data-testid="landing-open-dashboard"
							class="rounded-full bg-(--theme-accent-strong) px-6 py-3 text-sm font-semibold text-white shadow-(--theme-shadow) transition hover:bg-(--theme-accent)]"
						>
							Open dashboard
						</a>
						<a
							href="#downloads"
							id="landing-see-downloads"
							data-testid="landing-see-downloads"
							class="rounded-full border border-(--theme-border) bg-white/75 px-6 py-3 text-sm font-semibold text-(--theme-text) transition hover:bg-white"
						>
							See downloads
						</a>
					</div>
				</div>
			</section>
		</div>
	</div>

	<div class="border-t border-(--theme-border) bg-(--theme-section-bg)]">
		<div
			class="mx-auto flex max-w-7xl flex-col gap-24 px-6 py-16 lg:px-10 lg:py-24"
		>
			{#each features as feature, index}
				<section
					id={`landing-feature-${index + 1}`}
					data-testid={`landing-feature-${index + 1}`}
					class="grid gap-10 lg:grid-cols-2 lg:items-center"
				>
					{#if index % 2 === 0}
						<div class="space-y-4">
							<div
								class="text-sm uppercase tracking-[0.2em] text-(--theme-accent)"
							>
								{feature.eyebrow}
							</div>
							<h2
								class="max-w-xl text-4xl font-semibold tracking-tight"
								style="font-family: Georgia, 'Times New Roman', serif;"
							>
								{feature.title}
							</h2>
							<p class="max-w-xl text-base leading-8 text-(--theme-text)">
								{feature.description}
							</p>
							<div class="grid gap-3 pt-2">
								{#each feature.points as point}
									<div
										class="rounded-full border border-(--theme-border) bg-white px-4 py-3 text-sm text-(--theme-text) shadow-(--theme-shadow)"
									>
										{point}
									</div>
								{/each}
							</div>
						</div>
						<div
							class="rounded-[2.2rem] border border-(--theme-border) bg-white p-6 shadow-[0_22px_50px_var(--theme-shadow)]"
						>
							<div
								class="rounded-[1.8rem] p-5"
								style="background: var(--theme-card-gradient);"
							>
								<div
									class="flex items-center justify-between text-sm text-(--theme-muted)"
								>
									<span>Forecast surface</span>
									<span>daily view</span>
								</div>
								<div class="mt-5 grid grid-cols-5 gap-3">
									{#each [18, 24, 31, 22, 14] as height}
										<div class="rounded-[1.2rem] bg-white p-3 shadow-sm">
											<div class="text-xs text-(--theme-muted)">day</div>
											<div class="mt-3 flex h-24 items-end">
												<div
													class="w-full rounded-full"
													style={`height:${height * 3}px; background: var(--theme-bar-gradient);`}
												></div>
											</div>
										</div>
									{/each}
								</div>
							</div>
						</div>
					{:else}
						<div
							class="order-2 rounded-[2.2rem] border border-(--theme-border) bg-white p-6 shadow-[0_22px_50px_var(--theme-shadow)] lg:order-1"
						>
							<div
								class="grid gap-3 rounded-[1.8rem] p-5"
								style="background: var(--theme-card-gradient);"
							>
								<div
									class="flex items-center justify-between text-sm text-(--theme-muted)"
								>
									<span>Live cards</span>
									<span>location ready</span>
								</div>
								<div class="grid gap-3 md:grid-cols-2">
									<div class="rounded-[1.4rem] bg-white p-4 shadow-sm">
										<div
											class="text-xs uppercase tracking-[0.18em] text-(--theme-accent)"
										>
											Wind
										</div>
										<div
											class="mt-3 text-3xl font-semibold"
											style="font-family: Georgia, 'Times New Roman', serif;"
										>
											42 km/h
										</div>
										<div class="mt-2 text-sm text-(--theme-text)">
											windspeed_10m_max + gust watch
										</div>
									</div>
									<div class="rounded-[1.4rem] bg-white p-4 shadow-sm">
										<div
											class="text-xs uppercase tracking-[0.18em] text-(--theme-accent)"
										>
											Rain
										</div>
										<div
											class="mt-3 text-3xl font-semibold"
											style="font-family: Georgia, 'Times New Roman', serif;"
										>
											18 mm
										</div>
										<div class="mt-2 text-sm text-(--theme-text)">
											precipitation_sum with rain_sum split
										</div>
									</div>
									<div class="rounded-[1.4rem] bg-white p-4 shadow-sm">
										<div
											class="text-xs uppercase tracking-[0.18em] text-(--theme-accent)"
										>
											Feels like
										</div>
										<div
											class="mt-3 text-3xl font-semibold"
											style="font-family: Georgia, 'Times New Roman', serif;"
										>
											34°
										</div>
										<div class="mt-2 text-sm text-(--theme-text)">
											apparent temperature range
										</div>
									</div>
									<div class="rounded-[1.4rem] bg-white p-4 shadow-sm">
										<div
											class="text-xs uppercase tracking-[0.18em] text-(--theme-accent)"
										>
											Radiation
										</div>
										<div
											class="mt-3 text-3xl font-semibold"
											style="font-family: Georgia, 'Times New Roman', serif;"
										>
											28 MJ
										</div>
										<div class="mt-2 text-sm text-(--theme-text)">
											shortwave_radiation_sum
										</div>
									</div>
								</div>
							</div>
						</div>
						<div class="order-1 space-y-4 lg:order-2">
							<div
								class="text-sm uppercase tracking-[0.2em] text-(--theme-accent)"
							>
								{feature.eyebrow}
							</div>
							<h2
								class="max-w-xl text-4xl font-semibold tracking-tight"
								style="font-family: Georgia, 'Times New Roman', serif;"
							>
								{feature.title}
							</h2>
							<p class="max-w-xl text-base leading-8 text-(--theme-text)">
								{feature.description}
							</p>
							<div class="grid gap-3 pt-2">
								{#each feature.points as point}
									<div
										class="rounded-full border border-(--theme-border) bg-white px-4 py-3 text-sm text-(--theme-text) shadow-(--theme-shadow)"
									>
										{point}
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</section>
			{/each}

			<!-- <section class="rounded-[2.4rem] border border-[#eadacf] bg-[linear-gradient(180deg,#fffdfb_0%,#fff6ef_100%)] p-8 shadow-[0_22px_50px_rgba(160,124,98,0.1)] lg:p-10">
				<div class="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
					<div class="space-y-4">
						<div class="text-sm uppercase tracking-[0.2em] text-[#c26b4b]">Signals we monitor</div>
						<h2 class="text-4xl font-semibold tracking-tight" style="font-family: Georgia, 'Times New Roman', serif;">
							The landing page now reflects the same variables behind your anomaly logic.
						</h2>
						<p class="max-w-xl text-base leading-8 text-[#5e4b40]">
							These are the daily variables currently positioned as the anomaly inputs for the
							product. They belong in the story because they define what the dashboard is trying
							to catch.
						</p>
					</div>
					<div class="flex flex-wrap gap-3">
						{#each detectVars as variable}
							<div class={`rounded-full border px-4 py-3 text-sm shadow-sm ${
								spotlightVars.includes(variable)
									? 'border-[#e0b39b] bg-[#fff0e5] text-[#8f5034]'
									: 'border-[#eadacf] bg-white text-[#5c4a3f]'
							}`}>
								{variable}
							</div>
						{/each}
					</div>
				</div>
			</section> -->

			<section
				id="downloads"
				class="rounded-[2.4rem] border border-(--theme-border) p-8 shadow-[0_22px_50px_var(--theme-shadow)] lg:p-10"
				style="background: var(--theme-card-gradient);"
			>
				<div class="space-y-6">
					<div class="space-y-4">
						<div
							class="text-sm uppercase tracking-[0.2em] text-(--theme-accent)"
						>
							Downloads
						</div>
						<h2
							class="text-4xl font-semibold tracking-tight"
							style="font-family: Georgia, 'Times New Roman', serif;"
						>
							Get the desktop app when you want the dashboard close by all day.
						</h2>
						<p class="max-w-xl text-base leading-8 text-(--theme-text)">
							The desktop build keeps the anomaly dashboard one click away.
						</p>
					</div>
					<div class="grid gap-4 sm:grid-cols-2 sm:max-w-lg">
						<button
							class="flex items-center justify-center gap-2 rounded-[1.4rem] bg-(--theme-accent-strong) px-5 py-4 text-sm font-semibold text-white shadow-(--theme-shadow)"
							disabled
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								width="16"
								height="16"
								fill="none"
								viewBox="0 0 16 16"
								><path
									fill="currentColor"
									d="M12.665 15.358c-.905.844-1.893.711-2.843.311-1.006-.409-1.93-.427-2.991 0-1.33.551-2.03.391-2.825-.31C-.498 10.886.166 4.078 5.28 3.83c1.246.062 2.114.657 2.843.71 1.09-.213 2.133-.826 3.296-.746 1.393.107 2.446.64 3.138 1.6-2.88 1.662-2.197 5.315.443 6.337-.526 1.333-1.21 2.657-2.345 3.635zM8.03 3.778C7.892 1.794 9.563.16 11.483 0c.268 2.293-2.16 4-3.452 3.777"
								></path></svg
							>
							Download for Apple
						</button>
						<button
							class="flex items-center justify-center gap-2 rounded-[1.4rem] border border-(--theme-border) bg-(--theme-soft-45) px-5 py-4 text-sm font-semibold text-(--theme-text)"
							disabled
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								width="16"
								height="16"
								fill="none"
								viewBox="0 0 16 16"
								><path
									fill="currentColor"
									fill-rule="evenodd"
									d="M0 0h7.584v7.584H0zm8.416 0h7.583v7.584H8.416zm-.832 8.416H0V16h7.584zm.832 0h7.583V16H8.416z"
									clip-rule="evenodd"
								></path></svg
							>
							Download for Windows
						</button>
					</div>
				</div>
			</section>
		</div>
	</div>
</div>
