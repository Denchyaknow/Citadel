import {
	Application,
	Container,
	Graphics,
	Sprite,
	Text,
	type ApplicationOptions,
	type Texture
} from 'pixi.js';
import { Viewport } from 'pixi-viewport';

import { clamp, lerp, TOWN_WORLD } from './CitadelTownMath';
import { getTownSnapshotSignature } from './CitadelTownTelemetry';
import type {
	AgentTownAgent,
	AgentTownBuilding,
	AgentTownSnapshot,
	AgentTownStatus,
	LoadedTownAssets
} from './CitadelTownTypes';

type AgentVisual = {
	source: AgentTownAgent;
	container: Container;
	sprite: Sprite;
	ring: Graphics;
	label: Text;
	target: { x: number; y: number };
	phase: number;
};

const statusColors: Record<AgentTownStatus, number> = {
	active: 0x34d399,
	thinking: 0x38bdf8,
	tooling: 0xf59e0b,
	idle: 0x94a3b8,
	blocked: 0xf97316,
	error: 0xfb7185,
	offline: 0x64748b
};

const TOWN_MIN_ZOOM = 0.72;
const TOWN_MAX_ZOOM = 2.2;
const TOWN_ZOOM_STEP = 1.22;

const appOptions = (width: number, height: number): Partial<ApplicationOptions> => ({
	width,
	height,
	backgroundAlpha: 0,
	antialias: true,
	autoDensity: true,
	resolution: Math.min(window.devicePixelRatio || 1, 2),
	preference: 'webgl',
	powerPreference: 'low-power'
});

const makeLabel = (text: string, size = 15, color = 0xe5edf6) =>
	new Text({
		text,
		style: {
			fill: color,
			fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
			fontSize: size,
			fontWeight: '600',
			align: 'center',
			dropShadow: {
				color: '#020617',
				alpha: 0.75,
				blur: 3,
				distance: 1
			}
		}
	});

const makePill = (width: number, color: number) =>
	new Graphics()
		.roundRect(-width / 2, -12, width, 24, 12)
		.fill({ color: 0x020617, alpha: 0.72 })
		.stroke({ color, width: 1.5, alpha: 0.8 });

const textureFor = (map: Record<string, Texture>, key: string, fallbackKey: string) =>
	map[key] ?? map[fallbackKey] ?? Object.values(map)[0];

export class CitadelTownRenderer {
	private app: Application | null = null;
	private viewport: Viewport | null = null;
	private roadLayer: Container | null = null;
	private agentLayer: Container | null = null;
	private hudLayer: Container | null = null;
	private agents: AgentVisual[] = [];
	private snapshotSignature = '';
	private active = true;
	private destroyed = false;
	private minZoom = TOWN_MIN_ZOOM;
	private freePan = false;
	private readonly onTick = () => this.tick();

	constructor(
		private readonly container: HTMLElement,
		private readonly assets: LoadedTownAssets,
		private snapshot: AgentTownSnapshot
	) {}

	async init() {
		const { width, height } = this.containerSize();
		this.app = new Application();
		await this.app.init(appOptions(width, height));
		if (this.destroyed) return;

		this.app.canvas.classList.add('citadel-town-canvas');
		this.container.appendChild(this.app.canvas);

		this.viewport = new Viewport({
			screenWidth: width,
			screenHeight: height,
			worldWidth: TOWN_WORLD.width,
			worldHeight: TOWN_WORLD.height,
			events: this.app.renderer.events
		});

		this.configureDrag();
		this.viewport.clamp({ direction: 'all' }).clampZoom({
			minScale: this.minZoom,
			maxScale: TOWN_MAX_ZOOM
		});

		this.app.stage.addChild(this.viewport);
		this.buildScene();
		this.resize();
		this.app.ticker.add(this.onTick);
	}

	updateSnapshot(snapshot: AgentTownSnapshot) {
		const nextSignature = getTownSnapshotSignature(snapshot);
		if (nextSignature === this.snapshotSignature) return;

		this.snapshot = snapshot;
		if (!this.viewport) return;

		this.snapshotSignature = nextSignature;
		this.rebuildTownObjects();
	}

	resize() {
		if (!this.app || !this.viewport) return;

		const { width, height } = this.containerSize();
		this.app.renderer.resize(width, height);
		this.viewport.resize(width, height, TOWN_WORLD.width, TOWN_WORLD.height);
		this.viewport.fitWorld(true);
		this.minZoom = Math.min(this.viewport.scale.x, TOWN_MAX_ZOOM);
		this.viewport.clamp({ direction: 'all' });
		this.viewport.clampZoom({ minScale: this.minZoom, maxScale: TOWN_MAX_ZOOM });
	}

	zoomIn() {
		this.setZoom((this.viewport?.scale.x ?? this.minZoom) * TOWN_ZOOM_STEP);
	}

	zoomOut() {
		this.setZoom((this.viewport?.scale.x ?? this.minZoom) / TOWN_ZOOM_STEP);
	}

	resetZoom() {
		if (!this.viewport) return;

		this.viewport.fitWorld(true);
		this.minZoom = Math.min(this.viewport.scale.x, TOWN_MAX_ZOOM);
		this.viewport.clamp({ direction: 'all' });
		this.viewport.clampZoom({ minScale: this.minZoom, maxScale: TOWN_MAX_ZOOM });
	}

	setFreePan(enabled: boolean) {
		if (this.freePan === enabled) return;

		this.freePan = enabled;
		this.configureDrag();
	}

	setActive(active: boolean) {
		this.active = active;
		if (!this.app || this.destroyed) return;

		if (active) {
			this.app.ticker.start();
		} else {
			this.app.ticker.stop();
		}
	}

	destroy() {
		this.destroyed = true;
		this.agents = [];
		this.viewport?.destroy({ children: true });
		this.app?.ticker.remove(this.onTick);
		this.app?.destroy({ removeView: true }, { children: true });
		this.viewport = null;
		this.app = null;
		this.roadLayer = null;
		this.agentLayer = null;
		this.hudLayer = null;
	}

	private containerSize() {
		const bounds = this.container.getBoundingClientRect();
		return {
			width: Math.max(320, Math.round(bounds.width || 320)),
			height: Math.max(300, Math.round(bounds.height || 300))
		};
	}

	private setZoom(scale: number) {
		if (!this.viewport) return;

		this.viewport.setZoom(clamp(scale, this.minZoom, TOWN_MAX_ZOOM), true);
		this.viewport.clamp({ direction: 'all' });
	}

	private configureDrag() {
		if (!this.viewport) return;

		this.viewport.plugins.remove('drag');
		this.viewport.drag({
			...(this.freePan ? {} : { direction: 'x' }),
			mouseButtons: 'left',
			wheel: false
		});
	}

	private makeRoadNetwork() {
		const group = new Container();
		const plaza = { x: TOWN_WORLD.width / 2, y: TOWN_WORLD.height / 2 };
		const sortedBuildings = [...this.snapshot.buildings].sort((a, b) => a.id.localeCompare(b.id));

		const drawRoads = (width: number, color: number, alpha: number) => {
			const roads = new Graphics();
			for (const building of sortedBuildings) {
				const midpoint = { x: building.roadAnchor.x, y: plaza.y };
				roads
					.moveTo(plaza.x, plaza.y)
					.lineTo(midpoint.x, midpoint.y)
					.lineTo(building.roadAnchor.x, building.roadAnchor.y);
			}
			roads.stroke({ color, width, alpha, cap: 'round', join: 'round' });
			return roads;
		};

		group.addChild(drawRoads(44, 0x111827, 0.86));
		group.addChild(drawRoads(34, 0x253244, 0.94));
		group.addChild(drawRoads(2, 0x94a3b8, 0.42));

		const plazaBase = new Graphics()
			.circle(plaza.x, plaza.y, 76)
			.fill({ color: 0x0f172a, alpha: 0.92 })
			.stroke({ color: 0x334155, width: 4, alpha: 0.92 });
		const plazaGlow = new Graphics()
			.circle(plaza.x, plaza.y, 44)
			.fill({ color: 0x111c29, alpha: 0.86 })
			.stroke({ color: 0x38bdf8, width: 2, alpha: 0.5 });
		group.addChild(plazaBase, plazaGlow);

		for (const building of sortedBuildings) {
			const node = new Graphics()
				.circle(building.roadAnchor.x, building.roadAnchor.y, 13)
				.fill({ color: 0x0b1220, alpha: 0.96 })
				.stroke({ color: statusColors[building.status], width: 2, alpha: 0.72 });
			group.addChild(node);
		}

		return group;
	}

	private buildScene() {
		if (!this.viewport) return;

		const backgroundTexture = textureFor(
			this.assets.tiles as Record<string, Texture>,
			'ground',
			'ground'
		);
		const background = new Sprite({ texture: backgroundTexture });
		background.width = TOWN_WORLD.width;
		background.height = TOWN_WORLD.height;
		this.viewport.addChild(background);

		const glow = new Graphics()
			.circle(TOWN_WORLD.width / 2, TOWN_WORLD.height / 2, 156)
			.fill({ color: 0x38bdf8, alpha: 0.045 });
		this.viewport.addChild(glow);

		this.roadLayer = new Container();
		this.agentLayer = new Container();
		this.hudLayer = new Container();
		this.viewport.addChild(this.roadLayer, this.agentLayer, this.hudLayer);

		this.snapshotSignature = getTownSnapshotSignature(this.snapshot);
		this.rebuildTownObjects();
	}

	private rebuildTownObjects() {
		if (!this.viewport || !this.roadLayer || !this.agentLayer || !this.hudLayer) return;

		for (const child of this.roadLayer.removeChildren()) child.destroy({ children: true });
		for (const child of this.agentLayer.removeChildren()) child.destroy({ children: true });
		for (const child of this.hudLayer.removeChildren()) child.destroy({ children: true });
		this.agents = [];

		this.roadLayer.addChild(this.makeRoadNetwork());

		for (const building of this.snapshot.buildings) {
			this.hudLayer.addChild(this.makeBuilding(building));
		}

		for (const [index, agent] of this.snapshot.agents.entries()) {
			const visual = this.makeAgent(agent, index);
			this.agents.push(visual);
			this.agentLayer.addChild(visual.container);
		}

		this.hudLayer.addChild(this.makeEventBoard());
	}

	private makeBuilding(building: AgentTownBuilding) {
		const group = new Container();
		group.position.set(building.position.x, building.position.y);

		const color = statusColors[building.status];
		const anchorOffset = {
			x: building.roadAnchor.x - building.position.x,
			y: building.roadAnchor.y - building.position.y
		};
		const entranceEdgeY = anchorOffset.y > 0 ? 70 : -58;

		const lotPad = new Graphics()
			.roundRect(-76, -58, 152, 128, 18)
			.fill({ color: 0x07111f, alpha: 0.78 })
			.stroke({ color: 0x334155, width: 1.5, alpha: 0.72 });
		group.addChild(lotPad);

		const entryPath = new Graphics()
			.moveTo(anchorOffset.x, anchorOffset.y)
			.lineTo(0, entranceEdgeY)
			.stroke({ color: 0x253244, width: 12, alpha: 0.96, cap: 'round', join: 'round' })
			.moveTo(anchorOffset.x, anchorOffset.y)
			.lineTo(0, entranceEdgeY)
			.stroke({ color: 0x94a3b8, width: 1.5, alpha: 0.38, cap: 'round', join: 'round' });
		group.addChild(entryPath);

		const texture = textureFor(
			this.assets.buildings as Record<string, Texture>,
			building.assetKey,
			'system'
		);
		const sprite = new Sprite({ texture, anchor: 0.5 });
		sprite.width = 118;
		sprite.height = 100;
		group.addChild(sprite);

		const statusRing = new Graphics()
			.circle(44, -34, 11)
			.fill({ color: 0x020617, alpha: 0.82 })
			.stroke({ color, width: 3, alpha: 0.95 });
		group.addChild(statusRing);

		const label = makeLabel(building.label, 14);
		label.anchor.set(0.5, 0);
		label.position.set(0, 58);
		group.addChild(label);

		const value = makeLabel(building.value, 11, 0xa8b3c3);
		value.anchor.set(0.5, 0);
		value.position.set(0, 78);
		group.addChild(value);

		return group;
	}

	private makeAgent(agent: AgentTownAgent, index: number): AgentVisual {
		const group = new Container();
		group.position.set(agent.position.x, agent.position.y);

		const ring = new Graphics()
			.circle(0, 0, 28)
			.stroke({ color: statusColors[agent.status], width: 4, alpha: 0.92 });
		group.addChild(ring);

		const texture = textureFor(
			this.assets.avatars as Record<string, Texture>,
			agent.avatarKey,
			'agentBlue'
		);
		const sprite = new Sprite({ texture, anchor: 0.5 });
		sprite.width = 52;
		sprite.height = 52;
		group.addChild(sprite);

		const pill = makePill(116, statusColors[agent.status]);
		pill.position.set(0, 39);
		group.addChild(pill);

		const label = makeLabel(
			agent.name.length > 14 ? `${agent.name.slice(0, 13)}...` : agent.name,
			11
		);
		label.anchor.set(0.5, 0.5);
		label.position.set(0, 39);
		group.addChild(label);

		return {
			source: agent,
			container: group,
			sprite,
			ring,
			label,
			target: { ...agent.target },
			phase: index * 0.7
		};
	}

	private makeEventBoard() {
		const group = new Container();
		group.position.set(28, 28);

		const board = new Graphics()
			.roundRect(0, 0, 232, 114, 14)
			.fill({ color: 0x020617, alpha: 0.68 })
			.stroke({ color: 0x334155, width: 1, alpha: 0.9 });
		group.addChild(board);

		const title = makeLabel(this.snapshot.summaryLabel, 12, 0xcbd5e1);
		title.anchor.set(0, 0);
		title.position.set(14, 12);
		group.addChild(title);

		this.snapshot.events.slice(0, 3).forEach((event, index) => {
			const y = 40 + index * 22;
			const dot = new Graphics()
				.circle(18, y + 5, 4)
				.fill({ color: statusColors[event.status], alpha: 0.95 });
			group.addChild(dot);

			const label = makeLabel(
				event.label.length > 25 ? `${event.label.slice(0, 24)}...` : event.label,
				10,
				0x94a3b8
			);
			label.anchor.set(0, 0);
			label.position.set(30, y);
			group.addChild(label);
		});

		return group;
	}

	private tick() {
		if (!this.active || !this.viewport) return;

		const now = performance.now() / 1000;
		for (const agent of this.agents) {
			const dist = Math.hypot(
				agent.container.x - agent.target.x,
				agent.container.y - agent.target.y
			);
			if (dist < 8) {
				agent.target = { ...agent.source.position };
				agent.source.position = { x: agent.container.x, y: agent.container.y };
			}

			agent.container.x = lerp(agent.container.x, agent.target.x, 0.008);
			agent.container.y = lerp(agent.container.y, agent.target.y, 0.008);
			agent.sprite.y = Math.sin(now * 2 + agent.phase) * 3;
			agent.ring.alpha = 0.68 + Math.sin(now * 3 + agent.phase) * 0.18;
			agent.label.alpha = 0.86 + Math.sin(now * 2 + agent.phase) * 0.08;
		}
	}
}
