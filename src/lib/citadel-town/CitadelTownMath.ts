import type { AgentTownPoint } from './CitadelTownTypes';

export const TOWN_WORLD = {
	width: 960,
	height: 720
};

export const clamp = (value: number, min: number, max: number) =>
	Math.min(max, Math.max(min, value));

export const lerp = (from: number, to: number, amount: number) => from + (to - from) * amount;

export const distance = (a: AgentTownPoint, b: AgentTownPoint) => Math.hypot(a.x - b.x, a.y - b.y);

export const deterministicIndex = (value: string, modulo: number) => {
	let hash = 0;
	for (let index = 0; index < value.length; index += 1) {
		hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
	}
	return modulo > 0 ? hash % modulo : 0;
};

export const formatCompactNumber = (value: number) => {
	const number = Number(value || 0);
	if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`;
	if (number >= 1_000) return `${(number / 1_000).toFixed(1)}K`;
	return number.toLocaleString();
};
