import { Assets } from 'pixi.js';

import type { AgentTownManifest, LoadedTownAssets } from './CitadelTownTypes';

const MANIFEST_URL = '/citadel-town/manifest.json';

const assetUrl = (manifest: AgentTownManifest, path: string) =>
	`${manifest.basePath.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;

const loadTextureMap = async (manifest: AgentTownManifest, entries: Record<string, string>) => {
	const pairs = await Promise.all(
		Object.entries(entries).map(async ([key, path]) => [
			key,
			await Assets.load(assetUrl(manifest, path))
		])
	);

	return Object.fromEntries(pairs);
};

export const loadTownAssets = async (): Promise<LoadedTownAssets> => {
	const response = await fetch(MANIFEST_URL, { headers: { Accept: 'application/json' } });
	if (!response.ok) {
		throw new Error(`Town asset manifest failed to load: HTTP ${response.status}`);
	}

	const manifest = (await response.json()) as AgentTownManifest;

	return {
		manifest,
		tiles: await loadTextureMap(manifest, manifest.tiles),
		buildings: await loadTextureMap(manifest, manifest.buildings),
		avatars: await loadTextureMap(manifest, manifest.avatars)
	};
};
