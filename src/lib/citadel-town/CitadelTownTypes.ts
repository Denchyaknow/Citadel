import type { StatusSummary } from '$lib/apis/status';
import type { Texture } from 'pixi.js';

export type AgentTownStatus =
	| 'active'
	| 'thinking'
	| 'tooling'
	| 'idle'
	| 'blocked'
	| 'error'
	| 'offline';

export type AgentTownBuildingId =
	| 'memory'
	| 'skills'
	| 'automations'
	| 'chat'
	| 'models'
	| 'system';

export type AgentTownPoint = {
	x: number;
	y: number;
};

export type AgentTownBuilding = {
	id: AgentTownBuildingId;
	label: string;
	status: AgentTownStatus;
	value: string;
	position: AgentTownPoint;
	roadAnchor: AgentTownPoint;
	assetKey: AgentTownBuildingId;
};

export type AgentTownAgent = {
	id: string;
	name: string;
	role: string;
	status: AgentTownStatus;
	detail: string;
	avatarKey: string;
	position: AgentTownPoint;
	target: AgentTownPoint;
};

export type AgentTownEvent = {
	id: string;
	label: string;
	status: AgentTownStatus;
	timestamp?: string;
};

export type AgentTownSnapshot = {
	generatedAt: number;
	scope: StatusSummary['scope'];
	summaryLabel: string;
	buildings: AgentTownBuilding[];
	agents: AgentTownAgent[];
	events: AgentTownEvent[];
	stats: {
		sessions: number;
		messages: number;
		tokens: number;
		skills: number;
	};
};

export type AgentTownManifest = {
	version: number;
	basePath: string;
	tiles: Record<string, string>;
	buildings: Record<string, string>;
	avatars: Record<string, string>;
};

export type LoadedTownAssets = {
	manifest: AgentTownManifest;
	tiles: Record<string, Texture>;
	buildings: Record<string, Texture>;
	avatars: Record<string, Texture>;
};
