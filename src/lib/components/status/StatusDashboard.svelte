<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Settings from '$lib/components/icons/Settings.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { getStatusSummary, type StatusSummary } from '$lib/apis/status';

	const ORDER_STORAGE_KEY = 'citadel-status-module-order';
	const DEFAULT_ORDER = [
		'system-health',
		'skill-usage',
		'overview',
		'daily-tokens',
		'model-breakdown',
		'token-breakdown',
		'activity-day',
		'activity-hour'
	];

	const moduleLabels: Record<string, string> = {
		'system-health': 'System Health',
		'skill-usage': 'Skill Usage',
		overview: 'Overview',
		'daily-tokens': 'Daily Tokens',
		'model-breakdown': 'Models',
		'token-breakdown': 'Token Breakdown',
		'activity-day': 'Activity by Day',
		'activity-hour': 'Activity by Hour'
	};

	let loading = true;
	let refreshing = false;
	let error = '';
	let days = 30;
	let data: StatusSummary | null = null;
	let moduleOrder = [...DEFAULT_ORDER];
	let settingsOpen = false;
	let draggedModule = '';

	const loadOrder = () => {
		try {
			const stored = JSON.parse(localStorage.getItem(ORDER_STORAGE_KEY) ?? '[]');
			if (Array.isArray(stored)) {
				const known = stored.filter((id) => DEFAULT_ORDER.includes(id));
				moduleOrder = [...known, ...DEFAULT_ORDER.filter((id) => !known.includes(id))];
			}
		} catch {
			moduleOrder = [...DEFAULT_ORDER];
		}
	};

	const saveOrder = () => {
		localStorage.setItem(ORDER_STORAGE_KEY, JSON.stringify(moduleOrder));
	};

	const moveModule = (id: string, direction: -1 | 1) => {
		const index = moduleOrder.indexOf(id);
		const next = index + direction;
		if (index < 0 || next < 0 || next >= moduleOrder.length) return;
		const order = [...moduleOrder];
		order.splice(index, 1);
		order.splice(next, 0, id);
		moduleOrder = order;
		saveOrder();
	};

	const dropModule = (target: string) => {
		if (!draggedModule || draggedModule === target) return;
		const order = moduleOrder.filter((id) => id !== draggedModule);
		const targetIndex = order.indexOf(target);
		order.splice(targetIndex, 0, draggedModule);
		moduleOrder = order;
		draggedModule = '';
		saveOrder();
	};

	const loadStatus = async (animate = false) => {
		error = '';
		refreshing = animate;
		try {
			data = await getStatusSummary(localStorage.token, days);
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
			toast.error(error);
		} finally {
			loading = false;
			refreshing = false;
		}
	};

	const formatNumber = (value: number | undefined) => Number(value ?? 0).toLocaleString();
	const formatTokens = (value: number | undefined) => {
		const number = Number(value ?? 0);
		if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`;
		if (number >= 1_000) return `${(number / 1_000).toFixed(1)}K`;
		return formatNumber(number);
	};
	const formatCost = (value: number | undefined) => {
		const number = Number(value ?? 0);
		if (!number) return 'N/A';
		return `$${number.toFixed(number < 1 ? 4 : 2)}`;
	};

	const maxDaily = () =>
		Math.max(
			...(data?.daily_tokens ?? []).map(
				(row) => Number(row.input_tokens || 0) + Number(row.output_tokens || 0)
			),
			1
		);
	const maxSessions = (rows: { sessions: number }[]) =>
		Math.max(...rows.map((row) => Number(row.sessions || 0)), 1);
	const healthMetrics = (summary: StatusSummary) => [
		{ label: 'CPU', metric: summary.system_health.cpu },
		{ label: 'RAM', metric: summary.system_health.memory },
		{ label: 'Disk', metric: summary.system_health.disk }
	];

	const topSkills = () =>
		Object.entries(data?.skill_usage?.usage ?? {})
			.map(([name, meta]) => ({ name, ...meta }))
			.sort((a, b) => Number(b.use_count || 0) - Number(a.use_count || 0))
			.slice(0, 10);

	onMount(() => {
		loadOrder();
		loadStatus();
	});
</script>

<svelte:head>
	<title>Status</title>
</svelte:head>

<div class="min-h-screen bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100">
	<header
		class="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-gray-200 bg-white/90 px-5 py-3 backdrop-blur dark:border-gray-850 dark:bg-gray-950/90"
	>
		<div class="min-w-0">
			<h1 class="text-lg font-semibold leading-6">Status</h1>
			<p class="text-xs text-gray-500 dark:text-gray-400">
				{data?.scope === 'global' ? 'Global Citadel telemetry' : 'Your Citadel telemetry'} · Last {days}
				days
			</p>
		</div>
		<div class="flex items-center gap-2">
			<select
				class="h-9 rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-800 dark:bg-gray-900"
				bind:value={days}
				on:change={() => loadStatus(true)}
				aria-label="Status period"
			>
				<option value={7}>7 days</option>
				<option value={30}>30 days</option>
				<option value={90}>90 days</option>
				<option value={365}>365 days</option>
			</select>
			<Tooltip content="Refresh">
				<button
					class="flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900"
					on:click={() => loadStatus(true)}
					disabled={refreshing}
					aria-label="Refresh status"
				>
					<Refresh className="size-4 {refreshing ? 'animate-spin' : ''}" />
				</button>
			</Tooltip>
			<Tooltip content="Reorder modules">
				<button
					class="flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900"
					on:click={() => (settingsOpen = true)}
					aria-label="Reorder status modules"
				>
					<Settings className="size-4" />
				</button>
			</Tooltip>
		</div>
	</header>

	{#if loading}
		<div class="flex h-[60vh] items-center justify-center"><Spinner className="size-5" /></div>
	{:else if error}
		<div class="mx-auto max-w-3xl px-5 py-8 text-sm text-red-600 dark:text-red-300">{error}</div>
	{:else if data}
		<main class="mx-auto flex max-w-7xl flex-wrap items-start gap-4 px-5 py-5">
			{#each moduleOrder as moduleId (moduleId)}
				<section
					class="status-module w-full rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-850 dark:bg-gray-900"
					class:wide={moduleId === 'daily-tokens' || moduleId === 'model-breakdown'}
					aria-label={moduleLabels[moduleId]}
					draggable="true"
					on:dragstart={() => (draggedModule = moduleId)}
					on:dragover|preventDefault
					on:drop={() => dropModule(moduleId)}
				>
					<div
						class="flex cursor-grab items-center justify-between gap-3 border-b border-gray-100 px-4 py-3 active:cursor-grabbing dark:border-gray-850"
					>
						<h2 class="text-sm font-semibold">{moduleLabels[moduleId]}</h2>
						<div class="flex items-center gap-1">
							<button
								class="rounded-md p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
								on:click={() => moveModule(moduleId, -1)}
								aria-label="Move {moduleLabels[moduleId]} up"
							>
								<ChevronUp className="size-4" />
							</button>
							<button
								class="rounded-md p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
								on:click={() => moveModule(moduleId, 1)}
								aria-label="Move {moduleLabels[moduleId]} down"
							>
								<ChevronDown className="size-4" />
							</button>
						</div>
					</div>

					{#if moduleId === 'system-health'}
						<div class="space-y-4 p-4">
							{#each healthMetrics(data) as item}
								<div>
									<div class="mb-1 flex justify-between text-xs">
										<span class="font-medium">{item.label}</span>
										<span class="text-gray-500 dark:text-gray-400">{item.metric.label}</span>
									</div>
									<div class="h-2 rounded-full bg-gray-100 dark:bg-gray-800">
										<div
											class="h-2 rounded-full bg-emerald-500"
											style="width: {Math.min(100, Number(item.metric.percent || 0))}%"
										></div>
									</div>
								</div>
							{/each}
						</div>
					{:else if moduleId === 'skill-usage'}
						<div class="p-4">
							<div class="mb-4 grid grid-cols-2 gap-3">
								<div class="rounded-md bg-gray-50 p-3 dark:bg-gray-950">
									<div class="text-xs text-gray-500">Invocations</div>
									<div class="text-xl font-semibold">
										{formatNumber(data.skill_usage.total_invocations)}
									</div>
								</div>
								<div class="rounded-md bg-gray-50 p-3 dark:bg-gray-950">
									<div class="text-xs text-gray-500">Skills Used</div>
									<div class="text-xl font-semibold">
										{formatNumber(data.skill_usage.unique_skills_used)}/{formatNumber(
											data.skill_usage.skill_names.length
										)}
									</div>
								</div>
							</div>
							{#if topSkills().length}
								<div class="status-table">
									<div class="status-table-head grid-cols-[1fr_64px_64px_64px]">
										<span>Skill</span><span>Uses</span><span>Views</span><span>Patches</span>
									</div>
									{#each topSkills() as skill}
										<div class="status-table-row grid-cols-[1fr_64px_64px_64px]">
											<span class="truncate" title={skill.name}>{skill.name}</span>
											<span>{skill.use_count}</span>
											<span>{skill.view_count}</span>
											<span>{skill.patch_count}</span>
										</div>
									{/each}
								</div>
							{:else}
								<p class="text-sm text-gray-500 dark:text-gray-400">No skill usage data yet.</p>
							{/if}
						</div>
					{:else if moduleId === 'overview'}
						<div class="grid grid-cols-2 gap-3 p-4">
							{#each [['Sessions', formatNumber(data.total_sessions)], ['Messages', formatNumber(data.total_messages)], ['Tokens', formatTokens(data.total_tokens)], ['Estimated Cost', formatCost(data.total_cost)]] as [label, value]}
								<div class="rounded-md bg-gray-50 p-3 dark:bg-gray-950">
									<div class="text-xs text-gray-500">{label}</div>
									<div class="text-xl font-semibold">{value}</div>
								</div>
							{/each}
						</div>
					{:else if moduleId === 'daily-tokens'}
						<div class="p-4">
							<div class="flex h-56 items-end gap-1 overflow-hidden">
								{#each data.daily_tokens as row}
									{@const total = Number(row.input_tokens || 0) + Number(row.output_tokens || 0)}
									{@const inputHeight = total
										? Math.max(2, (Number(row.input_tokens || 0) / maxDaily()) * 100)
										: 0}
									{@const outputHeight = total
										? Math.max(2, (Number(row.output_tokens || 0) / maxDaily()) * 100)
										: 0}
									<div
										class="flex min-w-2 flex-1 flex-col items-center justify-end gap-1"
										title={`${row.date} · ${formatTokens(total)} tokens`}
									>
										<div
											class="flex h-44 w-full max-w-5 flex-col justify-end overflow-hidden rounded-t bg-gray-100 dark:bg-gray-800"
										>
											<div class="bg-cyan-500" style="height: {outputHeight}%"></div>
											<div class="bg-indigo-500" style="height: {inputHeight}%"></div>
										</div>
										<span class="hidden text-[10px] text-gray-400 sm:inline"
											>{row.date.slice(5)}</span
										>
									</div>
								{/each}
							</div>
							<div class="mt-3 flex gap-4 text-xs text-gray-500">
								<span><i class="mr-1 inline-block h-2 w-2 rounded-sm bg-indigo-500"></i>Input</span>
								<span><i class="mr-1 inline-block h-2 w-2 rounded-sm bg-cyan-500"></i>Output</span>
							</div>
						</div>
					{:else if moduleId === 'model-breakdown'}
						<div class="p-4">
							{#if data.models.length}
								<div class="status-table">
									<div class="status-table-head grid-cols-[minmax(140px,1fr)_80px_90px_80px_70px]">
										<span>Model</span><span>Messages</span><span>Tokens</span><span>Cost</span><span
											>Share</span
										>
									</div>
									{#each data.models as model}
										<div class="status-table-row grid-cols-[minmax(140px,1fr)_80px_90px_80px_70px]">
											<span class="truncate" title={model.model}>{model.model}</span>
											<span>{formatNumber(model.messages)}</span>
											<span>{formatTokens(model.total_tokens)}</span>
											<span>{formatCost(model.cost)}</span>
											<span>{model.cost_share || model.token_share}%</span>
										</div>
									{/each}
								</div>
							{:else}
								<p class="text-sm text-gray-500 dark:text-gray-400">No model usage data yet.</p>
							{/if}
						</div>
					{:else if moduleId === 'token-breakdown'}
						<div class="space-y-3 p-4">
							<div
								class="flex justify-between border-b border-gray-100 pb-2 text-sm dark:border-gray-850"
							>
								<span>Input</span><strong>{formatTokens(data.total_input_tokens)}</strong>
							</div>
							<div
								class="flex justify-between border-b border-gray-100 pb-2 text-sm dark:border-gray-850"
							>
								<span>Output</span><strong>{formatTokens(data.total_output_tokens)}</strong>
							</div>
							<div class="flex justify-between text-sm">
								<span>Total</span><strong>{formatTokens(data.total_tokens)}</strong>
							</div>
						</div>
					{:else if moduleId === 'activity-day'}
						<div class="space-y-2 p-4">
							{#each data.activity_by_day as row}
								<div class="grid grid-cols-[36px_1fr_40px] items-center gap-2 text-xs">
									<span>{row.day}</span>
									<div class="h-2 rounded-full bg-gray-100 dark:bg-gray-800">
										<div
											class="h-2 rounded-full bg-amber-500"
											style="width: {(row.sessions / maxSessions(data.activity_by_day)) * 100}%"
										></div>
									</div>
									<span class="text-right text-gray-500">{row.sessions}</span>
								</div>
							{/each}
						</div>
					{:else if moduleId === 'activity-hour'}
						<div class="space-y-1 p-4">
							{#each data.activity_by_hour as row}
								<div class="grid grid-cols-[32px_1fr_36px] items-center gap-2 text-xs">
									<span>{String(row.hour).padStart(2, '0')}</span>
									<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
										<div
											class="h-1.5 rounded-full bg-rose-500"
											style="width: {(row.sessions / maxSessions(data.activity_by_hour)) * 100}%"
										></div>
									</div>
									<span class="text-right text-gray-500">{row.sessions}</span>
								</div>
							{/each}
						</div>
					{/if}
				</section>
			{/each}
		</main>
	{/if}
</div>

{#if settingsOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
		role="presentation"
		on:click={() => (settingsOpen = false)}
		on:keydown={(event) => {
			if (event.key === 'Escape') settingsOpen = false;
		}}
	>
		<div
			class="w-full max-w-md rounded-lg border border-gray-200 bg-white shadow-xl dark:border-gray-800 dark:bg-gray-900"
			role="dialog"
			aria-modal="true"
			aria-label="Reorder status modules"
			tabindex="-1"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<div
				class="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-gray-850"
			>
				<h2 class="text-sm font-semibold">Reorder Modules</h2>
				<button
					class="rounded-md p-1 hover:bg-gray-100 dark:hover:bg-gray-800"
					on:click={() => (settingsOpen = false)}
					aria-label="Close"
				>
					<XMark className="size-4" />
				</button>
			</div>
			<div class="space-y-2 p-4">
				{#each moduleOrder as moduleId}
					<div
						class="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 dark:border-gray-800"
					>
						<span class="text-sm">{moduleLabels[moduleId]}</span>
						<div class="flex gap-1">
							<button
								class="rounded-md p-1 hover:bg-gray-100 dark:hover:bg-gray-800"
								on:click={() => moveModule(moduleId, -1)}
								aria-label="Move up"
							>
								<ChevronUp className="size-4" />
							</button>
							<button
								class="rounded-md p-1 hover:bg-gray-100 dark:hover:bg-gray-800"
								on:click={() => moveModule(moduleId, 1)}
								aria-label="Move down"
							>
								<ChevronDown className="size-4" />
							</button>
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}

<style>
	.status-module {
		flex: 1 1 22rem;
		min-width: min(100%, 22rem);
	}

	.status-module.wide {
		flex-basis: 38rem;
	}

	.status-table {
		overflow-x: auto;
	}

	.status-table-head,
	.status-table-row {
		display: grid;
		gap: 0.75rem;
		min-width: 34rem;
		align-items: center;
	}

	.status-table-head {
		padding: 0 0 0.5rem;
		font-size: 0.6875rem;
		font-weight: 600;
		color: rgb(107 114 128);
	}

	.status-table-row {
		border-top: 1px solid rgb(243 244 246);
		padding: 0.625rem 0;
		font-size: 0.8125rem;
	}

	:global(.dark) .status-table-row {
		border-top-color: rgb(31 41 55);
	}
</style>
