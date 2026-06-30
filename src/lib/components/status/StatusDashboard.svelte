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
	import { showSidebar } from '$lib/stores';

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
	let columnCount = 1;
	let settingsOpen = false;
	$: moduleColumns = Array.from({ length: columnCount }, (_, columnIndex) =>
		moduleOrder.filter((_, index) => index % columnCount === columnIndex)
	);

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
	const shortDate = (date: string | undefined) => date?.slice(5) ?? '';

	const updateColumnCount = () => {
		if (window.innerWidth >= 1180) {
			columnCount = 3;
		} else if (window.innerWidth >= 768) {
			columnCount = 2;
		} else {
			columnCount = 1;
		}
	};

	onMount(() => {
		loadOrder();
		loadStatus();
		updateColumnCount();
		window.addEventListener('resize', updateColumnCount);
		return () => window.removeEventListener('resize', updateColumnCount);
	});
</script>

<svelte:head>
	<title>Status</title>
</svelte:head>

<div
	class="status-shell flex h-screen max-h-[100dvh] w-full max-w-full flex-col bg-white text-gray-900 transition-width duration-200 ease-in-out dark:bg-gray-950 dark:text-gray-100 {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<header
		class="z-20 flex shrink-0 items-center justify-between gap-3 border-b border-gray-200 bg-white px-2 py-3 dark:border-gray-850 dark:bg-gray-950 sm:px-3"
	>
		<div class="min-w-0">
			<h1 class="truncate text-lg font-semibold leading-6">Status</h1>
			<p class="truncate text-xs text-gray-500 dark:text-gray-400">
				{data?.scope === 'global' ? 'Global Citadel telemetry' : 'Your Citadel telemetry'} · Last {days}
				days
			</p>
		</div>
		<div class="flex items-center gap-2">
			<select
				class="h-9 min-w-0 rounded-lg border border-gray-200 bg-white px-2 text-sm dark:border-gray-800 dark:bg-gray-900"
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
		<div class="status-content flex items-center justify-center">
			<Spinner className="size-5" />
		</div>
	{:else if error}
		<div class="status-content px-2 py-8 text-sm text-red-600 dark:text-red-300 sm:px-3">
			{error}
		</div>
	{:else if data}
		<main class="status-content">
			<div class="status-columns" style={`--status-columns: ${columnCount}`}>
				{#each moduleColumns as column, columnIndex (columnIndex)}
					<div class="status-column">
						{#each column as moduleId (moduleId)}
							<section
								class="status-module rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-850 dark:bg-gray-900"
								aria-label={moduleLabels[moduleId]}
							>
								<div
									class="flex items-center justify-between gap-3 border-b border-gray-100 px-3 py-3 dark:border-gray-850 sm:px-4"
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
									<div class="space-y-4 p-3 sm:p-4">
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
									<div class="p-3 sm:p-4">
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
												<div class="status-table-head skill-table-grid">
													<span>Skill</span><span>Uses</span><span>Views</span><span>Patches</span>
												</div>
												{#each topSkills() as skill}
													<div class="status-table-row skill-table-grid">
														<span class="truncate" title={skill.name}>{skill.name}</span>
														<span>{skill.use_count}</span>
														<span>{skill.view_count}</span>
														<span>{skill.patch_count}</span>
													</div>
												{/each}
											</div>
										{:else}
											<p class="text-sm text-gray-500 dark:text-gray-400">
												No skill usage data yet.
											</p>
										{/if}
									</div>
								{:else if moduleId === 'overview'}
									<div class="grid grid-cols-2 gap-3 p-3 sm:p-4">
										{#each [['Sessions', formatNumber(data.total_sessions)], ['Messages', formatNumber(data.total_messages)], ['Tokens', formatTokens(data.total_tokens)], ['Estimated Cost', formatCost(data.total_cost)]] as [label, value]}
											<div class="rounded-md bg-gray-50 p-3 dark:bg-gray-950">
												<div class="text-xs text-gray-500">{label}</div>
												<div class="text-xl font-semibold">{value}</div>
											</div>
										{/each}
									</div>
								{:else if moduleId === 'daily-tokens'}
									<div class="p-3 sm:p-4">
										<div class="flex h-56 items-end gap-1 overflow-hidden">
											{#each data.daily_tokens as row}
												{@const total =
													Number(row.input_tokens || 0) + Number(row.output_tokens || 0)}
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
												</div>
											{/each}
										</div>
										<div class="mt-1 flex justify-between text-[10px] text-gray-400">
											<span>{shortDate(data.daily_tokens[0]?.date)}</span>
											<span>{shortDate(data.daily_tokens[data.daily_tokens.length - 1]?.date)}</span
											>
										</div>
										<div class="mt-3 flex gap-4 text-xs text-gray-500">
											<span
												><i class="mr-1 inline-block h-2 w-2 rounded-sm bg-indigo-500"
												></i>Input</span
											>
											<span
												><i class="mr-1 inline-block h-2 w-2 rounded-sm bg-cyan-500"
												></i>Output</span
											>
										</div>
									</div>
								{:else if moduleId === 'model-breakdown'}
									<div class="p-3 sm:p-4">
										{#if data.models.length}
											<div class="status-table">
												<div class="status-table-head model-table-grid">
													<span>Model</span><span>Messages</span><span>Tokens</span><span>Cost</span
													><span>Share</span>
												</div>
												{#each data.models as model}
													<div class="status-table-row model-table-grid">
														<span class="truncate" title={model.model}>{model.model}</span>
														<span>{formatNumber(model.messages)}</span>
														<span>{formatTokens(model.total_tokens)}</span>
														<span>{formatCost(model.cost)}</span>
														<span>{model.cost_share || model.token_share}%</span>
													</div>
												{/each}
											</div>
										{:else}
											<p class="text-sm text-gray-500 dark:text-gray-400">
												No model usage data yet.
											</p>
										{/if}
									</div>
								{:else if moduleId === 'token-breakdown'}
									<div class="space-y-3 p-3 sm:p-4">
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
									<div class="space-y-2 p-3 sm:p-4">
										{#each data.activity_by_day as row}
											<div class="grid grid-cols-[36px_1fr_40px] items-center gap-2 text-xs">
												<span>{row.day}</span>
												<div class="h-2 rounded-full bg-gray-100 dark:bg-gray-800">
													<div
														class="h-2 rounded-full bg-amber-500"
														style="width: {(row.sessions / maxSessions(data.activity_by_day)) *
															100}%"
													></div>
												</div>
												<span class="text-right text-gray-500">{row.sessions}</span>
											</div>
										{/each}
									</div>
								{:else if moduleId === 'activity-hour'}
									<div class="space-y-1 p-3 sm:p-4">
										{#each data.activity_by_hour as row}
											<div class="grid grid-cols-[32px_1fr_36px] items-center gap-2 text-xs">
												<span>{String(row.hour).padStart(2, '0')}</span>
												<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
													<div
														class="h-1.5 rounded-full bg-rose-500"
														style="width: {(row.sessions / maxSessions(data.activity_by_hour)) *
															100}%"
													></div>
												</div>
												<span class="text-right text-gray-500">{row.sessions}</span>
											</div>
										{/each}
									</div>
								{/if}
							</section>
						{/each}
					</div>
				{/each}
			</div>
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
	.status-shell {
		min-width: 0;
		overflow-x: hidden;
	}

	.status-content {
		flex: 1 1 auto;
		min-height: 0;
		overflow-y: auto;
		overflow-x: hidden;
		background: inherit;
	}

	.status-columns {
		display: grid;
		grid-template-columns: repeat(var(--status-columns), minmax(0, 1fr));
		gap: 0.75rem;
		padding: 0.75rem 0.5rem 1rem;
		width: 100%;
	}

	.status-column {
		display: flex;
		min-width: 0;
		flex-direction: column;
		gap: 0.75rem;
	}

	@media (min-width: 1180px) {
		.status-columns,
		.status-column {
			gap: 0.875rem;
		}

		.status-columns {
			padding: 0.875rem 0.75rem 1rem;
		}
	}

	.status-module {
		min-width: 0;
		overflow: hidden;
	}

	.status-table {
		max-width: 100%;
		overflow: hidden;
	}

	.status-table-head,
	.status-table-row {
		display: grid;
		gap: 0.375rem;
		align-items: center;
		min-width: 0;
	}

	.skill-table-grid {
		grid-template-columns: minmax(0, 1fr) 3rem 3rem 3.25rem;
	}

	.model-table-grid {
		grid-template-columns: minmax(0, 1fr) 2.9rem 3.4rem 2.9rem 2.6rem;
	}

	.status-table-head span:not(:first-child),
	.status-table-row span:not(:first-child) {
		text-align: right;
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

	@media (min-width: 480px) {
		.status-table-head,
		.status-table-row {
			gap: 0.75rem;
		}

		.skill-table-grid {
			grid-template-columns: minmax(0, 1fr) 4rem 4rem 4rem;
		}

		.model-table-grid {
			grid-template-columns: minmax(0, 1fr) 4rem 4.5rem 4rem 3.5rem;
		}
	}

	:global(.dark) .status-table-row {
		border-top-color: rgb(31 41 55);
	}
</style>
