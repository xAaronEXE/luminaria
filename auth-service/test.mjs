import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const intercepted=[],tokenForms={};
const bindings={GITHUB_CLIENT_ID:'fixture',GITHUB_CLIENT_SECRET:'fixture-secret',GOOGLE_CLIENT_ID:'google-fixture',GOOGLE_CLIENT_SECRET:'google-secret',DISCORD_CLIENT_ID:'discord-fixture',DISCORD_CLIENT_SECRET:'discord-secret'};
const tokens={'https://github.com/login/oauth/access_token':['github',{access_token:'fixture-token',token_type:'bearer'}],'https://oauth2.googleapis.com/token':['google',{access_token:'google-token',token_type:'Bearer',id_token:'unused'}],'https://discord.com/api/oauth2/token':['discord',{access_token:'discord-token',token_type:'Bearer'}]};
const users={'https://api.github.com/user':['fixture-token',{id:123,name:'Fixture User'}],'https://openidconnect.googleapis.com/v1/userinfo':['google-token',{sub:'g-4471',name:'Google Fixture'}],'https://discord.com/api/users/@me':['discord-token',{id:'99001',username:'fixture_d',global_name:'Discord Fixture'}]};
const mf=new Miniflare(convertV4MiniflareOptions({modules:true,scriptPath:fileURLToPath(new URL('./src/index.js',import.meta.url)),compatibilityDate:'2026-10-16',d1Databases:{DB:'test'},bindings,outboundService:async request=>{
 const url=new URL(request.url),href=url.origin+url.pathname;intercepted.push(href);
 if(tokens[href]&&request.method==='POST'){tokenForms[tokens[href][0]]=new URLSearchParams(await request.text());return Response.json(tokens[href][1]);}
 if(users[href]&&request.headers.get('Authorization')==='Bearer '+users[href][0])return Response.json(users[href][1]);
 throw new Error('Unexpected outbound request');
}}));
const send=(path,body,headers={})=>mf.dispatchFetch('https://identity.test'+path,{method:body===undefined?'GET':'POST',headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),...headers},body:body===undefined?undefined:JSON.stringify(body),redirect:'manual'});
async function begin(provider,headers={}){
 const started=await (await send('/device/start',{provider},headers)).json();
 const redirected=await send('/authorize?device='+started.device_id);
 assert.equal(redirected.status,302);
 return {started,oauth:new URL(redirected.headers.get('location')),cookie:redirected.headers.get('set-cookie').split(';')[0]};
}
async function signIn(provider,headers={}){
 const {started,oauth,cookie}=await begin(provider,headers);
 const page=await send(`/callback/${provider}?code=code-${provider}&state=${oauth.searchParams.get('state')}`,undefined,{Cookie:cookie});
 assert.equal(page.status,200);assert.match(page.headers.get('content-type'),/text\/html/);assert.match(await page.text(),/Signed in to Luminaria/);
 const session=await (await send('/device/poll',started)).json();
 return {oauth,session,...await (await send('/session',undefined,{Authorization:'Bearer '+session.access_token})).json()};
}
try{
 const db=await mf.getD1Database('DB');
 for(const sql of (await readFile(new URL('./schema.sql',import.meta.url),'utf8')).split(';').filter(x=>x.trim()))await db.prepare(sql).run();
 assert.equal((await send('/session')).status,401);
 assert.equal((await send('/device/start',{provider:'facebook'})).status,503);
 const health=await (await send('/health')).json();
 assert.deepEqual(health.providers.map(p=>p.configured),[true,true,true]);
 const started=await (await send('/device/start',{provider:'github'})).json();
 assert.equal(started.device_secret.length,64);
 assert.equal((await send('/device/poll',started)).status,202);
 assert.equal((await send('/device/poll',{...started,device_secret:'0'.repeat(64)})).status,400);
 const redirected=await send('/authorize?device='+started.device_id);
 assert.equal(redirected.status,302);
 const oauth=new URL(redirected.headers.get('location'));
 assert.equal(oauth.searchParams.get('code_challenge_method'),'S256');
 const callback='/callback/github?code=test-code&state='+oauth.searchParams.get('state');
 assert.equal((await send(callback)).status,400); // Cookie is mandatory; state remains usable.
 const cookie=redirected.headers.get('set-cookie').split(';')[0];
 assert.equal((await send(callback,undefined,{Cookie:cookie})).status,200);
 assert.equal((await send(callback,undefined,{Cookie:cookie})).status,400); // Replay rejected.
 const session=await (await send('/device/poll',started)).json();
 assert.equal(session.access_token.length,64);
 assert.equal((await send('/device/poll',started)).status,400); // One-time claim.
 const headers={Authorization:'Bearer '+session.access_token};
 const checked=await (await send('/session',undefined,headers)).json();
 assert.equal(checked.user.name,'Fixture User');assert.equal(checked.user.provider,'github');
 const stored=await db.prepare('SELECT token_hash FROM sessions').first();assert.notEqual(stored.token_hash,session.access_token);
 assert.equal((await send('/logout',{},headers)).status,200);
 assert.equal((await send('/session',undefined,headers)).status,401);
 const expired=await (await send('/device/start',{provider:'github'})).json();
 await db.prepare('UPDATE devices SET expires=0 WHERE id=?').bind(expired.device_id).run();
 assert.equal((await send('/device/poll',expired)).status,400);

 const google=await signIn('google');
 assert.equal(google.oauth.origin+google.oauth.pathname,'https://accounts.google.com/o/oauth2/v2/auth');
 assert.equal(google.oauth.searchParams.get('scope'),'openid profile');
 assert.equal(google.oauth.searchParams.get('prompt'),'select_account');
 assert.equal(google.oauth.searchParams.get('code_challenge_method'),'S256');
 assert.equal(google.oauth.searchParams.get('redirect_uri'),'https://identity.test/callback/google');
 assert.equal(tokenForms.google.get('client_secret'),'google-secret');assert.equal(tokenForms.google.get('code_verifier').length,64);
 assert.equal(google.user.provider,'google');assert.equal(google.user.name,'Google Fixture');
 const discord=await signIn('discord');
 assert.equal(discord.oauth.searchParams.get('scope'),'identify');
 assert.equal(discord.oauth.searchParams.get('code_challenge'),null);
 assert.equal(tokenForms.discord.get('redirect_uri'),'https://identity.test/callback/discord');
 assert.equal(discord.user.provider,'discord');assert.equal(discord.user.name,'Discord Fixture');
 const identities=await db.prepare('SELECT provider,subject FROM identities ORDER BY provider').all();
 assert.deepEqual(identities.results.map(r=>r.provider+':'+r.subject),['discord:99001','github:123','google:g-4471']);

 const denied=await begin('google');
 const refusal=await send(`/callback/google?error=access_denied&state=${denied.oauth.searchParams.get('state')}`,undefined,{Cookie:denied.cookie});
 assert.equal(refusal.status,200);assert.match(await refusal.text(),/Sign-in cancelled/);
 assert.equal((await send('/device/poll',denied.started)).status,403);
 assert.equal((await send('/device/poll',denied.started)).status,400); // Cancellation is reported once.
 assert.equal((await send('/authorize?device='+denied.started.device_id)).status,400);
 const forged=await begin('discord');
 assert.equal((await send(`/callback/discord?error=access_denied&state=${'0'.repeat(64)}`,undefined,{Cookie:forged.cookie})).status,400);
 assert.equal((await send('/device/poll',forged.started)).status,202); // A forged refusal cannot cancel someone else's request.
 assert.equal((await db.prepare("SELECT count(*) AS n FROM sessions WHERE identity_id='denied'").first()).n,0);

 assert.deepEqual(intercepted,['https://github.com/login/oauth/access_token','https://api.github.com/user','https://oauth2.googleapis.com/token','https://openidconnect.googleapis.com/v1/userinfo','https://discord.com/api/oauth2/token','https://discord.com/api/users/@me']);
 // Account linking proves both sessions and creates one canonical account.
 assert.equal((await send('/device/start',{provider:'google'},{Authorization:'Bearer '+'0'.repeat(64)})).status,401);
 const linked=await signIn('google',{Authorization:'Bearer '+discord.session.access_token});
 assert.equal(linked.account.id,discord.account.id);
 assert.deepEqual(new Set(linked.connections.map(x=>x.provider)),new Set(['discord','google']));
 const googleAgain=await signIn('google');
 assert.equal(googleAgain.account.id,discord.account.id);
 const revokedParent=await begin('github',{Authorization:'Bearer '+linked.session.access_token});
 await send('/logout',{}, {Authorization:'Bearer '+linked.session.access_token});
 const deniedLink=await send(`/callback/github?code=code-github&state=${revokedParent.oauth.searchParams.get('state')}`,undefined,{Cookie:revokedParent.cookie});
 assert.equal(deniedLink.status,200);
 assert.equal((await send('/device/poll',revokedParent.started)).status,403);
 const foreignId=crypto.randomUUID(),foreignToken='e'.repeat(64);
 const foreignHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(foreignToken))),x=>x.toString(16).padStart(2,'0')).join('');
 await db.prepare('INSERT INTO identities VALUES(?,?,?,?,?)').bind(foreignId,'google','another-google-user','Other account',1).run();
 await db.prepare('INSERT INTO account_members VALUES(?,?,?)').bind(foreignId,foreignId,'google').run();
 await db.prepare('INSERT INTO sessions(token_hash,identity_id,expires) VALUES(?,?,?)').bind(foreignHash,foreignId,Math.floor(Date.now()/1000)+600).run();
 const conflict=await begin('google',{Authorization:'Bearer '+foreignToken});
 const conflictPage=await send(`/callback/google?code=code-google&state=${conflict.oauth.searchParams.get('state')}`,undefined,{Cookie:conflict.cookie});
 assert.equal(conflictPage.status,200);assert.equal((await send('/device/poll',conflict.started)).status,409);
 assert.equal((await db.prepare('SELECT account_id FROM account_members WHERE identity_id=?').bind(foreignId).first()).account_id,foreignId);

 // Remembered devices: labelled sessions, sliding expiry with an absolute cap, listing and revocation within one account only.
 const labelled=await begin('discord');
 await send(`/callback/discord?code=code-discord&state=${labelled.oauth.searchParams.get('state')}`,undefined,{Cookie:labelled.cookie});
 const laptop=await (await send('/device/poll',{...labelled.started,label:'Aaron <laptop>\u0000 ✓'})).json();
 const day=86400,clock=Math.floor(Date.now()/1000);
 assert.ok(Math.abs(laptop.expires_at-(clock+30*day))<60);
 const laptopAuth={Authorization:'Bearer '+laptop.access_token},desktopAuth={Authorization:'Bearer '+discord.session.access_token};
 const listing=await (await send('/sessions',undefined,laptopAuth)).json();
 assert.equal(listing.idle_days,30);assert.equal(listing.max_days,90);
 const mine=listing.devices.find(d=>d.current);assert.equal(mine.label,'Aaron laptop');assert.equal(mine.provider,'discord');assert.equal(mine.id.length,16);
 assert.ok(listing.devices.some(d=>d.provider==='google'));assert.ok(!listing.devices.some(d=>d.provider==='google'&&d.label==='Other account'));
 assert.equal(listing.devices.filter(d=>d.current).length,1);
 const foreignListed=await (await send('/sessions',undefined,{Authorization:'Bearer '+foreignToken})).json();
 assert.ok(foreignListed.devices.every(d=>!listing.devices.some(x=>x.id===d.id)));
 assert.equal((await send('/sessions/revoke',{id:foreignHash.slice(0,16)},laptopAuth)).status,404); // Another account's device cannot be revoked.
 assert.equal((await send('/session',undefined,{Authorization:'Bearer '+foreignToken})).status,200);
 const laptopHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(laptop.access_token))),x=>x.toString(16).padStart(2,'0')).join('');
 await db.prepare('UPDATE sessions SET expires=?,last_seen=?,created=? WHERE token_hash=?').bind(clock+2*day,clock-2*day,clock-89*day,laptopHash).run();
 const capped=await (await send('/session',undefined,laptopAuth)).json();
 assert.equal(capped.user.expires,clock+2*day); // At the 90-day cap a session is not extended (nor shortened).
 await db.prepare('UPDATE sessions SET expires=?,last_seen=?,created=? WHERE token_hash=?').bind(clock+2*day,clock-2*day,clock-10*day,laptopHash).run();
 const renewed=await (await send('/session',undefined,laptopAuth)).json();
 assert.ok(Math.abs(renewed.user.expires-(clock+30*day))<60);
 const legacy=await (await send('/session',undefined,{Authorization:'Bearer '+foreignToken})).json();assert.ok(legacy.user.expires>clock); // Sessions from before the migration keep working.
 const desktopId=listing.devices.find(d=>!d.current&&d.provider==='discord').id;
 assert.deepEqual(await (await send('/sessions/revoke',{id:desktopId},laptopAuth)).json(),{revoked:1,current:false});
 assert.equal((await send('/session',undefined,desktopAuth)).status,401);
 assert.equal((await send('/sessions/revoke',{id:'xyz'},laptopAuth)).status,400);
 const others=await (await send('/sessions/revoke',{others:true},laptopAuth)).json();assert.ok(others.revoked>=1);
 assert.equal((await send('/session',undefined,{Authorization:'Bearer '+googleAgain.session.access_token})).status,401);
 assert.equal((await send('/session',undefined,laptopAuth)).status,200);
 assert.equal((await send('/session',undefined,{Authorization:'Bearer '+foreignToken})).status,200);
 assert.equal((await send('/sessions',undefined,{Authorization:'Bearer '+'0'.repeat(64)})).status,401);

 console.log('Identity flow passed: GitHub, Google and Discord pairing, cookie, PKCE, callback replay, one-time claim, server session, hashed storage, logout, expiry, remembered devices (sliding 30-day expiry, 90-day cap, listing, revocation scoped to one account), browser cancellation and forged refusal. Provider responses were mocked; no real provider login claimed.');
}finally{await mf.dispose();}
