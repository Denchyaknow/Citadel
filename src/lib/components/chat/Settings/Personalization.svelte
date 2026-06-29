<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import { settings } from '$lib/stores';
	import { createEventDispatcher, onMount, getContext } from 'svelte';
	import ManageModal from './Personalization/ManageModal.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	const dispatch = createEventDispatcher();

	const i18n = getContext('i18n');

	export let saveSettings: Function;

	let showManageModal = false;
	let loginBackgroundImageUrl = null;
	let loginBackgroundFiles = null;
	let loginBackgroundInputElement;
	const LOGIN_BACKGROUND_STORAGE_KEY = 'citadelLoginBackgroundImageUrl';

	const saveLoginBackgroundImageUrl = (value: string | null) => {
		loginBackgroundImageUrl = value;
		if (value) {
			localStorage.setItem(LOGIN_BACKGROUND_STORAGE_KEY, value);
		} else {
			localStorage.removeItem(LOGIN_BACKGROUND_STORAGE_KEY);
		}
		saveSettings({ loginBackgroundImageUrl });
	};

	// Addons
	let enableMemory = false;

	onMount(async () => {
		enableMemory = $settings?.memory ?? false;
		loginBackgroundImageUrl =
			$settings?.loginBackgroundImageUrl ??
			localStorage.getItem(LOGIN_BACKGROUND_STORAGE_KEY) ??
			null;
	});
</script>

<ManageModal bind:show={showManageModal} />

<form
	id="tab-personalization"
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={() => {
		dispatch('save');
	}}
>
	<input
		bind:this={loginBackgroundInputElement}
		bind:files={loginBackgroundFiles}
		type="file"
		hidden
		accept="image/*"
		on:change={() => {
			let reader = new FileReader();
			reader.onload = (event) => {
				let originalImageUrl = `${event.target.result}`;
				saveLoginBackgroundImageUrl(originalImageUrl);
			};

			if (
				loginBackgroundFiles &&
				loginBackgroundFiles.length > 0 &&
				['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(
					loginBackgroundFiles[0]['type']
				)
			) {
				reader.readAsDataURL(loginBackgroundFiles[0]);
			} else {
				console.log(`Unsupported File Type '${loginBackgroundFiles[0]['type']}'.`);
				loginBackgroundFiles = null;
			}
		}}
	/>

	<div class="py-1 overflow-y-scroll max-h-[28rem] md:max-h-full">
		<div>
			<div class="flex items-center justify-between mb-1">
				<Tooltip
					content={$i18n.t(
						'This is an experimental feature, it may not function as expected and is subject to change at any time.'
					)}
				>
					<div class="flex items-center gap-2 text-sm font-medium">
						{$i18n.t('Memory')}
						<span
							class="text-[0.65rem] font-medium uppercase px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
							>{$i18n.t('Experimental')}</span
						>
					</div>
				</Tooltip>

				<div class="">
					<Switch
						bind:state={enableMemory}
						on:change={async () => {
							saveSettings({ memory: enableMemory });
						}}
					/>
				</div>
			</div>
		</div>

		<div class="text-xs text-gray-600 dark:text-gray-400">
			<div>
				{$i18n.t(
					"You can personalize your interactions with LLMs by adding memories through the 'Manage' button below, making them more helpful and tailored to you."
				)}
			</div>

			<!-- <div class="mt-3">
				To understand what LLM remembers or teach it something new, just chat with it:

				<div>- “Remember that I like concise responses.”</div>
				<div>- “I just got a puppy!”</div>
				<div>- “What do you remember about me?”</div>
				<div>- “Where did we leave off on my last project?”</div>
			</div> -->
		</div>

		<div class="mt-3 mb-1 ml-1">
			<button
				type="button"
				class=" px-3.5 py-1.5 font-medium hover:bg-black/5 dark:hover:bg-white/5 outline outline-1 outline-gray-300 dark:outline-gray-800 rounded-3xl"
				on:click={() => {
					showManageModal = true;
				}}
			>
				{$i18n.t('Manage')}
			</button>
		</div>

		<div class="mt-5 pt-4 border-t border-gray-100 dark:border-gray-850">
			<div class="mb-2 text-sm font-medium">
				{$i18n.t('Login Screen')}
			</div>

			<div class="py-0.5 flex w-full justify-between">
				<div id="login-background-label" class="self-center text-xs">
					{$i18n.t('Login Background Image')}
				</div>

				<button
					aria-labelledby="login-background-label login-background-image-url-state"
					class="p-1 px-3 text-xs flex rounded-sm transition"
					on:click={() => {
						if (loginBackgroundImageUrl !== null) {
							saveLoginBackgroundImageUrl(null);
						} else {
							loginBackgroundInputElement.click();
						}
					}}
					type="button"
				>
					<span class="ml-2 self-center" id="login-background-image-url-state"
						>{loginBackgroundImageUrl !== null ? $i18n.t('Reset') : $i18n.t('Upload')}</span
					>
				</button>
			</div>
		</div>
	</div>

	<div class="flex justify-end text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
