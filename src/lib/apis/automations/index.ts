import { WEBUI_API_BASE_URL } from '$lib/constants';

const HERMES_AUTOMATIONS_API = '/automations/hermes/cron';

export type AutomationTerminalConfig = {
	server_id: string;
	cwd?: string;
};

export type AutomationData = {
	prompt: string;
	profile: string;
	schedule: string;
	model_id?: string;
	rrule?: string;
	terminal?: AutomationTerminalConfig;
};

export type AutomationForm = {
	name: string;
	data: AutomationData;
	meta?: {
		system_prompt?: string;
		temperature?: number;
		max_tokens?: number;
		webhook?: string;
	};
	is_active?: boolean;
};

export type AutomationRunModel = {
	id: string;
	automation_id: string;
	chat_id: string | null;
	status: string;
	error: string | null;
	created_at: string | number;
	filename?: string | null;
	snippet?: string | null;
	content?: string | null;
	usage?: Record<string, any> | null;
};

export type AutomationResponse = {
	id: string;
	job_id: string;
	profile: string;
	profile_name?: string;
	user_id?: string;
	name: string;
	data: AutomationData;
	meta: Record<string, any> | null;
	is_active: boolean;
	state: string;
	running: boolean;
	enabled: boolean;
	last_status: string | null;
	last_error?: string | null;
	schedule_display: string | null;
	last_run_at: string | number | null;
	next_run_at: string | number | null;

	created_at: string | number | null;
	updated_at?: string | number | null;
	last_run: AutomationRunModel | null;
	next_runs: (string | number)[] | null;
};

export const encodeAutomationId = (profile: string, jobId: string) =>
	`${encodeURIComponent(profile || 'default')}~${encodeURIComponent(jobId)}`;

export const decodeAutomationId = (id: string) => {
	const [profile, ...jobParts] = `${id}`.split('~');
	const jobId = jobParts.join('~');
	return {
		profile: decodeURIComponent(profile || 'default'),
		jobId: decodeURIComponent(jobId || profile || '')
	};
};

const normalizeSchedule = (job: any) => {
	if (typeof job?.schedule === 'string') return job.schedule;
	if (typeof job?.schedule?.value === 'string') return job.schedule.value;
	if (typeof job?.schedule?.expr === 'string') return job.schedule.expr;
	return job?.schedule_display ?? '';
};

export const normalizeHermesCronJob = (job: any): AutomationResponse => {
	const profile = job?.profile_name ?? job?.profile ?? 'default';
	const jobId = `${job?.id ?? job?.job_id ?? ''}`;
	const state = `${job?.state ?? (job?.enabled === false ? 'paused' : 'scheduled')}`;
	const enabled = job?.enabled !== false && state !== 'paused';
	const schedule = normalizeSchedule(job);

	return {
		...job,
		id: encodeAutomationId(profile, jobId),
		job_id: jobId,
		profile,
		profile_name: job?.profile_name ?? profile,
		name: job?.name || jobId || 'Automation',
		data: {
			prompt: job?.prompt ?? '',
			profile,
			schedule,
			rrule: schedule,
			model_id: `hermes:${profile}`
		},
		meta: job?.meta ?? {
			citadel_user: job?.citadel_user ?? null,
			origin: job?.origin ?? null
		},
		is_active: enabled,
		state,
		running: state === 'running',
		enabled,
		last_status: job?.last_status ?? null,
		last_error: job?.last_error ?? null,
		schedule_display: job?.schedule_display ?? schedule,
		last_run_at: job?.last_run_at ?? null,
		next_run_at: job?.next_run_at ?? null,
		created_at: job?.created_at ?? null,
		updated_at: job?.updated_at ?? null,
		last_run: null,
		next_runs: job?.next_run_at ? [job.next_run_at] : null
	};
};

const parseApiResponse = async (res: Response) => {
	const contentType = res.headers.get('content-type') ?? '';
	const text = await res.text();
	let data: any = null;

	if (text) {
		if (contentType.includes('application/json')) {
			try {
				data = JSON.parse(text);
			} catch {
				throw new Error(`Invalid JSON response from ${res.url}`);
			}
		} else {
			data = { detail: text.trim() || res.statusText };
		}
	}

	if (!res.ok) {
		throw new Error(data?.detail ?? data?.error ?? res.statusText ?? `HTTP ${res.status}`);
	}

	if (contentType.includes('application/json') || !text) {
		return data ?? {};
	}

	throw new Error(`Expected JSON from ${res.url}, got ${contentType || 'unknown content type'}`);
};

const apiFetch = async (token: string, path: string, options: RequestInit = {}) => {
	try {
		const res = await fetch(`${WEBUI_API_BASE_URL}${path}`, {
			...options,
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`,
				...(options.headers ?? {})
			}
		});

		return await parseApiResponse(res);
	} catch (err) {
		console.error(err);
		throw err instanceof Error ? err.message : err;
	}
};

export const getAutomationItems = async (
	token: string,
	query: string | null,
	status: string | null,
	page: number
): Promise<{ items: AutomationResponse[]; total: number }> => {
	const raw = await apiFetch(token, `${HERMES_AUTOMATIONS_API}/jobs?profile=all`);
	const allItems: AutomationResponse[] = (Array.isArray(raw) ? raw : (raw?.jobs ?? [])).map(
		normalizeHermesCronJob
	);
	const queryText = (query ?? '').trim().toLowerCase();
	const filtered = allItems.filter((item: AutomationResponse) => {
		const matchesQuery =
			!queryText ||
			item.name.toLowerCase().includes(queryText) ||
			item.data.prompt.toLowerCase().includes(queryText) ||
			item.profile.toLowerCase().includes(queryText);
		const matchesStatus =
			!status ||
			status === 'all' ||
			(status === 'active' && item.is_active && !item.running) ||
			(status === 'running' && item.running) ||
			(status === 'paused' && !item.is_active) ||
			(status === 'completed' && item.state === 'completed');
		return matchesQuery && matchesStatus;
	});
	const total = filtered.length;
	const start = Math.max(0, ((page || 1) - 1) * 30);
	return { items: filtered.slice(start, start + 30), total };
};

export const createAutomation = async (token: string, form: AutomationForm) => {
	const profile = form.data.profile || 'default';
	const res = await apiFetch(
		token,
		`${HERMES_AUTOMATIONS_API}/jobs?profile=${encodeURIComponent(profile)}`,
		{
			method: 'POST',
			body: JSON.stringify({
				name: form.name,
				prompt: form.data.prompt,
				schedule: form.data.schedule,
				deliver: 'local'
			})
		}
	);
	return normalizeHermesCronJob(res);
};

export const getAutomationById = async (token: string, id: string) => {
	const { profile, jobId } = decodeAutomationId(id);
	const res = await apiFetch(
		token,
		`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}?profile=${encodeURIComponent(profile)}`
	);
	return normalizeHermesCronJob(res);
};

export const updateAutomationById = async (token: string, id: string, form: AutomationForm) => {
	const { profile, jobId } = decodeAutomationId(id);
	const targetProfile = form.data.profile || profile;
	const updates: Record<string, any> = {
		name: form.name,
		prompt: form.data.prompt,
		schedule: form.data.schedule
	};
	const res = await apiFetch(
		token,
		`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}?profile=${encodeURIComponent(targetProfile)}`,
		{
			method: 'PUT',
			body: JSON.stringify({ updates })
		}
	);
	if (form.is_active === false && res?.enabled !== false && res?.state !== 'paused') {
		return normalizeHermesCronJob(
			await apiFetch(
				token,
				`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}/pause?profile=${encodeURIComponent(targetProfile)}`,
				{ method: 'POST' }
			)
		);
	}
	if (form.is_active === true && (res?.enabled === false || res?.state === 'paused')) {
		return normalizeHermesCronJob(
			await apiFetch(
				token,
				`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}/resume?profile=${encodeURIComponent(targetProfile)}`,
				{ method: 'POST' }
			)
		);
	}
	return normalizeHermesCronJob(res);
};

export const toggleAutomationById = async (
	token: string,
	id: string,
	active?: boolean
): Promise<AutomationResponse> => {
	const { profile, jobId } = decodeAutomationId(id);
	const action = active === false ? 'pause' : active === true ? 'resume' : null;
	if (action) {
		return normalizeHermesCronJob(
			await apiFetch(
				token,
				`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}/${action}?profile=${encodeURIComponent(profile)}`,
				{ method: 'POST' }
			)
		);
	}
	const current = await getAutomationById(token, id);
	return await toggleAutomationById(token, id, !current.is_active);
};

export const runAutomationById = async (token: string, id: string) => {
	const { profile, jobId } = decodeAutomationId(id);
	return normalizeHermesCronJob(
		await apiFetch(
			token,
			`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}/trigger?profile=${encodeURIComponent(profile)}`,
			{ method: 'POST' }
		)
	);
};

export const deleteAutomationById = async (token: string, id: string) => {
	const { profile, jobId } = decodeAutomationId(id);
	return await apiFetch(
		token,
		`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}?profile=${encodeURIComponent(profile)}`,
		{ method: 'DELETE' }
	);
};

export const getAutomationRuns = async (
	token: string,
	id: string,
	skip: number = 0,
	limit: number = 50
) => {
	const { profile, jobId } = decodeAutomationId(id);
	const res = await apiFetch(
		token,
		`${HERMES_AUTOMATIONS_API}/jobs/${encodeURIComponent(jobId)}/runs?profile=${encodeURIComponent(profile)}&limit=${limit}`
	);
	const runs = (res?.runs ?? []).map((run: any) => ({
		id:
			run.id ??
			run.filename ??
			run.session_id ??
			`${jobId}-${run.started_at ?? run.created_at ?? ''}`,
		automation_id: id,
		chat_id: run.chat_id ?? run.session_id ?? null,
		status: run.status ?? (run.ended_at || run.ended_at === 0 ? 'success' : 'running'),
		error: run.error ?? null,
		created_at: run.created_at ?? run.started_at ?? run.modified ?? Date.now(),
		filename: run.filename ?? null,
		snippet: run.snippet ?? null,
		content: run.content ?? null,
		usage: run.usage ?? null
	}));
	return skip > 0 ? runs.slice(skip) : runs;
};
