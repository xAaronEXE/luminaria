import { cloudSync } from './cloud_sync.js';

const hex = /^[a-f0-9]{64}$/;
const bytes = value => Uint8Array.from(value.match(/../g), pair => Number.parseInt(pair, 16));

async function privateAccount(token, env) {
  let keys;
  try {
    keys = JSON.parse(env.SYNC_DEVICE_KEY_HASHES || '[]');
  } catch {
    return null;
  }
  if (!Array.isArray(keys) || !keys.length || keys.length > 32 || keys.some(key => typeof key !== 'string' || !hex.test(key))) return null;

  const received = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token));
  let allowed = false;
  for (const key of keys) allowed = crypto.subtle.timingSafeEqual(received, bytes(key)) || allowed;
  return allowed ? { account_id: 'private-sync' } : null;
}

export default {
  fetch(request, env) {
    if (!new URL(request.url).pathname.startsWith('/sync/')) {
      return new Response('Not found', { status: 404 });
    }
    return cloudSync(request, env, privateAccount);
  },
};
