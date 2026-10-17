// Identity only: provider access tokens are never returned to the desktop or saved.
const providers = {
 github:{authorize:'https://github.com/login/oauth/authorize',token:'https://github.com/login/oauth/access_token',user:'https://api.github.com/user',scope:'read:user',pkce:true},
 google:{authorize:'https://accounts.google.com/o/oauth2/v2/auth',token:'https://oauth2.googleapis.com/token',user:'https://openidconnect.googleapis.com/v1/userinfo',scope:'openid profile',pkce:true,extra:{prompt:'select_account'}},
 discord:{authorize:'https://discord.com/oauth2/authorize',token:'https://discord.com/api/oauth2/token',user:'https://discord.com/api/users/@me',scope:'identify',pkce:false}
};
const now=()=>Math.floor(Date.now()/1000);
// A remembered device stays signed in for 30 days after its last use, and never longer than 90 days in total.
const SESSION_IDLE=30*86400,SESSION_MAX=90*86400;
const deviceLabel=value=>typeof value==='string'?value.replace(/[^\p{L}\p{N} ._'()-]/gu,'').trim().slice(0,60)||null:null;
const random=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),x=>x.toString(16).padStart(2,'0')).join('');
const bytes=value=>new TextEncoder().encode(value);
async function hash(value){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes(value))),x=>x.toString(16).padStart(2,'0')).join('');}
async function challenge(value){return btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes(value))))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');}
function json(value,status=200){return Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}});}
// A denied device keeps this marker until the desktop polls, so it can stop waiting.
const DENIED='denied';
const pageStyle='body{margin:0;min-height:100vh;display:grid;place-items:center;background:#fff;color:#0a0a0a;font:15px/1.5 system-ui,sans-serif}@media(prefers-color-scheme:dark){body{background:#000;color:#f5f5f2}}main{max-width:420px;padding:32px}h1{font-size:22px;font-weight:600;margin:0 0 8px}p{margin:0;opacity:.75}';
function page(title,message,status=200,headers={}){
 const escape=value=>value.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 return new Response(`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)} · Luminaria</title><style>${pageStyle}</style><main><h1>${escape(title)}</h1><p>${escape(message)}</p></main></html>`,{status,headers:{'Content-Type':'text/html; charset=utf-8','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'",'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',...headers}});
}
const clearCookie={'Set-Cookie':'__Host-luminaria_oauth=; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'};
function configured(env,name){return Boolean(providers[name]&&env[name.toUpperCase()+'_CLIENT_ID']&&env[name.toUpperCase()+'_CLIENT_SECRET']);}
async function body(request){
 if(!request.headers.get('content-type')?.startsWith('application/json'))throw new Error('JSON required');
 const reader=request.body?.getReader();if(!reader)throw new Error('Body required');
 let size=0,chunks=[];
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>4096){await reader.cancel();throw new Error('Body too large');}chunks.push(value);}
 const result=new Uint8Array(size);let offset=0;for(const chunk of chunks){result.set(chunk,offset);offset+=chunk.length;}
 return JSON.parse(new TextDecoder().decode(result));
}
async function limited(env,request){
 const key=await hash((request.headers.get('CF-Connecting-IP')||'local')+':'+Math.floor(now()/3600));
 const row=await env.DB.prepare('INSERT INTO rate_limits(key,count,expires) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1 RETURNING count').bind(key,now()+7200).first();
 return row.count>600;
}
// Upstream bodies are bounded to protect the Worker from unexpected payloads.
async function boundedText(response,limit){
 const reader=response.body.getReader();let size=0,chunks=[];
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();throw new Error('Upstream response too large');}chunks.push(value);}
 const result=new Uint8Array(size);let offset=0;for(const chunk of chunks){result.set(chunk,offset);offset+=chunk.length;}
 return new TextDecoder().decode(result);
}
async function providerJson(url,options){
 const response=await fetch(url,{...options,signal:AbortSignal.timeout(15000)});
 if(!response.ok)throw new Error('Provider request failed');
 return JSON.parse(await boundedText(response,131072));
}
// Release channel: the source repository is private, so a read-only token stays here.
const installerName=/^Luminaria-(\d+\.\d+\.\d+)-Setup\.exe$/;
const releaseTag=/^v(\d+\.\d+\.\d+)$/;
function releasesConfigured(env){return /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(env.RELEASE_REPO||'')&&Boolean(env.GITHUB_RELEASES_TOKEN);}
function github(env,path,accept='application/vnd.github+json',timeout=true){
 return fetch('https://api.github.com/repos/'+env.RELEASE_REPO+path,{headers:{Authorization:'Bearer '+env.GITHUB_RELEASES_TOKEN,Accept:accept,'User-Agent':'Luminaria-Updates','X-GitHub-Api-Version':'2022-11-28'},redirect:'manual',...(timeout?{signal:AbortSignal.timeout(20000)}:{})});
}
async function assetResponse(env,asset,timeout=true){
 const first=await github(env,'/releases/assets/'+asset.id,'application/octet-stream',timeout);
 if(first.status===200)return first;
 const location=[301,302,303,307,308].includes(first.status)&&first.headers.get('location');
 if(!location)throw new Error('Release asset unavailable');
 const host=new URL(location).hostname;
 if(new URL(location).protocol!=='https:'||!(host.endsWith('.githubusercontent.com')||host==='github.com'))throw new Error('Unexpected release asset host');
 const response=await fetch(location,timeout?{signal:AbortSignal.timeout(20000)}:{});
 if(!response.ok)throw new Error('Release asset unavailable');
 return response;
}
async function releaseManifest(env,origin){
 const response=await github(env,'/releases/latest');
 if(response.status===404)return {status:404};
 if(!response.ok)throw new Error('Release lookup failed');
 const release=JSON.parse(await boundedText(response,1048576));
 const version=String(release.tag_name||'').match(releaseTag)?.[1];
 const installer=(release.assets||[]).find(asset=>installerName.test(asset.name));
 const sums=(release.assets||[]).find(asset=>asset.name==='SHA256SUMS.txt');
 if(!version||!installer||!sums||installer.name.match(installerName)[1]!==version)return {status:409};
 const lines=(await boundedText(await assetResponse(env,sums),65536)).split(/\r?\n/).map(line=>line.trim().split(/\s+/));
 const sha256=lines.find(parts=>parts.length===2&&parts[1].replace(/^\*/,'')===installer.name)?.[0]?.toLowerCase();
 if(!/^[a-f0-9]{64}$/.test(sha256||''))return {status:409};
 return {status:200,body:{version,tag:release.tag_name,name:String(release.name||'Luminaria '+version).slice(0,200),notes:String(release.body||'').slice(0,12000),published_at:release.published_at,
  installer:{name:installer.name,size:installer.size,sha256,url:origin+'/releases/download/'+release.tag_name+'/'+installer.name}}};
}
async function releaseDownload(env,tag,name){
 if(!releaseTag.test(tag)||!installerName.test(name)||name.match(installerName)[1]!==tag.slice(1))return json({error:'Not found'},404);
 const response=await github(env,'/releases/tags/'+tag);
 if(response.status===404)return json({error:'Not found'},404);
 if(!response.ok)throw new Error('Release lookup failed');
 const release=JSON.parse(await boundedText(response,1048576));
 const asset=(release.assets||[]).find(item=>item.name===name);
 if(!asset||release.draft)return json({error:'Not found'},404);
 const upstream=await assetResponse(env,asset,false);
 const headers={'Content-Type':'application/octet-stream','Content-Disposition':'attachment; filename="'+name+'"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
 if(upstream.headers.get('content-length'))headers['Content-Length']=upstream.headers.get('content-length');
 return new Response(upstream.body,{headers});
}
async function route(request,env){
 const url=new URL(request.url),path=url.pathname,time=now();
 if(path==='/health'&&request.method==='GET')return json({service:'Luminaria identity',providers:Object.keys(providers).map(id=>({id,configured:configured(env,id)}))});
 if(await limited(env,request))return json({error:'Too many requests'},429);
 if(path.startsWith('/releases/')&&request.method==='GET'){
  if(!releasesConfigured(env))return json({error:'Release channel is not configured'},503);
  if(path==='/releases/latest'){
   const manifest=await releaseManifest(env,url.origin);
   if(manifest.status===404)return json({error:'No release has been published'},404);
   if(manifest.status===409)return json({error:'Latest release is missing its installer or checksum'},409);
   return json(manifest.body);
  }
  const parts=path.split('/');
  if(parts.length===5&&parts[2]==='download')return releaseDownload(env,parts[3],parts[4]);
  return json({error:'Not found'},404);
 }
 if(path==='/device/start'&&request.method==='POST'){
  const input=await body(request),provider=input.provider;
  if(!configured(env,provider))return json({error:'Sign-in provider is not configured'},503);
  const authorization=request.headers.get('Authorization');let parentHash=null;
  if(authorization){
   const parent=authorization.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
   if(!parent)return json({error:'Valid sign-in required to link accounts'},401);
   parentHash=await hash(parent);
   const session=await env.DB.prepare('SELECT identity_id FROM sessions WHERE token_hash=? AND expires>?').bind(parentHash,time).first();
   if(!session)return json({error:'Sign in again before connecting another sign-in method'},401);
  }
  const id=random(),secret=random();
  await env.DB.prepare('INSERT INTO devices(id,secret_hash,provider,expires) VALUES(?,?,?,?)').bind(id,await hash(secret),provider,time+600).run();
  if(parentHash)await env.DB.prepare('INSERT INTO device_links VALUES(?,?,?)').bind(id,parentHash,time+600).run();
  return json({device_id:id,device_secret:secret,verification_uri:url.origin+'/authorize?device='+id,expires_in:600,interval:5});
 }
 if(path==='/authorize'&&request.method==='GET'){
  const id=url.searchParams.get('device');
  const device=await env.DB.prepare('SELECT * FROM devices WHERE id=? AND expires>? AND identity_id IS NULL').bind(id,time).first();
  if(!device||!configured(env,device.provider))return page('Sign-in link expired','Start sign-in again from Luminaria.',400);
  const provider=providers[device.provider],state=random(),cookie=random(),verifier=random();
  await env.DB.prepare('INSERT INTO oauth_states VALUES(?,?,?,?,?,?)').bind(await hash(state),await hash(cookie),id,device.provider,verifier,time+600).run();
  const target=new URL(provider.authorize);
  target.search=new URLSearchParams({client_id:env[device.provider.toUpperCase()+'_CLIENT_ID'],redirect_uri:url.origin+'/callback/'+device.provider,response_type:'code',scope:provider.scope,state,...provider.extra}).toString();
  if(provider.pkce){target.searchParams.set('code_challenge',await challenge(verifier));target.searchParams.set('code_challenge_method','S256');}
  return new Response(null,{status:302,headers:{Location:target.href,'Set-Cookie':`__Host-luminaria_oauth=${cookie}; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=600`,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
 }
 if(path.startsWith('/callback/')&&request.method==='GET'){
  const providerName=path.slice(10),state=url.searchParams.get('state')||'',code=url.searchParams.get('code'),refused=url.searchParams.get('error');
  const cookie=(request.headers.get('Cookie')||'').match(/(?:^|;\s*)__Host-luminaria_oauth=([a-f0-9]{64})(?:;|$)/)?.[1];
  if((!code&&!refused)||!cookie||!configured(env,providerName))return page('Sign-in could not be completed','Start sign-in again from Luminaria.',400);
  // Atomic consumption prevents parallel callbacks from reusing an authorization.
  const entry=await env.DB.prepare('DELETE FROM oauth_states WHERE state_hash=? AND cookie_hash=? AND provider=? AND expires>? RETURNING *').bind(await hash(state),await hash(cookie),providerName,time).first();
  if(!entry)return page('Sign-in expired or already used','Start sign-in again from Luminaria.',400);
  if(refused){
   await env.DB.prepare('UPDATE devices SET identity_id=? WHERE id=? AND expires>? AND identity_id IS NULL').bind(DENIED,entry.device_id,time).run();
   return page('Sign-in cancelled','Nothing was shared. You can close this tab; Luminaria has stopped waiting.',200,clearCookie);
  }
  const provider=providers[providerName],form=new URLSearchParams({grant_type:'authorization_code',client_id:env[providerName.toUpperCase()+'_CLIENT_ID'],client_secret:env[providerName.toUpperCase()+'_CLIENT_SECRET'],code,redirect_uri:url.origin+path});
  if(provider.pkce)form.set('code_verifier',entry.verifier);
  const token=await providerJson(provider.token,{method:'POST',headers:{Accept:'application/json','Content-Type':'application/x-www-form-urlencoded'},body:form.toString()});
  if(typeof token.access_token!=='string'||token.token_type?.toLowerCase()!=='bearer')throw new Error('Provider token missing');
  const user=await providerJson(provider.user,{headers:{Authorization:'Bearer '+token.access_token,Accept:'application/json','User-Agent':'Luminaria'}});
  const subject=providerName==='google'?user.sub:user.id;
  if((typeof subject!=='string'&&typeof subject!=='number')||!String(subject))throw new Error('Provider identity missing');
  const name=String(user.name||user.global_name||user.login||user.username||'Luminaria user').slice(0,120);
  const identity=await env.DB.prepare('INSERT INTO identities VALUES(?,?,?,?,?) ON CONFLICT(provider,subject) DO UPDATE SET name=excluded.name RETURNING id').bind(crypto.randomUUID(),providerName,String(subject),name,time).first();
  await env.DB.prepare('UPDATE devices SET identity_id=? WHERE id=? AND expires>? AND identity_id IS NULL').bind(identity.id,entry.device_id,time).run();
  return page('Signed in to Luminaria','You can close this tab and return to the desktop app.',200,clearCookie);
 }
 if(path==='/device/poll'&&request.method==='POST'){
  const input=await body(request);
  if(typeof input.device_secret!=='string'||input.device_secret.length!==64)return json({error:'Invalid device request'},400);
  const digest=await hash(input.device_secret);
  const device=await env.DB.prepare('SELECT * FROM devices WHERE id=? AND secret_hash=? AND expires>?').bind(input.device_id,digest,time).first();
  if(!device)return json({error:'Device request expired or consumed'},400);
  if(!device.identity_id)return json({status:'pending'},202);
  if(device.identity_id===DENIED){await env.DB.prepare('DELETE FROM devices WHERE id=? AND secret_hash=?').bind(input.device_id,digest).run();return json({error:'Sign-in was cancelled in the browser'},403);}
  const link=await env.DB.prepare('SELECT session_hash FROM device_links WHERE device_id=? AND expires>?').bind(input.device_id,time).first();
  await env.DB.prepare('INSERT OR IGNORE INTO account_members VALUES(?,?,?)').bind(device.identity_id,device.identity_id,device.provider).run();
  const statements=[];
  if(link){
   const parent=await env.DB.prepare('SELECT i.id,i.provider FROM sessions s JOIN identities i ON i.id=s.identity_id WHERE s.token_hash=? AND s.expires>?').bind(link.session_hash,time).first();
   if(!parent)return json({error:'Original sign-in expired; account was not connected'},403);
   await env.DB.prepare('INSERT OR IGNORE INTO account_members VALUES(?,?,?)').bind(parent.id,parent.id,parent.provider).run();
   statements.push(env.DB.prepare('UPDATE account_members SET account_id=(SELECT account_id FROM account_members WHERE identity_id=?) WHERE account_id=(SELECT account_id FROM account_members WHERE identity_id=?) AND EXISTS(SELECT 1 FROM sessions WHERE token_hash=? AND expires>?)').bind(parent.id,device.identity_id,link.session_hash,time));
  }
  const token=random(),tokenHash=await hash(token),expires=time+SESSION_IDLE,label=deviceLabel(input.label);
  // Insertion and deletion share a transaction. Only one poll can obtain a session.
  const sessionIndex=statements.length;let results;
  try{results=await env.DB.batch([...statements,
   env.DB.prepare('INSERT INTO sessions(token_hash,identity_id,expires,created,last_seen,label) SELECT ?,identity_id,?,?,?,? FROM devices WHERE id=? AND secret_hash=? AND expires>? AND identity_id IS NOT NULL AND identity_id<>? AND (? IS NULL OR EXISTS(SELECT 1 FROM sessions WHERE token_hash=? AND expires>?))').bind(tokenHash,expires,time,time,label,input.device_id,digest,time,DENIED,link?.session_hash||null,link?.session_hash||null,time),
   env.DB.prepare('DELETE FROM devices WHERE id=? AND secret_hash=? AND identity_id IS NOT NULL').bind(input.device_id,digest),
   env.DB.prepare('DELETE FROM device_links WHERE device_id=?').bind(input.device_id)
  ]);}catch{return json({error:'Account already has a different identity for this provider. No account was changed.'},409);}
  if(results[sessionIndex].meta.changes!==1)return json({error:'Device request already consumed'},400);
  return json({access_token:token,token_type:'Bearer',expires_at:expires});
 }
 if(path==='/session'&&request.method==='GET'||path==='/logout'&&request.method==='POST'){
  const token=request.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
  if(!token)return json({error:'Sign-in required'},401);
  const digest=await hash(token);
  if(path==='/logout'){await env.DB.prepare('DELETE FROM sessions WHERE token_hash=?').bind(digest).run();return json({signed_out:true});}
  const user=await env.DB.prepare('SELECT i.id,i.provider,i.name,s.expires,s.created,s.last_seen FROM sessions s JOIN identities i ON i.id=s.identity_id WHERE s.token_hash=? AND s.expires>?').bind(digest,time).first();
  if(!user)return json({error:'Session expired or revoked'},401);
  const started=user.created||time;
  if(!user.last_seen||time-user.last_seen>3600||user.expires-time<SESSION_IDLE-86400){
   user.expires=Math.max(user.expires,Math.min(time+SESSION_IDLE,started+SESSION_MAX));
   await env.DB.prepare('UPDATE sessions SET expires=?,last_seen=?,created=COALESCE(created,?) WHERE token_hash=?').bind(user.expires,time,started,digest).run();
  }
  delete user.created;delete user.last_seen;
  await env.DB.prepare('INSERT OR IGNORE INTO account_members VALUES(?,?,?)').bind(user.id,user.id,user.provider).run();
  const account=await env.DB.prepare('SELECT i.id,i.name FROM account_members m JOIN identities i ON i.id=m.account_id WHERE m.identity_id=?').bind(user.id).first();
  const connections=await env.DB.prepare('SELECT i.id,i.provider,i.name FROM identities i JOIN account_members m ON m.identity_id=i.id WHERE m.account_id=? ORDER BY i.created,i.id').bind(account.id).all();
  return json({user,account,connections:connections.results});
 }
 if(path==='/sessions'&&request.method==='GET'||path==='/sessions/revoke'&&request.method==='POST'){
  const token=request.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
  if(!token)return json({error:'Sign-in required'},401);
  const digest=await hash(token);
  const me=await env.DB.prepare('SELECT m.account_id FROM sessions s JOIN account_members m ON m.identity_id=s.identity_id WHERE s.token_hash=? AND s.expires>?').bind(digest,time).first();
  if(!me)return json({error:'Session expired or revoked'},401);
  const scope='FROM sessions s JOIN account_members m ON m.identity_id=s.identity_id JOIN identities i ON i.id=s.identity_id WHERE m.account_id=? AND s.expires>?';
  if(path==='/sessions'){
   const rows=await env.DB.prepare(`SELECT substr(s.token_hash,1,16) AS id,s.token_hash=? AS current,i.provider,s.label,s.created,s.last_seen,s.expires ${scope} ORDER BY s.last_seen DESC`).bind(digest,me.account_id,time).all();
   return json({devices:rows.results.map(r=>({...r,current:Boolean(r.current)})),idle_days:SESSION_IDLE/86400,max_days:SESSION_MAX/86400});
  }
  const input=await body(request);
  if(input.others===true){
   const done=await env.DB.prepare(`DELETE FROM sessions WHERE token_hash IN (SELECT s.token_hash ${scope}) AND token_hash<>?`).bind(me.account_id,time,digest).run();
   return json({revoked:done.meta.changes});
  }
  if(typeof input.id!=='string'||!/^[a-f0-9]{16}$/.test(input.id))return json({error:'Invalid device'},400);
  const done=await env.DB.prepare(`DELETE FROM sessions WHERE token_hash IN (SELECT s.token_hash ${scope} AND substr(s.token_hash,1,16)=?)`).bind(me.account_id,time,input.id).run();
  if(!done.meta.changes)return json({error:'That device is not signed in to your account'},404);
  return json({revoked:done.meta.changes,current:digest.startsWith(input.id)});
 }
 return json({error:'Not found'},404);
}
export default {
 async fetch(request,env){try{return await route(request,env);}catch(error){
  const path=new URL(request.url).pathname,release=path.startsWith('/releases/');
  console.error(JSON.stringify({event:release?'release_request_failed':'auth_request_failed',kind:error.name}));
  if(path.startsWith('/callback/'))return page('Sign-in could not be completed','The provider did not confirm your account. Start sign-in again from Luminaria.',400,clearCookie);
  return release?json({error:'The update service could not read the release. Try again later.'},502):json({error:'Sign-in could not be completed. Please start again.'},400);}},
 async scheduled(controller,env){await env.DB.batch(['devices','device_links','oauth_states','sessions','rate_limits'].map(table=>env.DB.prepare(`DELETE FROM ${table} WHERE expires<?`).bind(now())));}
};
