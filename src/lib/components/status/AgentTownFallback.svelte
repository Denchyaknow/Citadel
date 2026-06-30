<script lang="ts">
	import type { AgentTownSnapshot } from '$lib/citadel-town/CitadelTownTypes';

	export let snapshot: AgentTownSnapshot;
	export let reason = '';
</script>

<div class="town-fallback" role="status" aria-live="polite">
	<div class="town-fallback__header">
		<div>
			<p class="town-fallback__eyebrow">AI Town</p>
			<h2>Hermes Agent Status</h2>
		</div>
		<span>{snapshot.scope}</span>
	</div>

	<div class="town-fallback__grid">
		{#each snapshot.buildings as building}
			<div class="town-fallback__tile">
				<strong>{building.label}</strong>
				<span>{building.value}</span>
			</div>
		{/each}
	</div>

	{#if snapshot.agents.length}
		<div class="town-fallback__agents">
			{#each snapshot.agents.slice(0, 4) as agent}
				<div>
					<strong>{agent.name}</strong>
					<span>{agent.status}</span>
				</div>
			{/each}
		</div>
	{/if}

	{#if reason}
		<p class="town-fallback__reason">{reason}</p>
	{/if}
</div>

<style>
	.town-fallback {
		display: flex;
		min-height: 100%;
		flex-direction: column;
		gap: 0.875rem;
		border-radius: 0.75rem;
		border: 1px solid rgb(30 41 59);
		background:
			linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(8, 13, 22, 0.94)),
			radial-gradient(circle at 50% 40%, rgba(56, 189, 248, 0.16), transparent 42%);
		padding: 1rem;
		color: rgb(226 232 240);
	}

	.town-fallback__header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
	}

	.town-fallback__eyebrow,
	.town-fallback__header h2,
	.town-fallback__header span,
	.town-fallback__tile strong,
	.town-fallback__tile span,
	.town-fallback__agents strong,
	.town-fallback__agents span,
	.town-fallback__reason {
		margin: 0;
		line-height: 1.3;
	}

	.town-fallback__eyebrow,
	.town-fallback__header span,
	.town-fallback__tile span,
	.town-fallback__agents span,
	.town-fallback__reason {
		color: rgb(148 163 184);
		font-size: 0.75rem;
	}

	.town-fallback__header h2 {
		font-size: 1.1rem;
		font-weight: 700;
	}

	.town-fallback__grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.5rem;
	}

	.town-fallback__tile,
	.town-fallback__agents div {
		min-width: 0;
		border-radius: 0.5rem;
		border: 1px solid rgba(51, 65, 85, 0.8);
		background: rgba(15, 23, 42, 0.7);
		padding: 0.625rem;
	}

	.town-fallback__tile strong,
	.town-fallback__agents strong {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.8125rem;
	}

	.town-fallback__tile span,
	.town-fallback__agents span {
		display: block;
		margin-top: 0.25rem;
		text-transform: capitalize;
	}

	.town-fallback__agents {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.5rem;
	}

	@media (min-width: 640px) {
		.town-fallback {
			padding: 1.125rem;
		}

		.town-fallback__grid,
		.town-fallback__agents {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}
</style>
