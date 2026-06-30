<script lang="ts">
	import { getContext } from 'svelte';

	import { models } from '$lib/stores';
	import {
		getHermesProfileFromModelId,
		isHermesModelId,
		toPascalCaseProfileName
	} from '$lib/apis/hermes';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Search from '$lib/components/icons/Search.svelte';

	const i18n = getContext('i18n');

	export let profile = '';
	export let side: 'top' | 'bottom' = 'top';
	export let align: 'start' | 'end' = 'start';
	export let onChange: () => void = () => {};

	let showDropdown = false;
	let profileSearch = '';

	$: hermesProfiles = ($models as any[])
		.filter((model) => model?.owned_by === 'hermes' || isHermesModelId(model?.id))
		.map((model) => ({
			id: model.id,
			profile: model?.hermes?.profile ?? getHermesProfileFromModelId(model.id) ?? model.name,
			label: toPascalCaseProfileName(
				model?.hermes?.profile ?? getHermesProfileFromModelId(model.id) ?? model.name
			),
			active: model?.hermes?.active ?? false
		}));

	$: if (!profile && hermesProfiles.length > 0) {
		const active = hermesProfiles.find((item) => item.active);
		profile = active?.profile ?? hermesProfiles[0].profile;
	}

	$: profileLabel = profile ? toPascalCaseProfileName(profile) : $i18n.t('Select profile');

	$: filteredProfiles = profileSearch
		? hermesProfiles.filter(
				(item) =>
					item.profile.toLowerCase().includes(profileSearch.toLowerCase()) ||
					item.label.toLowerCase().includes(profileSearch.toLowerCase())
			)
		: hermesProfiles;
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
			class="size-3.5 shrink-0"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
			/>
		</svg>
		<span class="whitespace-nowrap max-w-32 truncate">{profileLabel}</span>
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
		class="rounded-2xl shadow-lg border border-gray-200 dark:border-gray-800 flex flex-col bg-white dark:bg-gray-850 w-72 p-1"
	>
		<div class="flex items-center gap-2 px-2.5 py-1.5">
			<Search className="size-3.5" strokeWidth="2.5" />
			<input
				bind:value={profileSearch}
				class="w-full text-sm bg-transparent outline-hidden"
				placeholder={$i18n.t('Search profiles')}
				autocomplete="off"
				on:click={(e) => e.stopPropagation()}
			/>
		</div>

		<div class="overflow-y-auto scrollbar-thin max-h-60">
			<div class="px-2 text-xs text-gray-500 py-1">
				{$i18n.t('Hermes Profiles')}
			</div>

			{#each filteredProfiles as item (item.profile)}
				<button
					class="px-2.5 py-1.5 rounded-xl w-full text-left text-sm {profile === item.profile
						? 'bg-gray-50 dark:bg-gray-800'
						: ''}"
					type="button"
					on:click={() => {
						profile = item.profile;
						showDropdown = false;
						profileSearch = '';
						onChange();
					}}
				>
					<div class="flex items-center gap-2 text-black dark:text-gray-100 line-clamp-1">
						<div
							class="size-5 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-[10px] font-medium"
						>
							{item.label.slice(0, 1)}
						</div>
						<div class="truncate">{item.label}</div>
					</div>
				</button>
			{:else}
				<div class="block px-3 py-2 text-sm text-gray-700 dark:text-gray-100">
					{$i18n.t('No Hermes profiles found')}
				</div>
			{/each}
		</div>
	</div>
</Dropdown>
