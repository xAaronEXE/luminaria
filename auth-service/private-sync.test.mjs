import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join } from 'node:path';

const dependencyRoot = process.env.LUMINARIA_TEST_NODE_PROJECT;
const require = createRequire(dependencyRoot ? join(dependencyRoot, 'package.json') : import.meta.url);
const { Miniflare, convertV4MiniflareOptions } = await import(pathToFileURL(require.resolve('miniflare')).href);
const devices = ['a'.repeat(64), 'b'.repeat(64)];
const hashes = devices.map(key => createHash('sha256').update(key).digest('hex'));
const modules = ['private_sync', 'cloud_sync'].map(name => ({
  type: 'ESModule',
  path: fileURLToPath(new URL('./src/' + name + '.js', import.meta.url)),
}));
const worker = new Miniflare(convertV4MiniflareOptions({
  modules,
  compatibilityDate: '2026-10-16',
  d1Databases: { DB: 'private-sync-test' },
  r2Buckets: ['SYNC_BUCKET'],
  bindings: { SYNC_ENABLED: 'true', SYNC_DEVICE_KEY_HASHES: JSON.stringify(hashes) },
}));

const send = (path, token, data) => worker.dispatchFetch('https://private-sync.test/' + path, {
  method: data ? 'PUT' : 'GET',
  headers: token ? { Authorization: 'Bearer ' + token } : {},
  body: data ? JSON.stringify(data) : undefined,
});

try {
  const db = await worker.getD1Database('DB');
  const migration = await readFile(new URL('./migrations/0005_cloud_sync.sql', import.meta.url), 'utf8');
  for (const statement of migration.split(';').filter(sql => sql.trim())) await db.prepare(statement).run();
  assert.equal((await send('sync/status')).status, 401);
  assert.equal((await send('sync/status', hashes[0])).status, 401);
  assert.equal((await send('sync/status', 'c'.repeat(64))).status, 401);
  assert.equal((await send('oauth/start', devices[0])).status, 404);
  const status = await send('sync/status', devices[0]);
  assert.equal(status.status, 200);
  assert.equal((await status.json()).account_id, 'private-sync');
  const record = { base: 0, mutation: 'one', data: { envelope: 'opaque ciphertext' }, deleted: false };
  assert.equal((await send('sync/records/memory/demo', devices[0], record)).status, 200);
  const received = await send('sync/records/memory/demo', devices[1]);
  assert.equal(received.status, 200);
  assert.deepEqual((await received.json()).data, record.data);
  console.log('Private sync Worker passed authentication and cross-device storage checks.');
} finally {
  await worker.dispose();
}
