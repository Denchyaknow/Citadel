<script lang="ts">
	import { onMount } from 'svelte';

	import { getStatusSummary, type StatusSummary } from '$lib/apis/status';
	import { createStatusTownSnapshot } from '$lib/citadel-town/CitadelTownTelemetry';
	import type { AgentTownSnapshot } from '$lib/citadel-town/CitadelTownTypes';
	import ArrowsPointingOut from '$lib/components/icons/ArrowsPointingOut.svelte';
	import Minus from '$lib/components/icons/Minus.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';

	import AgentTownFallback from './AgentTownFallback.svelte';

	export let summary: StatusSummary;
	export let days = 30;

	let frameElement: HTMLDivElement;
	let canvasHost: HTMLDivElement;
	let renderer: import('$lib/citadel-town/CitadelTownRenderer').CitadelTownRenderer | null = null;
	let snapshot: AgentTownSnapshot = createStatusTownSnapshot(summary);
	let rendererReady = false;
	let pixiError = '';
	let visible = false;
	let disposed = false;
	let freePan = false;
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	$: if (summary) {
		snapshot = createStatusTownSnapshot(summary);
		renderer?.updateSnapshot(snapshot);
	}

	const clearPollTimer = () => {
		if (!pollTimer) return;
		clearInterval(pollTimer);
		pollTimer = null;
	};

	const syncActivity = () => {
		const active = visible && !document.hidden;
		renderer?.setActive(active);

		clearPollTimer();
		if (!active) return;

		pollTimer = setInterval(() => {
			void pollStatus();
		}, 5000);
	};

	const pollStatus = async () => {
		if (!visible || document.hidden) return;

		try {
			const nextSummary = await getStatusSummary(localStorage.token, days);
			snapshot = createStatusTownSnapshot(nextSummary);
			renderer?.updateSnapshot(snapshot);
		} catch {
			// The dashboard already owns user-facing status API errors.
		}
	};

	const zoomIn = () => renderer?.zoomIn();
	const zoomOut = () => renderer?.zoomOut();
	const resetZoom = () => renderer?.resetZoom();
	const toggleFreePan = () => {
		freePan = !freePan;
		renderer?.setFreePan(freePan);
	};
	const scrollToStatusModules = () => {
		frameElement
			?.closest('.status-content')
			?.querySelector('.status-columns')
			?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	};

	onMount(() => {
		let resizeObserver: ResizeObserver | null = null;
		let intersectionObserver: IntersectionObserver | null = null;

		const onVisibilityChange = () => syncActivity();

		const start = async () => {
			try {
				const [{ loadTownAssets }, { CitadelTownRenderer }] = await Promise.all([
					import('$lib/citadel-town/CitadelTownAssets'),
					import('$lib/citadel-town/CitadelTownRenderer')
				]);

				const assets = await loadTownAssets();
				if (disposed) return;

				renderer = new CitadelTownRenderer(canvasHost, assets, snapshot);
				await renderer.init();
				if (disposed) return;

				renderer.setFreePan(freePan);
				rendererReady = true;
				syncActivity();
			} catch (error) {
				renderer?.destroy();
				renderer = null;
				rendererReady = false;
				pixiError = error instanceof Error ? error.message : String(error);
			}
		};

		resizeObserver = new ResizeObserver(() => renderer?.resize());
		resizeObserver.observe(canvasHost);

		intersectionObserver = new IntersectionObserver(
			(entries) => {
				visible = entries.some((entry) => entry.isIntersecting);
				syncActivity();
			},
			{ threshold: 0.12 }
		);
		intersectionObserver.observe(frameElement);

		document.addEventListener('visibilitychange', onVisibilityChange);
		void start();

		return () => {
			disposed = true;
			clearPollTimer();
			document.removeEventListener('visibilitychange', onVisibilityChange);
			resizeObserver?.disconnect();
			intersectionObserver?.disconnect();
			renderer?.destroy();
			renderer = null;
		};
	});
</script>

<section class="town-hero" aria-label="AI Town agent status">
	<div class="town-hero__frame" bind:this={frameElement}>
		<div class:town-hero__surface--free-pan={freePan} class="town-hero__surface" bind:this={canvasHost}>
			{#if !rendererReady || pixiError}
				<AgentTownFallback
					{snapshot}
					reason={pixiError
						? `Interactive renderer unavailable: ${pixiError}`
						: 'Preparing town renderer'}
				/>
			{/if}
		</div>
		<div class="town-hero__controls" aria-label="AI Town zoom controls">
			<button
				type="button"
				class="town-hero__control"
				aria-label="Zoom out"
				title="Zoom out"
				disabled={!rendererReady}
				on:pointerdown|stopPropagation
				on:click={zoomOut}
			>
				<Minus className="h-4 w-4" strokeWidth="2" />
			</button>
			<button
				type="button"
				class:town-hero__control--active={freePan}
				class="town-hero__control"
				aria-label={freePan ? 'Release map pan' : 'Move map'}
				aria-pressed={freePan}
				title={freePan ? 'Release map pan' : 'Move map'}
				disabled={!rendererReady}
				on:pointerdown|stopPropagation
				on:click={toggleFreePan}
			>
				<ArrowsPointingOut className="h-4 w-4" strokeWidth="2" />
			</button>
			<button
				type="button"
				class="town-hero__control town-hero__control--reset"
				aria-label="Reset zoom"
				title="Reset zoom"
				disabled={!rendererReady}
				on:pointerdown|stopPropagation
				on:click={resetZoom}
			>
				1x
			</button>
			<button
				type="button"
				class="town-hero__control"
				aria-label="Zoom in"
				title="Zoom in"
				disabled={!rendererReady}
				on:pointerdown|stopPropagation
				on:click={zoomIn}
			>
				<Plus className="h-4 w-4" strokeWidth="2" />
			</button>
		</div>
	</div>
	<button
		type="button"
		class="town-hero__arrow"
		aria-label="Scroll to status modules"
		title="Scroll to status modules"
		on:click={scrollToStatusModules}
	></button>
</section>

<style>
	.town-hero {
		width: 100%;
		padding: 0.75rem 0.5rem 0;
	}

	.town-hero__frame {
		position: relative;
		aspect-ratio: 1 / 0.95;
		max-height: min(760px, calc(100dvh - 11rem));
		min-height: 19rem;
		width: 100%;
		overflow: hidden;
		border-radius: 0.75rem;
		border: 1px solid rgb(31 41 55);
		background:
			linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(3, 7, 18, 0.96)),
			radial-gradient(circle at 50% 45%, rgba(56, 189, 248, 0.12), transparent 45%);
		box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.12);
	}

	.town-hero__surface {
		position: relative;
		height: 100%;
		width: 100%;
		touch-action: pan-y;
	}

	.town-hero__surface :global(.citadel-town-canvas) {
		display: block;
		height: 100%;
		touch-action: pan-y;
		width: 100%;
	}

	.town-hero__surface--free-pan,
	.town-hero__surface--free-pan :global(.citadel-town-canvas) {
		touch-action: none;
	}

	.town-hero__controls {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		z-index: 2;
		display: flex;
		gap: 0.375rem;
	}

	.town-hero__control {
		display: inline-flex;
		height: 2.125rem;
		width: 2.125rem;
		align-items: center;
		justify-content: center;
		border-radius: 0.5rem;
		border: 1px solid rgb(51 65 85 / 0.92);
		background: rgb(2 6 23 / 0.78);
		color: rgb(226 232 240);
		box-shadow: 0 8px 20px rgb(2 6 23 / 0.28);
		transition:
			background 120ms ease,
			border-color 120ms ease,
			color 120ms ease;
	}

	.town-hero__control:hover:not(:disabled) {
		border-color: rgb(56 189 248 / 0.74);
		background: rgb(15 23 42 / 0.92);
		color: white;
	}

	.town-hero__control--active:not(:disabled) {
		border-color: rgb(56 189 248 / 0.85);
		background: rgb(8 47 73 / 0.9);
		color: white;
	}

	.town-hero__control:disabled {
		cursor: default;
		opacity: 0.45;
	}

	.town-hero__control--reset {
		width: 2.375rem;
		font-size: 0.6875rem;
		font-weight: 700;
		line-height: 1;
	}

	.town-hero__arrow {
		display: block;
		margin: 0.45rem auto 0;
		height: 0.625rem;
		width: 0.625rem;
		border-top: 0;
		border-left: 0;
		border-bottom: 1px solid rgb(100 116 139);
		border-right: 1px solid rgb(100 116 139);
		background: transparent;
		cursor: pointer;
		opacity: 0.7;
		padding: 0;
		transform: rotate(45deg);
	}

	.town-hero__arrow:hover {
		border-color: rgb(203 213 225);
		opacity: 1;
	}

	@media (min-width: 640px) {
		.town-hero {
			padding-inline: 0.75rem;
		}

		.town-hero__frame {
			min-height: 24rem;
		}
	}

	@media (min-width: 1180px) {
		.town-hero {
			padding-top: 0.875rem;
		}
	}
</style>
