import type { Severity } from '$lib/types/weather';

const codeMap = new Map<number, string>([
	[0, 'Clear sky'],
	[1, 'Mostly clear'],
	[2, 'Partly cloudy'],
	[3, 'Overcast'],
	[45, 'Fog'],
	[48, 'Depositing rime fog'],
	[51, 'Light drizzle'],
	[53, 'Moderate drizzle'],
	[55, 'Dense drizzle'],
	[61, 'Slight rain'],
	[63, 'Moderate rain'],
	[65, 'Heavy rain'],
	[71, 'Light snow'],
	[73, 'Moderate snow'],
	[75, 'Heavy snow'],
	[80, 'Rain showers'],
	[81, 'Strong rain showers'],
	[82, 'Violent rain showers'],
	[95, 'Thunderstorm'],
	[96, 'Thunderstorm with hail'],
	[99, 'Severe hailstorm']
]);

export function weatherCodeLabel(code: number) {
	return codeMap.get(code) ?? 'Mixed conditions';
}

export function severityClasses(severity: Severity) {
	if (severity === 'high') return 'border-[#e8b6ae] bg-[#fff0ed] text-[#8d3f35]';
	if (severity === 'medium') return 'border-[#ecd1a5] bg-[#fff6e7] text-[#8a5a1f]';
	return 'border-[#c6dae7] bg-[#eef8ff] text-[#345c78]';
}
