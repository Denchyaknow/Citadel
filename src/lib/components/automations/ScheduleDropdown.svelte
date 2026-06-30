<script lang="ts">
	import type i18nType from '$lib/i18n';
	import { getContext } from 'svelte';

	import Dropdown from '$lib/components/common/Dropdown.svelte';

	const i18n: typeof i18nType = getContext('i18n');

	export let frequency = 'DAILY';
	export let interval = 1;
	export let hour = 9;
	export let minute = 0;
	export let selectedDays: string[] = [];
	export let monthDay = 1;
	export let onceDate = '';
	export let onceTime = '09:00';
	export let customSchedule = '';

	export let side: 'top' | 'bottom' = 'top';
	export let align: 'start' | 'end' = 'start';

	/** Optional callback when any value changes */
	export let onChange: () => void = () => {};

	let showDropdown = false;

	$: FREQUENCIES = [
		{ key: 'ONCE', label: $i18n.t('Once') },
		{ key: 'HOURLY', label: $i18n.t('Hourly') },
		{ key: 'DAILY', label: $i18n.t('Daily') },
		{ key: 'WEEKLY', label: $i18n.t('Weekly') },
		{ key: 'MONTHLY', label: $i18n.t('Monthly') },
		{ key: 'CUSTOM', label: $i18n.t('Custom') }
	];

	$: DAYS = [
		{ key: 'MO', label: $i18n.t('Mo', { context: 'day_of_week' }) },
		{ key: 'TU', label: $i18n.t('Tu', { context: 'day_of_week' }) },
		{ key: 'WE', label: $i18n.t('We', { context: 'day_of_week' }) },
		{ key: 'TH', label: $i18n.t('Th', { context: 'day_of_week' }) },
		{ key: 'FR', label: $i18n.t('Fr', { context: 'day_of_week' }) },
		{ key: 'SA', label: $i18n.t('Sa', { context: 'day_of_week' }) },
		{ key: 'SU', label: $i18n.t('Su', { context: 'day_of_week' }) }
	];

	let lastVisualFrequency = 'DAILY';
	let prevFrequency = 'DAILY';

	$: if (frequency !== 'CUSTOM') {
		lastVisualFrequency = frequency;
	}

	$: if (frequency === 'ONCE' && !onceDate) {
		const soon = new Date(Date.now() + 5 * 60_000);
		onceDate = soon.toISOString().split('T')[0];
		onceTime = `${String(soon.getHours()).padStart(2, '0')}:${String(soon.getMinutes()).padStart(2, '0')}`;
	}

	$: {
		if (frequency === 'CUSTOM' && prevFrequency !== 'CUSTOM') {
			customSchedule = buildVisualRrule();
		}
		prevFrequency = frequency;
	}

	const dayToCron: Record<string, string> = {
		SU: '0',
		MO: '1',
		TU: '2',
		WE: '3',
		TH: '4',
		FR: '5',
		SA: '6'
	};

	const cronToDay: Record<string, string> = {
		'0': 'SU',
		'7': 'SU',
		'1': 'MO',
		'2': 'TU',
		'3': 'WE',
		'4': 'TH',
		'5': 'FR',
		'6': 'SA'
	};

	const buildVisualRrule = (): string => {
		return buildSchedule(lastVisualFrequency);
	};

	const buildSchedule = (targetFrequency = frequency): string => {
		if (targetFrequency === 'CUSTOM') return customSchedule;
		if (targetFrequency === 'ONCE') {
			return `${onceDate}T${onceTime}:00`;
		}
		if (targetFrequency === 'HOURLY') {
			return interval > 1 ? `every ${interval}h` : 'every 1h';
		}
		if (targetFrequency === 'DAILY') {
			return `${minute} ${hour} * * *`;
		}
		if (targetFrequency === 'WEEKLY') {
			const days = selectedDays.length ? selectedDays : ['MO'];
			return `${minute} ${hour} * * ${days.map((day) => dayToCron[day] ?? day).join(',')}`;
		}
		if (targetFrequency === 'MONTHLY') {
			return `${minute} ${hour} ${monthDay} * *`;
		}
		return customSchedule;
	};

	export const buildScheduleString = (): string => buildSchedule();

	export const buildRrule = (): string => {
		return buildSchedule();
	};

	export const parseSchedule = (s: string) => {
		const value = (s ?? '').trim();
		if (!value) return;

		const isoMatch = value.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2})?/);
		if (isoMatch) {
			frequency = 'ONCE';
			onceDate = isoMatch[1];
			onceTime = isoMatch[2];
			return;
		}

		const everyMatch = value.match(/^every\s+(\d+)\s*h/i);
		if (everyMatch) {
			frequency = 'HOURLY';
			interval = parseInt(everyMatch[1] || '1');
			return;
		}

		const cronParts = value.split(/\s+/);
		if (cronParts.length === 5) {
			const [minutePart, hourPart, dayPart, monthPart, weekPart] = cronParts;
			const parsedMinute = parseInt(minutePart);
			const parsedHour = parseInt(hourPart);
			if (!Number.isNaN(parsedMinute)) minute = parsedMinute;
			if (!Number.isNaN(parsedHour)) hour = parsedHour;

			if (dayPart === '*' && monthPart === '*' && weekPart === '*') {
				frequency = 'DAILY';
				return;
			}
			if (dayPart === '*' && monthPart === '*' && weekPart !== '*') {
				frequency = 'WEEKLY';
				selectedDays = weekPart
					.split(',')
					.map((day) => cronToDay[day] ?? day)
					.filter(Boolean);
				return;
			}
			if (dayPart !== '*' && monthPart === '*' && weekPart === '*') {
				frequency = 'MONTHLY';
				const parsedDay = parseInt(dayPart);
				if (!Number.isNaN(parsedDay)) monthDay = parsedDay;
				return;
			}
		}

		parseRrule(value);
	};

	export const parseRrule = (s: string) => {
		// Detect ONCE (COUNT=1 with DTSTART)
		if (s.includes('COUNT=1')) {
			frequency = 'ONCE';
			const match = s.match(/DTSTART:(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/);
			if (match) {
				onceDate = `${match[1]}-${match[2]}-${match[3]}`;
				onceTime = `${match[4]}:${match[5]}`;
			}
			return;
		}
		const parts: Record<string, string> = {};
		s.replace('RRULE:', '')
			.split(';')
			.forEach((p) => {
				const [k, v] = p.split('=');
				if (k && v) parts[k] = v;
			});
		const freq = parts.FREQ || 'DAILY';
		if (!['HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY'].includes(freq)) {
			frequency = 'CUSTOM';
			customSchedule = s;
			return;
		}
		frequency = freq;
		interval = parseInt(parts.INTERVAL || '1');
		hour = parseInt(parts.BYHOUR || '9');
		minute = parseInt(parts.BYMINUTE || '0');
		selectedDays = parts.BYDAY ? parts.BYDAY.split(',') : [];
		monthDay = parseInt(parts.BYMONTHDAY || '1');
	};

	export const getScheduleLabel = (): string => {
		if (frequency === 'ONCE') return 'Once';
		if (frequency === 'HOURLY') return 'Hourly';
		if (frequency === 'DAILY') return 'Daily';
		if (frequency === 'WEEKLY') return 'Weekly';
		if (frequency === 'MONTHLY') return 'Monthly';
		if (frequency === 'CUSTOM') return 'Custom';
		return 'Schedule';
	};

	$: scheduleLabel = (() => {
		if (frequency === 'ONCE') return 'Once';
		if (frequency === 'HOURLY') return 'Hourly';
		if (frequency === 'DAILY') return 'Daily';
		if (frequency === 'WEEKLY') return 'Weekly';
		if (frequency === 'MONTHLY') return 'Monthly';
		if (frequency === 'CUSTOM') return 'Custom';
		return 'Schedule';
	})();
</script>

<Dropdown bind:show={showDropdown} {side} {align}>
	<button
		type="button"
		class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-2xl text-xs transition
			text-gray-600 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/5"
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			fill="none"
			viewBox="0 0 24 24"
			stroke-width="1.5"
			stroke="currentColor"
			class="size-3.5"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
			/>
		</svg>
		<span class="whitespace-nowrap">{scheduleLabel}</span>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			fill="none"
			viewBox="0 0 24 24"
			stroke-width="2"
			stroke="currentColor"
			class="size-2.5"
		>
			<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
		</svg>
	</button>

	<div
		slot="content"
		class="rounded-2xl shadow-lg border border-gray-200 dark:border-gray-800 flex flex-col bg-white dark:bg-gray-850 w-48 p-1"
	>
		<div class="px-2 text-xs text-gray-500 pt-1">
			{$i18n.t('Schedule')}
		</div>

		<div class="px-1.5 py-0.5">
			<select
				class="w-full bg-transparent rounded-xl text-xs py-1.5 px-1.5 outline-hidden"
				bind:value={frequency}
				on:click={(e) => e.stopPropagation()}
				on:change={onChange}
			>
				{#each FREQUENCIES as f}
					<option value={f.key}>{f.label}</option>
				{/each}
			</select>
		</div>

		{#if frequency === 'CUSTOM'}
			<div class="px-2 pb-2">
				<input
					type="text"
					bind:value={customSchedule}
					placeholder="every 30m, 0 9 * * *, or 2026-01-15T09:00:00"
					class="w-full bg-transparent outline-hidden text-xs placeholder:text-gray-400 dark:placeholder:text-gray-600"
					on:click={(e) => e.stopPropagation()}
					on:input={onChange}
				/>
			</div>
		{:else if frequency !== 'HOURLY'}
			<div class="flex gap-2 flex-wrap items-center px-3 pb-2 text-xs">
				{#if frequency === 'ONCE'}
					<div class="flex items-center gap-1.5">
						<input
							type="date"
							bind:value={onceDate}
							min={new Date().toISOString().split('T')[0]}
							class="bg-transparent outline-hidden text-xs dark:color-scheme-dark"
							on:click={(e) => e.stopPropagation()}
							on:input={onChange}
						/>
					</div>
					<div class="flex items-center gap-1.5">
						<input
							type="time"
							bind:value={onceTime}
							class="bg-transparent outline-hidden text-xs dark:color-scheme-dark"
							on:click={(e) => e.stopPropagation()}
							on:input={onChange}
						/>
					</div>
				{:else}
					<div class="flex items-center gap-1.5">
						<span class="text-xs text-gray-500 mr-0.5">{$i18n.t('Time')}</span>
						<input
							type="time"
							value={`${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`}
							on:input={(e) => {
								const [h, m] = e.currentTarget.value.split(':').map(Number);
								hour = h;
								minute = m;
								onChange();
							}}
							class="bg-transparent text-center outline-hidden text-xs dark:color-scheme-dark"
							on:click={(e) => e.stopPropagation()}
						/>
					</div>
				{/if}

				{#if frequency === 'MONTHLY'}
					<div class="flex items-center gap-1.5">
						<span class="text-xs text-gray-500">{$i18n.t('Day')}</span>
						<input
							type="number"
							bind:value={monthDay}
							min={1}
							max={31}
							class="w-8 bg-transparent text-center outline-hidden text-xs"
							on:click={(e) => e.stopPropagation()}
							on:input={onChange}
						/>
					</div>
				{/if}
			</div>

			{#if frequency === 'WEEKLY'}
				<div class="flex gap-1 px-2 pb-2">
					{#each DAYS as d}
						<button
							type="button"
							class="flex-1 py-1 text-xs rounded-xl transition {selectedDays.includes(d.key)
								? 'bg-gray-50 dark:bg-gray-800 text-black dark:text-gray-100'
								: 'text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200'}"
							on:click={() => {
								if (selectedDays.includes(d.key)) {
									selectedDays = selectedDays.filter((x) => x !== d.key);
								} else {
									selectedDays = [...selectedDays, d.key];
								}
								onChange();
							}}
						>
							{d.label}
						</button>
					{/each}
				</div>
			{/if}
		{/if}
	</div>
</Dropdown>
