import { WEBUI_API_BASE_URL } from '$lib/constants';

export const CITADEL_ICON_URL = '/static/favicon.png';
export const USER_ICON_URL = '/user.png';
const TRANSPARENT_IMAGE =
	'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';

export const toPascalCaseName = (value: string | null | undefined, fallback = 'Default') => {
	const words = String(value || fallback)
		.replace(/([a-z0-9])([A-Z])/g, '$1 $2')
		.split(/[^A-Za-z0-9]+/)
		.filter(Boolean);

	return words.length
		? words
				.map((word) =>
					/^[A-Z0-9]+$/.test(word)
						? word
						: `${word.charAt(0).toUpperCase()}${word.slice(1).toLowerCase()}`
				)
				.join('')
		: fallback;
};

export const isCitadelModelId = (modelId: string | null | undefined) => {
	return Boolean(modelId && String(modelId).toLowerCase().startsWith('hermes:'));
};

export const isAgentProfileModel = (model: { id?: string; owned_by?: string } | null | undefined) => {
	return Boolean(model?.owned_by === 'hermes' || isCitadelModelId(model?.id));
};

export const getModelDisplayName = (
	model:
		| { id?: string; name?: string; owned_by?: string; hermes?: { profile?: string } }
		| null
		| undefined
) => {
	if (isAgentProfileModel(model)) {
		return toPascalCaseName(model?.hermes?.profile ?? model?.name ?? model?.id, 'AgentProfile');
	}

	return model?.name || (model?.id ?? '');
};

export const getModelTooltipLabel = (
	model: { id?: string; name?: string; owned_by?: string } | null | undefined
) => {
	const displayName = getModelDisplayName(model);
	return isAgentProfileModel(model) ? displayName : `${displayName} (${model?.id ?? ''})`;
};

export const getModelShareUrl = (
	model: { id?: string; owned_by?: string } | null | undefined,
	baseUrl: string
) => {
	return isAgentProfileModel(model) ? `${baseUrl}/` : `${baseUrl}/?model=${encodeURIComponent(model?.id ?? '')}`;
};

export const getModelProfileImageUrl = (
	modelId: string | null | undefined,
	language: string | null | undefined = '',
	options: { voice?: boolean } = {}
) => {
	if (!modelId || isCitadelModelId(modelId)) {
		return CITADEL_ICON_URL;
	}

	const searchParams = new URLSearchParams();
	searchParams.set('id', modelId);
	if (language) {
		searchParams.set('lang', language);
	}
	if (options.voice) {
		searchParams.set('voice', 'true');
	}

	return `${WEBUI_API_BASE_URL}/models/model/profile/image?${searchParams.toString()}`;
};

export const useCitadelImageFallback = (event: Event) => {
	const target = event.currentTarget as HTMLImageElement | null;
	if (target) {
		const fallbackUrl = new URL(CITADEL_ICON_URL, window.location.href).href;
		if (target.dataset.fallbackApplied === fallbackUrl || target.src === fallbackUrl) {
			target.src = TRANSPARENT_IMAGE;
			return;
		}
		target.dataset.fallbackApplied = fallbackUrl;
		target.src = CITADEL_ICON_URL;
	}
};

export const useUserImageFallback = (event: Event) => {
	const target = event.currentTarget as HTMLImageElement | null;
	if (target) {
		const fallbackUrl = new URL(USER_ICON_URL, window.location.href).href;
		if (target.dataset.fallbackApplied === fallbackUrl || target.src === fallbackUrl) {
			target.src = TRANSPARENT_IMAGE;
			return;
		}
		target.dataset.fallbackApplied = fallbackUrl;
		target.src = USER_ICON_URL;
	}
};
