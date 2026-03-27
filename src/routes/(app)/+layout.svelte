<script lang="ts">
	import { page } from "$app/state";
	import AppNavigationSidebar from "$lib/components/app-navigation-sidebar.svelte";
	import ThemePaletteSwitcher from "$lib/components/theme-palette-switcher.svelte";
	import { Separator } from "$lib/components/ui/separator/index.js";
	import * as Sidebar from "$lib/components/ui/sidebar/index.js";

	let { children } = $props();

	const titles: Record<string, string> = {
		"/dashboard": "Dashboard",
		"/dashboard/forecast": "Forecast",
		"/dashboard/dataset": "Dataset",
		"/downloads": "Downloads",
	};

	const subtitles: Record<string, string> = {
		"/dashboard": "Date-based anomaly prediction and category scoring.",
		"/dashboard/forecast":
			"Timeline, detected anomalies, and the 5-day operational outlook.",
		"/dashboard/dataset":
			"Search, filter, and inspect the bundled Sri Lanka weather dataset.",
		"/downloads":
			"Get the desktop builds and install instructions for the Tauri shell.",
	};

	const title = $derived(titles[page.url.pathname] ?? "Workspace");
	const subtitle = $derived(
		subtitles[page.url.pathname] ?? "Weather monitoring workspace",
	);
</script>

<div
	class="min-h-screen text-(--theme-text)"
	style="background: var(--theme-app-gradient);"
>
	<Sidebar.Provider
		style="--sidebar-width: 21rem; --sidebar-width-icon: 4rem; --sidebar: var(--theme-section-bg); --sidebar-foreground: var(--theme-text); --sidebar-border: var(--theme-border); --sidebar-accent: var(--theme-soft); --sidebar-accent-foreground: var(--theme-text); --sidebar-primary: var(--theme-accent); --sidebar-primary-foreground: #ffffff; --sidebar-ring: var(--theme-border);"
	>
		<AppNavigationSidebar />
		<Sidebar.Inset>
			<header
				class="sticky top-0 z-20 flex items-center gap-3 border-b border-(--theme-border) bg-(--theme-section-bg)/90 px-4 py-4 backdrop-blur lg:px-6"
			>
				<Sidebar.Trigger class="-ms-1" />
				<Separator
					orientation="vertical"
					class="data-[orientation=vertical]:h-5 bg-(--theme-border)"
				/>
				<div class="min-w-0 flex-1">
					<div
						class="text-lg font-semibold"
						style="font-family: Georgia, 'Times New Roman', serif;"
					>
						{title}
					</div>
					<p class="truncate text-sm text-(--theme-muted)">{subtitle}</p>
				</div>
				<ThemePaletteSwitcher />
			</header>
			<main
				class="mx-auto flex w-full max-w-7xl flex-1 flex-col px-4 py-6 lg:px-6"
			>
				{@render children()}
			</main>
		</Sidebar.Inset>
	</Sidebar.Provider>
</div>
