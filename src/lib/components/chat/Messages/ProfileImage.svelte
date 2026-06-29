<script lang="ts">
	import { CITADEL_ICON_URL } from '$lib/utils/modelImages';
	import { safeImageUrl } from '$lib/utils/safeImageUrl';

	export let className = 'size-8';
	export let src = CITADEL_ICON_URL;
</script>

<img
	aria-hidden="true"
	src={safeImageUrl(src)}
	class=" {className} object-cover rounded-full"
	alt="profile"
	draggable="false"
/>
