import { WEBUI_API_BASE_URL } from '$lib/constants';
import { toPascalCaseName } from '$lib/utils/modelImages';

const HERMES_PREFIX = 'hermes:';
const HERMES_MODEL_OVERRIDE_SEP = '#model=';

export const isHermesModelId = (modelId: string | null | undefined) =>
	typeof modelId === 'string' && modelId.startsWith(HERMES_PREFIX);

export const getHermesProfileFromModelId = (modelId: string | null | undefined) => {
	if (!isHermesModelId(modelId)) {
		return '';
	}
	const value = modelId as string;
	return value.slice(HERMES_PREFIX.length).split(HERMES_MODEL_OVERRIDE_SEP)[0] || 'default';
};

export const toPascalCaseProfileName = (value: string | null | undefined) => {
	return toPascalCaseName(value, 'Default');
};

export const getHermesFallbackFromModelId = (modelId: string | null | undefined) => {
	if (!isHermesModelId(modelId)) {
		return '';
	}
	const value = modelId as string;
	if (!value.includes(HERMES_MODEL_OVERRIDE_SEP)) {
		return '';
	}
	const encoded = value.split(HERMES_MODEL_OVERRIDE_SEP, 2)[1] || '';
	try {
		return decodeURIComponent(encoded);
	} catch {
		return encoded;
	}
};

export const buildHermesModelId = (profile: string, fallbackModel: string = '') => {
	const base = `${HERMES_PREFIX}${profile || 'default'}`;
	return fallbackModel ? `${base}${HERMES_MODEL_OVERRIDE_SEP}${encodeURIComponent(fallbackModel)}` : base;
};

export const getHermesSessions = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/hermes/sessions`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
