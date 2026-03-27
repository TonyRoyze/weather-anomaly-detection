<script lang="ts">
	import { tick } from "svelte";
	import SearchIcon from "@lucide/svelte/icons/search";
	import { computeCommandScore } from "bits-ui";

	import * as Select from "$lib/components/ui/select";
	import { cn } from "$lib/utils";

	type SelectItem = {
		value: string;
		label: string;
	};

	let {
		value = $bindable(""),
		items,
		triggerId,
		triggerTestId,
		labelledBy,
		placeholder = "Search...",
		emptyMessage = "No matches found.",
		inputClass,
		contentClass,
		itemClass,
		onValueChange = (_value: string) => {},
	}: {
		value?: string;
		items: SelectItem[];
		triggerId?: string;
		triggerTestId?: string;
		labelledBy?: string;
		placeholder?: string;
		emptyMessage?: string;
		inputClass?: string;
		contentClass?: string;
		itemClass?: string;
		onValueChange?: (value: string) => void;
	} = $props();

	let open = $state(false);
	let searchValue = $state("");
	let searchInput = $state<HTMLInputElement | null>(null);

	const selectedLabel = $derived.by(() => {
		return items.find((item) => item.value === value)?.label ?? "";
	});

	const filteredItems = $derived.by(() => {
		const query = searchValue.trim().toLowerCase();
		if (!query) return items;

		return items
			.map((item) => {
				const label = item.label.toLowerCase();
				const exactMatch = label === query ? 3 : 0;
				const startsWithMatch = label.startsWith(query) ? 2 : 0;
				const includesMatch = label.includes(query) ? 1 : 0;
				const fuzzyScore = computeCommandScore(item.label, query);

				return {
					item,
					score: exactMatch + startsWithMatch + includesMatch + fuzzyScore,
				};
			})
			.filter(({ score }) => score > 0)
			.sort((left, right) => {
				if (right.score !== left.score) return right.score - left.score;
				return left.item.label.localeCompare(right.item.label);
			})
			.map(({ item }) => item);
	});

	const closestItem = $derived.by(() => filteredItems[0] ?? null);

	function commitValue(nextValue: string) {
		value = nextValue;
		onValueChange(nextValue);
		open = false;
	}

	function commitClosestMatch() {
		if (!searchValue.trim() || !closestItem) return;
		commitValue(closestItem.value);
	}

	async function handleOpenChange(nextOpen: boolean) {
		open = nextOpen;
		if (nextOpen) {
			searchValue = "";
			await tick();
			searchInput?.focus();
			return;
		}

		commitClosestMatch();
		searchValue = "";
	}

	function handleValueChange(nextValue: string) {
		commitValue(nextValue);
		searchValue = "";
	}

	function handleSearchKeydown(event: KeyboardEvent) {
		if (event.key === "Enter" && closestItem) {
			event.preventDefault();
			commitClosestMatch();
			return;
		}

		if (event.key === "ArrowDown" && filteredItems.length > 0) {
			event.preventDefault();
			const firstItem = document.querySelector<HTMLElement>(
				'[data-slot="select-item"]',
			);
			firstItem?.focus();
		}
	}
</script>

<Select.Root
	type="single"
	{items}
	{value}
	{open}
	onOpenChange={handleOpenChange}
	onValueChange={handleValueChange}
>
	<Select.Trigger
		id={triggerId}
		data-testid={triggerTestId}
		aria-labelledby={labelledBy}
		class={cn("w-full", inputClass)}
	>
		{selectedLabel || placeholder}
	</Select.Trigger>

	<Select.Content
		side="bottom"
		align="start"
		sideOffset={8}
		avoidCollisions={false}
		class={cn(
			"min-w-(--bits-select-anchor-width) overflow-hidden p-0",
			contentClass,
		)}
	>
		<div
			class="sticky top-0 z-10 border-b border-(--theme-border) bg-(--theme-bg)"
		>
			<div class="relative">
				<input
					bind:this={searchInput}
					type="text"
					placeholder="Search..."
					autocomplete="off"
					bind:value={searchValue}
					onkeydown={handleSearchKeydown}
					class="w-full border-none bg-transparent py-3 pr-4 pl-11 text-sm text-(--theme-text) outline-none placeholder:text-(--theme-muted)"
				/>
				<SearchIcon
					class="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-(--theme-muted)"
				/>
			</div>
		</div>

		{#if filteredItems.length === 0}
			<div class="px-3 py-3 text-sm text-(--theme-muted)">
				{emptyMessage}
			</div>
		{:else}
			{#each filteredItems as item (item.value)}
				<Select.Item
					value={item.value}
					label={item.label}
					class={cn(itemClass)}
				>
					{item.label}
				</Select.Item>
			{/each}
		{/if}
	</Select.Content>
</Select.Root>
