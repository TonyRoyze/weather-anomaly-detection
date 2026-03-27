<script lang="ts">
	import { onMount } from "svelte";

	import {
		applyPalette,
		getStoredPalette,
		paletteOptions,
		type PaletteName,
	} from "$lib/theme";

	let currentPalette = $state<PaletteName>("slate");

	function selectPalette(palette: PaletteName) {
		currentPalette = palette;
		applyPalette(palette);
	}

	onMount(() => {
		currentPalette = getStoredPalette();
	});
</script>

<div
	class="flex flex-wrap items-center gap-2 rounded-full border border-(--theme-border) bg-white/80 p-1 text-sm shadow-(--theme-shadow)"
>
	{#each paletteOptions as option}
		<button
			type="button"
			class={`rounded-full px-3 py-1.5 font-medium transition ${
				currentPalette === option.value
					? "bg-(--theme-accent-strong) text-white"
					: "text-(--theme-text) hover:bg-(--theme-soft-45)"
			}`}
			onclick={() => selectPalette(option.value)}
		>
			{option.label}
		</button>
	{/each}
</div>
