// Account scope always comes from a live server session, never a client account ID.
const MAX_BLOB=20*1024*1024,QUOTA=128*1024*1024,GLOBAL_QUOTA=512*1024*1024,MAX_RECORD=128*1024;
const kinds=new Set(['chat','file','memory','settings','profile']);
const hex=/^[a-f0-9]{64}$/,key=/^[a-zA-Z0-9_-]{1,128}$/;
const reply=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const digest=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))).map(n=>n.toString(16).padStart(2,'0')).join('');
async function input(request){const reader=request.body?.getReader();if(!reader)throw Error('Body required');let n=0,chunks=[];try{while(true){const {done,value}=await reader.read();if(done)break;n+=value.byteLength;if(n>MAX_RECORD+4096){await reader.cancel();throw Error('Sync record is too large')}chunks.push(value)}}finally{reader.releaseLock()}const all=new Uint8Array(n);let at=0;for(const chunk of chunks){all.set(chunk,at);at+=chunk.length}return JSON.parse(new TextDecoder().decode(all))}
async function spend(env,kind){
 const limits={requests:[25000,1500],read:[50000,2500],write:[5000,250],mutation:[1000,100]},date=new Date().toISOString().slice(0,10),[month,day]=limits[kind];
 for(const [period,cap] of [[date.slice(0,7),month],[date,day]]){
  const row=await env.DB.prepare('INSERT INTO sync_budget(key,used) VALUES(?,1) ON CONFLICT(key) DO UPDATE SET used=used+1 WHERE used<? RETURNING used').bind(kind+':'+period,cap).first();
  if(!row)return false;
 }
 return true;
}
async function sessionAccount(token,env,time){
 return await env.DB.prepare('SELECT m.account_id FROM sessions s JOIN account_members m ON m.identity_id=s.identity_id WHERE s.token_hash=? AND s.expires>? AND (s.created IS NULL OR s.created>?)').bind(await digest(token),time,time-90*86400).first();
}
export async function cloudSync(request,env,accountFor=sessionAccount){
 const path=new URL(request.url).pathname,time=Math.floor(Date.now()/1000);
 const token=request.headers.get('Authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
 if(!token)return reply({error:'Sign-in required'},401);
 const me=await accountFor(token,env,time);
 if(!me)return reply({error:'Session expired or revoked'},401);
 if(env.SYNC_ENABLED!=='true')return reply({error:'Cloud sync is not enabled by the service owner',code:'sync_disabled'},503);
 if(!env.SYNC_BUCKET)return reply({error:'Cloud sync storage is not configured'},503);
 if(!await spend(env,'requests'))return reply({error:'Free-use sync request budget reached. Sync is paused; no paid fallback.',budget_exhausted:true},429);
 const account=me.account_id,prefix='accounts/'+account+'/';
 if(path==='/sync/status'&&request.method==='GET'){
  const usage=await env.DB.prepare('SELECT COALESCE(SUM(size),0) AS bytes,COUNT(*) AS blobs FROM sync_blobs WHERE account_id=?').bind(account).first();
  return reply({available:true,account_id:account,usage,quota:QUOTA,max_blob:MAX_BLOB,global_quota:GLOBAL_QUOTA,budgets:{monthly_requests:25000,monthly_writes:5000,monthly_reads:50000,daily_record_changes:100},paid_fallback:false});
 }
 if(path==='/sync/records'&&request.method==='GET'){
  const after=new URL(request.url).searchParams.get('after')||'';if(after.length>160)return reply({error:'Invalid cursor'},400);
  const result=await env.DB.prepare("SELECT kind,id,version,deleted,updated FROM sync_records WHERE version>0 AND account_id=? AND kind||':'||id>? ORDER BY kind,id LIMIT 200").bind(account,after).all();
  return reply({records:result.results,next:result.results.length===200?result.results.at(-1).kind+':'+result.results.at(-1).id:null});
 }
 const blob=path.match(/^\/sync\/blobs\/([a-f0-9]{64})$/);
 if(blob){const hash=blob[1],objectKey=prefix+'blobs/'+hash;
  if(request.method==='GET'){
   const row=await env.DB.prepare('SELECT size FROM sync_blobs WHERE account_id=? AND hash=? AND ready=1').bind(account,hash).first();if(!row)return reply({error:'File not found'},404);
   if(!await spend(env,'read'))return reply({error:'Free-use download budget reached. Sync is paused.',budget_exhausted:true},429);
   const object=await env.SYNC_BUCKET.get(objectKey);if(!object)return reply({error:'File unavailable'},404);
   return new Response(object.body,{headers:{'Content-Type':'application/octet-stream','Content-Length':String(object.size),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
  }
  if(request.method==='PUT'){
   const size=Number(request.headers.get('Content-Length'));if(request.headers.get('Content-Length')===null||!Number.isSafeInteger(size)||size<0||size>MAX_BLOB)return reply({error:'File exceeds the supported size or has no valid length'},413);
   const known=await env.DB.prepare('SELECT size,ready FROM sync_blobs WHERE account_id=? AND hash=?').bind(account,hash).first();
   if(known?.ready)return known.size===size?reply({hash,size}):reply({error:'File size mismatch'},409);
   await env.DB.prepare('INSERT OR IGNORE INTO sync_blobs(account_id,hash,size,created) SELECT ?,?,?,? WHERE (SELECT COALESCE(SUM(size),0) FROM sync_blobs WHERE account_id=?) + ? <= ? AND (SELECT COALESCE(SUM(size),0) FROM sync_blobs)+?<=?').bind(account,hash,size,time,account,size,QUOTA,size,GLOBAL_QUOTA).run();
   const reservation=await env.DB.prepare('SELECT size FROM sync_blobs WHERE account_id=? AND hash=?').bind(account,hash).first();if(!reservation)return reply({error:'Cloud storage quota reached'},413);if(reservation.size!==size)return reply({error:'File reservation mismatch'},409);
   if(!await spend(env,'write'))return reply({error:'Free-use upload budget reached. Sync is paused.',budget_exhausted:true},429);
   try{const stream=new FixedLengthStream(size),controller=new AbortController();
    const copying=(request.body||new Blob([]).stream()).pipeTo(stream.writable,{signal:controller.signal});
    let object;try{[,object]=await Promise.all([copying,env.SYNC_BUCKET.put(objectKey,stream.readable,{sha256:hash,httpMetadata:{contentType:'application/octet-stream'}})])}catch(error){controller.abort();throw error}
if(object.size!==size){await env.SYNC_BUCKET.delete(objectKey);return reply({error:'File length mismatch'},400)}await env.DB.prepare('UPDATE sync_blobs SET ready=1 WHERE account_id=? AND hash=?').bind(account,hash).run();return reply({hash,size})}
   catch{return reply({error:'File upload failed integrity verification; retry is safe'},400)}
  }
 }
 const record=path.match(/^\/sync\/records\/([a-z]+)\/([a-zA-Z0-9_-]{1,128})$/);
 if(record&&kinds.has(record[1])){const [,kind,id]=record;
  if(request.method==='GET'){const row=await env.DB.prepare('SELECT kind,id,version,data,deleted,updated FROM sync_records WHERE version>0 AND account_id=? AND kind=? AND id=?').bind(account,kind,id).first();return row?reply({...row,data:JSON.parse(row.data)}):reply({error:'Record not found'},404)}
  if(request.method==='PUT'){
   let body;try{body=await input(request)}catch{return reply({error:'Invalid or oversized sync record'},400)}
   if(!Number.isSafeInteger(body.base)||body.base<0||!key.test(body.mutation||'')||typeof body.data!=='object'||body.data===null||Array.isArray(body.data)||typeof body.deleted!=='boolean')return reply({error:'Invalid sync mutation'},400);
   const serialized=JSON.stringify(body.data);if(new TextEncoder().encode(serialized).length>MAX_RECORD)return reply({error:'Sync record is too large'},413);
   // Blob ownership and availability are checked before publishing metadata.
   if(body.data.blob!==undefined){if(!hex.test(body.data.blob))return reply({error:'Invalid file reference'},400);const found=await env.DB.prepare('SELECT ready FROM sync_blobs WHERE account_id=? AND hash=?').bind(account,body.data.blob).first();if(!found?.ready)return reply({error:'Upload this file before publishing it'},409)}
   const fingerprint=await digest(kind+':'+id+':'+JSON.stringify(body)),prior=await env.DB.prepare('SELECT fingerprint,response FROM sync_receipts WHERE account_id=? AND mutation=?').bind(account,body.mutation).first();
   if(prior)return prior.fingerprint===fingerprint?reply(JSON.parse(prior.response)):reply({error:'Mutation identifier was reused with different content'},409);
   if(!await spend(env,'mutation'))return reply({error:'Free-use change budget reached. Remaining changes stay on this PC.',budget_exhausted:true},429);
   const result=await env.DB.batch([
    env.DB.prepare('INSERT OR IGNORE INTO sync_records(account_id,kind,id,updated) SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM sync_records WHERE account_id=?)<2000 AND (SELECT COUNT(*) FROM sync_records)<2000').bind(account,kind,id,time,account),
    env.DB.prepare('UPDATE sync_records SET version=version+1,data=?,deleted=?,mutation=?,updated=? WHERE account_id=? AND kind=? AND id=? AND version=?').bind(serialized,Number(body.deleted),body.mutation,time,account,kind,id,body.base),
    env.DB.prepare("INSERT OR IGNORE INTO sync_receipts(account_id,mutation,fingerprint,response,created) SELECT ?,?,?,json_object('version',version,'mutation',mutation),? FROM sync_records WHERE account_id=? AND kind=? AND id=? AND mutation=?").bind(account,body.mutation,fingerprint,time,account,kind,id,body.mutation)
   ]);
   const receipt=await env.DB.prepare('SELECT fingerprint,response FROM sync_receipts WHERE account_id=? AND mutation=?').bind(account,body.mutation).first();
   if(receipt?.fingerprint===fingerprint)return reply(JSON.parse(receipt.response));
   const present=await env.DB.prepare('SELECT version FROM sync_records WHERE account_id=? AND kind=? AND id=?').bind(account,kind,id).first();
   if(!present)return reply({error:'The sync service record budget is full. No paid fallback.',budget_exhausted:true},429);
   return reply({error:'Another device changed this record. Both copies have been preserved.',conflict:true},409);
  }
 }
 return reply({error:'Not found'},404);
}
