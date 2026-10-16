// Identity only: provider access tokens are never returned to the desktop or saved.
const providers = {
 github:{authorize:'https://github.com/login/oauth/authorize',token:'https://github.com/login/oauth/access_token',user:'https://api.github.com/user',scope:'read:user',pkce:true},
 google:{authorize:'https://accounts.google.com/o/oauth2/v2/auth',token:'https://oauth2.googleapis.com/token',user:'https://openidconnect.googleapis.com/v1/userinfo',scope:'openid profile',pkce:true},
 discord:{authorize:'https://discord.com/oauth2/authorize',token:'https://discord.com/api/oauth2/token',user:'https://discord.com/api/users/@me',scope:'identify',pkce:false}
};
const now=()=>Math.floor(Date.now()/1000);
const random=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),x=>x.toString(16).padStart(2,'0')).join('');
const bytes=value=>new TextEncoder().encode(value);
async function hash(value){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes(value))),x=>x.toString(16).padStart(2,'0')).join('');}
async function challenge(value){return btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes(value))))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');}
function json(value,status=200){return Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}});}
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
async function providerJson(url,options){
 const response=await fetch(url,{...options,signal:AbortSignal.timeout(15000)});
 if(!response.ok)throw new Error('Provider request failed');
 // Provider bodies are bounded to protect the Worker from unexpected payloads.
 const reader=response.body.getReader();let size=0,chunks=[];
 while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>131072){await reader.cancel();throw new Error('Provider response too large');}chunks.push(value);}
 const result=new Uint8Array(size);let offset=0;for(const chunk of chunks){result.set(chunk,offset);offset+=chunk.length;}
 return JSON.parse(new TextDecoder().decode(result));
}
async function route(request,env){
 const url=new URL(request.url),path=url.pathname,time=now();
 if(path==='/health'&&request.method==='GET')return json({service:'Luminaria identity',providers:Object.keys(providers).map(id=>({id,configured:configured(env,id)}))});
 if(await limited(env,request))return json({error:'Too many requests'},429);
 if(path==='/device/start'&&request.method==='POST'){
  const input=await body(request),provider=input.provider;
  if(!configured(env,provider))return json({error:'Sign-in provider is not configured'},503);
  const id=random(),secret=random();
  await env.DB.prepare('INSERT INTO devices(id,secret_hash,provider,expires) VALUES(?,?,?,?)').bind(id,await hash(secret),provider,time+600).run();
  return json({device_id:id,device_secret:secret,verification_uri:url.origin+'/authorize?device='+id,expires_in:600,interval:5});
 }
 if(path==='/authorize'&&request.method==='GET'){
  const id=url.searchParams.get('device');
  const device=await env.DB.prepare('SELECT * FROM devices WHERE id=? AND expires>? AND identity_id IS NULL').bind(id,time).first();
  if(!device||!configured(env,device.provider))return json({error:'Sign-in request expired or unavailable'},400);
  const provider=providers[device.provider],state=random(),cookie=random(),verifier=random();
  await env.DB.prepare('INSERT INTO oauth_states VALUES(?,?,?,?,?,?)').bind(await hash(state),await hash(cookie),id,device.provider,verifier,time+600).run();
  const target=new URL(provider.authorize);
  target.search=new URLSearchParams({client_id:env[device.provider.toUpperCase()+'_CLIENT_ID'],redirect_uri:url.origin+'/callback/'+device.provider,response_type:'code',scope:provider.scope,state}).toString();
  if(provider.pkce){target.searchParams.set('code_challenge',await challenge(verifier));target.searchParams.set('code_challenge_method','S256');}
  return new Response(null,{status:302,headers:{Location:target.href,'Set-Cookie':`__Host-luminaria_oauth=${cookie}; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=600`,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
 }
 if(path.startsWith('/callback/')&&request.method==='GET'){
  const providerName=path.slice(10),state=url.searchParams.get('state')||'',code=url.searchParams.get('code');
  const cookie=(request.headers.get('Cookie')||'').match(/(?:^|;\s*)__Host-luminaria_oauth=([a-f0-9]{64})(?:;|$)/)?.[1];
  if(!code||!cookie||!configured(env,providerName))return json({error:'Invalid sign-in callback'},400);
  // Atomic consumption prevents parallel callbacks from reusing an authorization.
  const entry=await env.DB.prepare('DELETE FROM oauth_states WHERE state_hash=? AND cookie_hash=? AND provider=? AND expires>? RETURNING *').bind(await hash(state),await hash(cookie),providerName,time).first();
  if(!entry)return json({error:'Sign-in expired or already used'},400);
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
  return new Response('Signed in to Luminaria. You can close this tab and return to the desktop app.',{headers:{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store','Set-Cookie':'__Host-luminaria_oauth=; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=0','Referrer-Policy':'no-referrer'}});
 }
 if(path==='/device/poll'&&request.method==='POST'){
  const input=await body(request);
  if(typeof input.device_secret!=='string'||input.device_secret.length!==64)return json({error:'Invalid device request'},400);
  const digest=await hash(input.device_secret);
  const device=await env.DB.prepare('SELECT * FROM devices WHERE id=? AND secret_hash=? AND expires>?').bind(input.device_id,digest,time).first();
  if(!device)return json({error:'Device request expired or consumed'},400);
  if(!device.identity_id)return json({status:'pending'},202);
  const token=random(),tokenHash=await hash(token),expires=time+7*86400;
  // Insertion and deletion share a transaction. Only one poll can obtain a session.
  const results=await env.DB.batch([
   env.DB.prepare('INSERT INTO sessions SELECT ?,identity_id,? FROM devices WHERE id=? AND secret_hash=? AND expires>? AND identity_id IS NOT NULL').bind(tokenHash,expires,input.device_id,digest,time),
   env.DB.prepare('DELETE FROM devices WHERE id=? AND secret_hash=? AND identity_id IS NOT NULL').bind(input.device_id,digest)
  ]);
  if(results[0].meta.changes!==1)return json({error:'Device request already consumed'},400);
  return json({access_token:token,token_type:'Bearer',expires_at:expires});
 }
 if(path==='/session'&&request.method==='GET'||path==='/logout'&&request.method==='POST'){
  const token=request.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
  if(!token)return json({error:'Sign-in required'},401);
  const digest=await hash(token);
  if(path==='/logout'){await env.DB.prepare('DELETE FROM sessions WHERE token_hash=?').bind(digest).run();return json({signed_out:true});}
  const user=await env.DB.prepare('SELECT i.id,i.provider,i.name,s.expires FROM sessions s JOIN identities i ON i.id=s.identity_id WHERE s.token_hash=? AND s.expires>?').bind(digest,time).first();
  return user?json({user}):json({error:'Session expired or revoked'},401);
 }
 return json({error:'Not found'},404);
}
export default {
 async fetch(request,env){try{return await route(request,env);}catch(error){console.error(JSON.stringify({event:'auth_request_failed',kind:error.name}));return json({error:'Sign-in could not be completed. Please start again.'},400);}},
 async scheduled(controller,env){await env.DB.batch(['devices','oauth_states','sessions','rate_limits'].map(table=>env.DB.prepare(`DELETE FROM ${table} WHERE expires<?`).bind(now())));}
};
