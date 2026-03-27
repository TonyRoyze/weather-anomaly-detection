<script lang="ts">
	import { page } from "$app/state";
	import CloudDownloadIcon from "@lucide/svelte/icons/cloud-download";
	import DatabaseIcon from "@lucide/svelte/icons/database";
	import LayoutDashboardIcon from "@lucide/svelte/icons/layout-dashboard";
	import LineChartIcon from "@lucide/svelte/icons/chart-column";
	import SparklesIcon from "@lucide/svelte/icons/sparkles";
	import logo from "$lib/assets/logo.svg";

	import * as Sidebar from "$lib/components/ui/sidebar/index.js";

	type NavItem = {
		title: string;
		url: string;
		icon: typeof LayoutDashboardIcon;
		description: string;
	};

	const isTauriBuild = import.meta.env.VITE_TAURI_BUILD === "1";

	const items: NavItem[] = [
		{
			title: "Dataset",
			url: "/dashboard/dataset",
			icon: DatabaseIcon,
			description: "Search and filter historical weather rows",
		},
		{
			title: "Dashboard",
			url: "/dashboard",
			icon: LayoutDashboardIcon,
			description: "Date-based anomaly prediction workspace",
		},
		// {
		// 	title: "Forecast",
		// 	url: "/dashboard/forecast",
		// 	icon: LineChartIcon,
		// 	description: "Timeline, alerts, and daily outlook",
		// },
	];

	function isActive(url: string) {
		return page.url.pathname === url;
	}
</script>

<Sidebar.Root id="app-sidebar" data-testid="app-sidebar" variant="floating">
	<Sidebar.Header>
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton size="lg">
					{#snippet child({ props })}
						<a
							id="sidebar-home-link"
							data-testid="sidebar-home-link"
							href="/"
							onclick={(event) => {
								if (isTauriBuild) event.preventDefault();
							}}
							{...props}
						>
							<div
								class="flex size-8 items-center justify-center rounded-lg bg-white"
							>
								<img src={logo} alt="Anomalize logo" class="h-5 w-auto" />
							</div>
							<div class="flex flex-col gap-0.5 leading-none">
								<span
									class="font-medium"
									style="font-family: Georgia, 'Times New Roman', serif;"
									>Anomalize</span
								>
								<span class="text-xs text-(--theme-muted)"
									>Weather anomaly workspace</span
								>
							</div>
						</a>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Header>

	<Sidebar.Content>
		<Sidebar.Group>
			<Sidebar.GroupLabel class="text-(--theme-muted)"
				>Workspace</Sidebar.GroupLabel
			>
			<Sidebar.Menu class="gap-2">
				{#each items as item (item.url)}
					<Sidebar.MenuItem>
						<Sidebar.MenuButton isActive={isActive(item.url)}>
							{#snippet child({ props })}
								{@const Icon = item.icon}
								<a
									id={`sidebar-link-${item.title.toLowerCase().replaceAll(" ", "-")}`}
									data-testid={`sidebar-link-${item.title.toLowerCase().replaceAll(" ", "-")}`}
									href={item.url}
									title={item.title}
									{...props}
								>
									<Icon class="size-4" />
									<div class="flex flex-col">
										<span>{item.title}</span>
										<span class="text-xs text-(--theme-muted)"
											>{item.description}</span
										>
									</div>
								</a>
							{/snippet}
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
				{/each}
			</Sidebar.Menu>
		</Sidebar.Group>
	</Sidebar.Content>

	<Sidebar.Footer>
		<div
			class="rounded-2xl border border-(--theme-border) bg-white/90 p-4 text-sm text-(--theme-text)"
		>
			Data source: Open-Meteo
		</div>
	</Sidebar.Footer>
</Sidebar.Root>
