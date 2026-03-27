export const paletteOptions = [
	{ value: "sky", label: "Sky" },
	{ value: "warm", label: "Warm" },
	{ value: "slate", label: "Slate" },
] as const;

export type PaletteName = (typeof paletteOptions)[number]["value"];

export const DEFAULT_PALETTE: PaletteName = "sky";
export const PALETTE_STORAGE_KEY = "anomalize-palette";

export function isPaletteName(value: string | null | undefined): value is PaletteName {
	return paletteOptions.some((option) => option.value === value);
}

export function applyPalette(palette: PaletteName) {
	if (typeof document === "undefined") return;
	document.documentElement.dataset.palette = palette;
	localStorage.setItem(PALETTE_STORAGE_KEY, palette);
}

export function getStoredPalette(): PaletteName {
	if (typeof document === "undefined") return DEFAULT_PALETTE;
	const current = document.documentElement.dataset.palette;
	if (isPaletteName(current)) return current;
	const stored = localStorage.getItem(PALETTE_STORAGE_KEY);
	return isPaletteName(stored) ? stored : DEFAULT_PALETTE;
}
