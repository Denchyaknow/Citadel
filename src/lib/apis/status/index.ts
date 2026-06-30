import { WEBUI_API_BASE_URL } from '$lib/constants';

export type StatusSummary = {
	period_days: number;
	scope: 'global' | 'user';
	system_health: {
		status: string;
		checked_at: number;
		cpu: { percent: number; label: string };
		memory: { percent: number; label: string };
		disk: { percent: number; label: string };
	};
	skill_usage: {
		usage: Record<string, { use_count: number; view_count: number; patch_count: number }>;
		skill_names: string[];
		total_invocations: number;
		unique_skills_used: number;
		sources: string[];
	};
	total_sessions: number;
	total_messages: number;
	total_input_tokens: number;
	total_output_tokens: number;
	total_tokens: number;
	total_cost: number;
	models: {
		model: string;
		messages: number;
		input_tokens: number;
		output_tokens: number;
		total_tokens: number;
		cost: number;
		token_share: number;
		cost_share: number;
	}[];
	daily_tokens: {
		date: string;
		input_tokens: number;
		output_tokens: number;
		sessions: number;
		cost: number;
	}[];
	activity_by_day: { day: string; sessions: number }[];
	activity_by_hour: { hour: number; sessions: number }[];
};

const parseApiResponse = async (res: Response) => {
	const text = await res.text();
	const data = text ? JSON.parse(text) : {};
	if (!res.ok) {
		throw new Error(data?.detail ?? data?.error ?? res.statusText ?? `HTTP ${res.status}`);
	}
	return data;
};

export const getStatusSummary = async (token: string, days = 30): Promise<StatusSummary> => {
	const params = new URLSearchParams({ days: String(days) });
	const res = await fetch(`${WEBUI_API_BASE_URL}/status/summary?${params.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	});

	return parseApiResponse(res);
};
