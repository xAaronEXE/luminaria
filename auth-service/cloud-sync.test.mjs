import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {readFile} from 'node:fs/promises';import {fileURLToPath} from 'node:url';import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
const modules=['index','legal','cloud_sync'].map(name=>({type:'ESModule',path:fileURLToPath(new URL('./src/'+name+'.js',import.meta.url))}));
const mf=new Miniflare(convertV4MiniflareOptions({modules,compatibilityDate:'2026-10-16',d1Databases:{DB:'sync-test'},r2Buckets:['SYNC_BUCKET'],bindings:{SYNC_ENABLED:'true'}}));
const sha=value=>createHash('sha256').update(value).digest('hex'),a='a'.repeat(64),b='b'.repeat(64),time=Math.floor(Date.now()/1000);
const send=(path,token=a,body,method=body===undefined?'GET':'PUT')=>mf.dispatchFetch('https://identity.test/sync/'+path,{method,headers:{...(token?{Authorization:'Bearer '+token}:{}),...(body!==undefined?{'Content-Type':'application/json'}:{})},body:body===undefined?undefined:JSON.stringify(body)});
const mutation=(base,id,data={title:'Memory',content:'Keep this'})=>({base,mutation:id,data,deleted:false});
try{
 const db=await mf.getD1Database('DB');for(const sql of (await readFile(new URL('./schema.sql',import.meta.url),'utf8')).split(';').filter(s=>s.trim()))await db.prepare(sql).run();
 for(const [id,token] of [['account-a',a],['account-b',b]]){await db.prepare('INSERT INTO identities(id,provider,subject,name,created) VALUES(?,?,?,?,?)').bind(id,'google',id,id,time).run();await db.prepare('INSERT INTO account_members VALUES(?,?,?)').bind(id,id,'google').run();await db.prepare('INSERT INTO sessions VALUES(?,?,?,?,?,?)').bind(sha(token),id,time+600,time,time,'test').run()}
 assert.equal((await send('status',null)).status,401);assert.equal((await send('status','c'.repeat(64))).status,401);
 let r=await send('records/memory/first',a,mutation(0,'write1'));assert.equal(r.status,200);assert.equal((await r.json()).version,1);
 assert.equal((await send('records/memory/first',b)).status,404);assert.equal((await (await send('records',b)).json()).records.length,0);
 assert.equal((await (await send('records/memory/first',a,mutation(0,'write1'))).json()).version,1);
 assert.equal((await send('records/memory/first',a,mutation(0,'write1',{content:'different'}))).status,409);
 const races=await Promise.all([send('records/memory/first',a,mutation(1,'racer1',{content:'one'})),send('records/memory/first',a,mutation(1,'racer2',{content:'two'}))]);assert.deepEqual(races.map(r=>r.status).sort(),[200,409]);
 const row=await (await send('records/memory/first')).json();assert.equal(row.version,2);
 assert.equal((await send('records/memory/first',a,{...mutation(2,'delete1',row.data),deleted:true})).status,200);assert.equal((await (await send('records/memory/first')).json()).deleted,1);
 const content=new TextEncoder().encode('file content'),hash=sha(content);
 const upload=await mf.dispatchFetch('https://identity.test/sync/blobs/'+hash,{method:'PUT',headers:{Authorization:'Bearer '+a,'Content-Length':String(content.length)},body:content});assert.equal(upload.status,200);
 assert.equal(await (await send('blobs/'+hash)).text(),'file content');assert.equal((await send('blobs/'+hash,b)).status,404);
 assert.equal((await send('records/file/file1',b,mutation(0,'foreign',{blob:hash}))).status,409);
 const wrong=await mf.dispatchFetch('https://identity.test/sync/blobs/'+'0'.repeat(64),{method:'PUT',headers:{Authorization:'Bearer '+a,'Content-Length':String(content.length)},body:content});assert.equal(wrong.status,400);assert.equal((await send('blobs/'+'0'.repeat(64))).status,404);
 const empty=sha('');assert.equal((await mf.dispatchFetch('https://identity.test/sync/blobs/'+empty,{method:'PUT',headers:{Authorization:'Bearer '+a,'Content-Length':'0'},body:new Uint8Array()})).status,200);
 const period=new Date().toISOString().slice(0,10);
 await db.prepare('INSERT OR REPLACE INTO sync_budget VALUES(?,?)').bind('write:'+period,249).run();
 const beforeObjects=(await (await mf.getR2Bucket('SYNC_BUCKET')).list()).objects.length;
 const limited=await Promise.all(['quota one','quota two'].map(text=>mf.dispatchFetch('https://identity.test/sync/blobs/'+sha(text),{method:'PUT',headers:{Authorization:'Bearer '+b,'Content-Length':String(text.length)},body:text})));
 assert.deepEqual(limited.map(r=>r.status).sort(),[200,429]);
 assert.equal((await (await mf.getR2Bucket('SYNC_BUCKET')).list()).objects.length,beforeObjects+1);
 assert.equal((await db.prepare('SELECT used FROM sync_budget WHERE key=?').bind('write:'+period).first()).used,250);
 await db.prepare('INSERT INTO sync_blobs(account_id,hash,size,created) VALUES(?,?,?,?)').bind('budget-account','f'.repeat(64),512*1024*1024,time).run();
 const noStorage=await mf.dispatchFetch('https://identity.test/sync/blobs/'+sha('storage cap'),{method:'PUT',headers:{Authorization:'Bearer '+b,'Content-Length':'11'},body:'storage cap'});assert.equal(noStorage.status,413);
 await db.prepare('UPDATE sessions SET expires=? WHERE token_hash=?').bind(time-1,sha(a)).run();assert.equal((await send('records')).status,401);
 console.log('Cloud sync service passed: authentication, isolation, revision races, retry idempotency, tombstones, private files, integrity, empty files, revocation, concurrent operation budgets and global storage caps.');
}finally{await mf.dispose()}
