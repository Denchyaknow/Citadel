<script lang="ts">
	import { models, showSettings, settings, user, mobile, config, type Model } from '$lib/stores';
	import { onMount, tick, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Selector from './ModelSelector/Selector.svelte';
	import Tooltip from '../common/Tooltip.svelte';

	import { updateUserSettings } from '$lib/apis/users';
	import { getModelDisplayName } from '$lib/utils/modelImages';
	import {
		buildHermesModelId,
		getHermesFallbackFromModelId,
		getHermesProfileFromModelId,
		isHermesModelId,
		toPascalCaseProfileName
	} from '$lib/apis/hermes';
	import equal from 'fast-deep-equal';
	const i18n = getContext('i18n');

	export let selectedModels = [''];
	export let disabled = false;

	export let showSetDefault = true;

	type HermesFallback = {
		id: string;
		name?: string;
		label?: string;
		provider?: string | null;
	};

	type HermesModel = Omit<Model, 'owned_by'> & {
		owned_by?: string;
		hermes?: {
			profile?: string;
			active?: boolean;
			fallbacks?: HermesFallback[];
		};
	};

	$: hermesProfileModels = ($models as unknown as HermesModel[]).filter(
		(model) => model?.owned_by === 'hermes'
	);
	$: localBrainOnly =
		$models.length === 1 &&
		$models[0]?.id === 'localbrain-router:latest' &&
		$models[0]?.owned_by === 'localbrain';
	$: if (localBrainOnly && !equal(selectedModels, ['localbrain-router:latest'])) {
		selectedModels = ['localbrain-router:latest'];
	}
	$: hermesMode = hermesProfileModels.length > 0;
	$: selectedHermesProfile = getHermesProfileFromModelId(selectedModels?.[0]);
	$: selectedHermesProfileModel = hermesProfileModels.find(
		(model) => model?.hermes?.profile === selectedHermesProfile
	);
	$: selectedHermesFallback = getHermesFallbackFromModelId(selectedModels?.[0]);
	$: selectedHermesFallbacks = selectedHermesProfileModel?.hermes?.fallbacks ?? [];
	$: if (hermesMode && !isHermesModelId(selectedModels?.[0])) {
		const activeProfileModel = hermesProfileModels.find((model) => model?.hermes?.active);
		const nextModel = activeProfileModel ?? hermesProfileModels[0];
		if (nextModel) {
			queueMicrotask(() => {
				selectedModels = [nextModel.id];
			});
		}
	}

	const setHermesProfile = (modelId: string) => {
		const profile = getHermesProfileFromModelId(modelId);
		const profileModel = hermesProfileModels.find((model) => model?.hermes?.profile === profile);
		const fallbacks = profileModel?.hermes?.fallbacks ?? [];
		const currentFallback = getHermesFallbackFromModelId(selectedModels?.[0]);
		const nextFallback = fallbacks.some((fallback: HermesFallback) => fallback.id === currentFallback)
			? currentFallback
			: '';
		selectedModels = [buildHermesModelId(profile, nextFallback)];
	};

	const setHermesFallback = (fallbackModelId: string) => {
		selectedModels = [buildHermesModelId(selectedHermesProfile, fallbackModelId)];
	};

	const saveDefaultModel = async () => {
		const hasEmptyModel = selectedModels.filter((it) => it === '');
		if (hasEmptyModel.length) {
			toast.error($i18n.t('Choose a model before saving...'));
			return;
		}
		settings.set({ ...$settings, models: selectedModels });
		await updateUserSettings(localStorage.token, { ui: $settings });

		toast.success($i18n.t('Default model updated'));
	};

	const pinModelHandler = async (modelId: string) => {
		let pinnedModels: string[] = [...(($settings?.pinnedModels as string[] | undefined) ?? [])];

		if (pinnedModels.includes(modelId)) {
			pinnedModels = pinnedModels.filter((id) => id !== modelId);
		} else {
			pinnedModels = [...new Set([...pinnedModels, modelId])];
		}

		settings.set({ ...($settings as any), pinnedModels: pinnedModels });
		await updateUserSettings(localStorage.token, { ui: $settings });
	};

	$: if (selectedModels.length > 0 && $models.length > 0) {
		const _selectedModels = selectedModels.map((model) =>
			$models.map((m) => m.id).includes(model) || isHermesModelId(model) ? model : ''
		);

		if (!equal(_selectedModels, selectedModels)) {
			selectedModels = _selectedModels;
		}
	}
</script>

{#if !localBrainOnly}
<div class="flex flex-col w-full items-start">
	{#if hermesMode}
		<div class="flex w-full max-w-fit items-center gap-1">
			<div class="overflow-hidden w-full">
				<div class="max-w-full {($settings?.highContrastMode ?? false) ? 'm-1' : 'mr-1'}">
					<Selector
						id="hermes-profile"
						placeholder="Select a profile"
						items={hermesProfileModels.map((model) => ({
							value: model.id,
							label: toPascalCaseProfileName(model.hermes?.profile ?? model.name),
							model: model
						}))}
						{pinModelHandler}
						value={selectedHermesProfileModel?.id ?? selectedModels?.[0] ?? ''}
						onChange={setHermesProfile}
					/>
				</div>
			</div>

			{#if selectedHermesFallbacks.length > 0}
				<div class="overflow-hidden w-full min-w-[13rem]">
					<div class="max-w-full {($settings?.highContrastMode ?? false) ? 'm-1' : 'mr-1'}">
						<Selector
							id="hermes-fallback"
							placeholder="Default model"
							items={[
								{
									value: '',
									label: 'Default model',
									model: selectedHermesProfileModel
								},
								...selectedHermesFallbacks.map((fallback: HermesFallback) => ({
									value: fallback.id,
									label: fallback.name ?? fallback.id,
									model: {
										...selectedHermesProfileModel,
										id: fallback.id,
										name: fallback.name ?? fallback.id,
										tags: [{ name: fallback.label ?? 'Fallback' }]
									}
								}))
							]}
							value={selectedHermesFallback}
							onChange={setHermesFallback}
							searchEnabled={false}
						/>
					</div>
				</div>
			{/if}
		</div>
	{:else}
	{#each selectedModels as selectedModel, selectedModelIdx}
		<div class="flex w-full max-w-fit">
			<div class="overflow-hidden w-full">
				<div class="max-w-full {($settings?.highContrastMode ?? false) ? 'm-1' : 'mr-1'}">
					<Selector
						id={`${selectedModelIdx}`}
						placeholder={$i18n.t('Select a model')}
						items={$models.map((model) => ({
							value: model.id,
							label: getModelDisplayName(model),
							model: model
						}))}
						{pinModelHandler}
						bind:value={selectedModel}
					/>
				</div>
			</div>

			{#if $user?.role === 'admin' || ($user?.permissions?.chat?.multiple_models ?? true)}
				{#if selectedModelIdx === 0}
					<div
						class="  self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]"
					>
						<Tooltip content={$i18n.t('Add Model')}>
							<button
								class=" "
								{disabled}
								on:click={() => {
									selectedModels = [...selectedModels, ''];
								}}
								aria-label="Add Model"
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="2"
									stroke="currentColor"
									class="size-3.5"
								>
									<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m6-6H6" />
								</svg>
							</button>
						</Tooltip>
					</div>
				{:else}
					<div
						class="  self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]"
					>
						<Tooltip content={$i18n.t('Remove Model')}>
							<button
								{disabled}
								on:click={() => {
									selectedModels.splice(selectedModelIdx, 1);
									selectedModels = selectedModels;
								}}
								aria-label="Remove Model"
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									fill="none"
									viewBox="0 0 24 24"
									stroke-width="2"
									stroke="currentColor"
									class="size-3"
								>
									<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" />
								</svg>
							</button>
						</Tooltip>
					</div>
				{/if}
			{/if}
		</div>
	{/each}
	{/if}
</div>
{/if}

{#if showSetDefault && !localBrainOnly}
	<div
		class="relative text-left mt-[1px] ml-1 text-[0.7rem] text-gray-600 dark:text-gray-400 font-primary"
	>
		<button on:click={saveDefaultModel}> {$i18n.t('Set as default')}</button>
	</div>
{/if}
