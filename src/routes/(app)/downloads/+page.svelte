<script lang="ts">
	const platforms = [
		{
			name: "Apple",
			copy: "Download for Apple",
			styles: "bg-(--theme-accent-strong) text-white shadow-(--theme-shadow)",
		},
		{
			name: "Windows",
			copy: "Download for Windows",
			styles:
				"border border-(--theme-border) bg-(--theme-soft-45) text-(--theme-text)",
		},
	];
</script>

<svelte:head>
	<title>Anomalize Downloads</title>
	<meta
		name="description"
		content="Download page for the Anomalize desktop app with Apple and Windows installer actions."
	/>
</svelte:head>

<div class="flex flex-col gap-8">
	<section
		id="downloads-overview"
		data-testid="downloads-overview"
		class="rounded-[2.4rem] border border-(--theme-border) p-8 shadow-[0_22px_50px_var(--theme-shadow)] lg:p-10"
		style="background: var(--theme-card-gradient);"
	>
		<div class="grid gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
			<div id="downloads-copy" data-testid="downloads-copy" class="space-y-4">
				<div class="text-sm uppercase tracking-[0.2em] text-(--theme-accent)">
					Downloads
				</div>
				<h1
					class="text-4xl font-semibold tracking-tight text-(--theme-text)"
					style="font-family: Georgia, 'Times New Roman', serif;"
				>
					Download Anomalize in the same calm product theme as the landing page.
				</h1>
				<p class="max-w-xl text-base leading-8 text-(--theme-text)">
					This page is intentionally simple: just the installer actions you
					asked for, plus a short note on release readiness.
				</p>
				<div class="flex flex-wrap gap-3">
					<a
						href="/"
						id="downloads-back-home"
						data-testid="downloads-back-home"
						class="rounded-full border border-(--theme-border) bg-white px-6 py-3 text-sm font-semibold text-(--theme-text) transition hover:bg-(--theme-soft)"
					>
						Back to landing
					</a>
					<a
						href="/dashboard"
						id="downloads-open-dashboard"
						data-testid="downloads-open-dashboard"
						class="rounded-full bg-(--theme-accent-strong) px-6 py-3 text-sm font-semibold text-white shadow-(--theme-shadow) transition hover:bg-(--theme-accent)"
					>
						Open dashboard
					</a>
				</div>
			</div>

			<div
				id="downloads-actions"
				data-testid="downloads-actions"
				class="rounded-[2rem] border border-(--theme-border) bg-white p-6 shadow-(--theme-shadow)"
			>
				<div class="grid gap-4 sm:grid-cols-2">
					{#each platforms as platform}
						<button
							id={`download-${platform.name.toLowerCase()}`}
							data-testid={`download-${platform.name.toLowerCase()}`}
							class={`rounded-[1.4rem] px-5 py-4 text-sm font-semibold ${platform.styles}`}
							disabled
						>
							{platform.copy}
						</button>
					{/each}
				</div>
				<div
					id="downloads-status"
					data-testid="downloads-status"
					class="mt-5 rounded-[1.4rem] border border-(--theme-border) bg-(--theme-soft-45) p-4 text-sm leading-7 text-(--theme-text)"
				>
					Installers are not live yet. The buttons are in place so we can hook
					them up as soon as packaging is ready.
				</div>
			</div>
		</div>
	</section>
</div>
