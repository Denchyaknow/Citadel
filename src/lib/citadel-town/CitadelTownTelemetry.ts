import type { StatusSummary } from '$lib/apis/status';

import { deterministicIndex, formatCompactNumber } from './CitadelTownMath';
import type {
	AgentTownAgent,
	AgentTownBuilding,
	AgentTownBuildingId,
	AgentTownEvent,
	AgentTownSnapshot,
	AgentTownStatus
} from './CitadelTownTypes';

const buildingLots: Record<
	AgentTownBuildingId,
	{ position: { x: number; y: number }; roadAnchor: { x: number; y: number } }
> = {
	memory: { position: { x: 224, y: 184 }, roadAnchor: { x: 224, y: 272 } },
	skills: { position: { x: 480, y: 144 }, roadAnchor: { x: 480, y: 232 } },
	automations: { position: { x: 736, y: 184 }, roadAnchor: { x: 736, y: 272 } },
	chat: { position: { x: 224, y: 536 }, roadAnchor: { x: 224, y: 448 } },
	models: { position: { x: 480, y: 576 }, roadAnchor: { x: 480, y: 488 } },
	system: { position: { x: 736, y: 536 }, roadAnchor: { x: 736, y: 448 } }
};

const agentAnchors = [
	{ x: 355, y: 332 },
	{ x: 510, y: 308 },
	{ x: 610, y: 398 },
	{ x: 420, y: 430 },
	{ x: 286, y: 390 },
	{ x: 682, y: 296 },
	{ x: 268, y: 274 },
	{ x: 565, y: 486 }
];

const avatarKeys = ['agentBlue', 'agentGreen', 'agentAmber', 'agentRose'];

const statusFromLoad = (percent: number | undefined): AgentTownStatus => {
	const value = Number(percent || 0);
	if (value >= 92) return 'error';
	if (value >= 80) return 'blocked';
	if (value >= 55) return 'tooling';
	return 'active';
};

const skillStatus = (useCount: number): AgentTownStatus => {
	if (useCount >= 10) return 'tooling';
	if (useCount > 0) return 'thinking';
	return 'idle';
};

const makeBuildings = (summary: StatusSummary): AgentTownBuilding[] => [
	{
		id: 'memory',
		label: 'Memory',
		status: summary.total_messages > 0 ? 'active' : 'idle',
		value: `${formatCompactNumber(summary.total_messages)} msgs`,
		position: buildingLots.memory.position,
		roadAnchor: buildingLots.memory.roadAnchor,
		assetKey: 'memory'
	},
	{
		id: 'skills',
		label: 'Skills',
		status: summary.skill_usage.total_invocations > 0 ? 'tooling' : 'idle',
		value: `${formatCompactNumber(summary.skill_usage.total_invocations)} runs`,
		position: buildingLots.skills.position,
		roadAnchor: buildingLots.skills.roadAnchor,
		assetKey: 'skills'
	},
	{
		id: 'automations',
		label: 'Automations',
		status: summary.activity_by_hour.some((row) => Number(row.sessions || 0) > 0)
			? 'thinking'
			: 'idle',
		value: `${formatCompactNumber(summary.total_sessions)} sessions`,
		position: buildingLots.automations.position,
		roadAnchor: buildingLots.automations.roadAnchor,
		assetKey: 'automations'
	},
	{
		id: 'chat',
		label: 'Chat',
		status: summary.total_sessions > 0 ? 'active' : 'idle',
		value: `${formatCompactNumber(summary.total_sessions)} chats`,
		position: buildingLots.chat.position,
		roadAnchor: buildingLots.chat.roadAnchor,
		assetKey: 'chat'
	},
	{
		id: 'models',
		label: 'Models',
		status: summary.models.length ? 'thinking' : 'idle',
		value: `${formatCompactNumber(summary.models.length)} models`,
		position: buildingLots.models.position,
		roadAnchor: buildingLots.models.roadAnchor,
		assetKey: 'models'
	},
	{
		id: 'system',
		label: 'System',
		status: statusFromLoad(
			Math.max(
				Number(summary.system_health.cpu?.percent || 0),
				Number(summary.system_health.memory?.percent || 0),
				Number(summary.system_health.disk?.percent || 0)
			)
		),
		value: summary.system_health.status || 'checked',
		position: buildingLots.system.position,
		roadAnchor: buildingLots.system.roadAnchor,
		assetKey: 'system'
	}
];

const makeAgent = (
	id: string,
	name: string,
	role: string,
	status: AgentTownStatus,
	detail: string,
	index: number
): AgentTownAgent => {
	const anchor = agentAnchors[index % agentAnchors.length];
	const offset = deterministicIndex(id, 42) - 21;

	return {
		id,
		name,
		role,
		status,
		detail,
		avatarKey: avatarKeys[index % avatarKeys.length],
		position: { x: anchor.x + offset, y: anchor.y - offset / 2 },
		target: {
			x: agentAnchors[(index + 2) % agentAnchors.length].x - offset / 2,
			y: agentAnchors[(index + 2) % agentAnchors.length].y + offset
		}
	};
};

const makeAgents = (summary: StatusSummary): AgentTownAgent[] => {
	const modelAgents = summary.models
		.slice(0, 5)
		.map((model, index) =>
			makeAgent(
				`model-${model.model}`,
				model.model || `Model ${index + 1}`,
				'Model',
				model.messages > 0 ? 'thinking' : 'idle',
				`${formatCompactNumber(model.total_tokens)} tokens`,
				index
			)
		);

	const skillAgents = Object.entries(summary.skill_usage.usage ?? {})
		.sort(([, a], [, b]) => Number(b.use_count || 0) - Number(a.use_count || 0))
		.slice(0, Math.max(0, 6 - modelAgents.length))
		.map(([name, meta], index) =>
			makeAgent(
				`skill-${name}`,
				name,
				'Skill',
				skillStatus(Number(meta.use_count || 0)),
				`${formatCompactNumber(Number(meta.use_count || 0))} uses`,
				modelAgents.length + index
			)
		);

	const agents = [...modelAgents, ...skillAgents].slice(0, 8);
	if (agents.length) return agents;

	return [
		makeAgent(
			'mock-session',
			'Session Watch',
			'Telemetry',
			summary.total_sessions ? 'active' : 'idle',
			`${formatCompactNumber(summary.total_sessions)} sessions`,
			0
		),
		makeAgent(
			'mock-models',
			'Model Scout',
			'Telemetry',
			summary.models.length ? 'thinking' : 'idle',
			`${formatCompactNumber(summary.models.length)} models`,
			1
		),
		makeAgent(
			'mock-system',
			'System Hand',
			'Telemetry',
			statusFromLoad(summary.system_health.cpu?.percent),
			summary.system_health.cpu?.label ?? 'CPU',
			2
		)
	];
};

const makeEvents = (summary: StatusSummary): AgentTownEvent[] => {
	const skillEvents = Object.entries(summary.skill_usage.usage ?? {})
		.sort(([, a], [, b]) => Number(b.use_count || 0) - Number(a.use_count || 0))
		.slice(0, 3)
		.map(([name, meta], index) => ({
			id: `skill-event-${name}`,
			label: `${name}: ${formatCompactNumber(Number(meta.use_count || 0))} uses`,
			status: skillStatus(Number(meta.use_count || 0)),
			timestamp: String(index + 1)
		}));

	if (skillEvents.length) return skillEvents;

	return summary.daily_tokens
		.slice(-3)
		.reverse()
		.map((row) => ({
			id: `daily-${row.date}`,
			label: `${row.date}: ${formatCompactNumber(
				Number(row.input_tokens || 0) + Number(row.output_tokens || 0)
			)} tokens`,
			status: Number(row.sessions || 0) > 0 ? 'active' : 'idle',
			timestamp: row.date
		}));
};

export const createStatusTownSnapshot = (summary: StatusSummary): AgentTownSnapshot => ({
	generatedAt: Date.now(),
	scope: summary.scope,
	summaryLabel: summary.scope === 'global' ? 'Global Citadel telemetry' : 'Your Citadel telemetry',
	buildings: makeBuildings(summary),
	agents: makeAgents(summary),
	events: makeEvents(summary),
	stats: {
		sessions: Number(summary.total_sessions || 0),
		messages: Number(summary.total_messages || 0),
		tokens: Number(summary.total_tokens || 0),
		skills: Number(summary.skill_usage.unique_skills_used || 0)
	}
});

export const getTownSnapshotSignature = (snapshot: AgentTownSnapshot) =>
	JSON.stringify({
		scope: snapshot.scope,
		buildings: snapshot.buildings.map(({ id, status, value }) => ({ id, status, value })),
		agents: snapshot.agents.map(({ id, status, detail }) => ({ id, status, detail })),
		events: snapshot.events.map(({ id, label, status }) => ({ id, label, status })),
		stats: snapshot.stats
	});
