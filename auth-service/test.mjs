import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const intercepted=[];
const mf=new Miniflare(convertV4MiniflareOptions({modules:true,scriptPath:'src/index.js',compatibilityDate:'2026-10-16',d1Databases:{DB:'test'},bindings:{GITHUB_CLIENT_ID:'fixture',GITHUB_CLIENT_SECRET:'fixture-secret'},outboundService:async request=>{
 const url=new URL(request.url);intercepted.push(url.origin+url.pathname);
 if(url.href==='https://github.com/login/oauth/access_token'&&request.method==='POST')return Response.json({access_token:'fixture-token',token_type:'bearer'});
 if(url.href==='https://api.github.com/user'&&request.headers.get('Authorization')==='Bearer fixture-token')return Response.json({id:123,name:'Fixture User'});
 throw new Error('Unexpected outbound request');
}}));
const send=(path,body,headers={})=>mf.dispatchFetch('https://identity.test'+path,{method:body===undefined?'GET':'POST',headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),...headers},body:body===undefined?undefined:JSON.stringify(body),redirect:'manual'});
try{
 const db=await mf.getD1Database('DB');
 for(const sql of (await readFile('schema.sql','utf8')).split(';').filter(x=>x.trim()))await db.prepare(sql).run();
 assert.equal((await send('/session')).status,401);
 assert.equal((await send('/device/start',{provider:'google'})).status,503);
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
 assert.deepEqual(intercepted,['https://github.com/login/oauth/access_token','https://api.github.com/user']);
 console.log('Identity flow passed: unconfigured provider, cookie, PKCE, callback replay, one-time claim, server session, hashed storage, logout and expiry. Provider responses were mocked; no real provider login claimed.');
}finally{await mf.dispose();}
