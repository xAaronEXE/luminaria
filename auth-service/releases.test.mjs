import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const installer=new TextEncoder().encode('fixture installer bytes - never executed');
const digest=createHash('sha256').update(installer).digest('hex');
const repo='https://api.github.com/repos/owner/private-app';
let latest={status:200,body:{tag_name:'v0.2.5',name:'Luminaria 0.2.5',body:'Release notes',published_at:'2026-10-16T00:00:00Z',draft:false,
 assets:[{id:1,name:'Luminaria-0.2.5-Setup.exe',size:installer.length},{id:2,name:'SHA256SUMS.txt',size:90}]}};
const intercepted=[];
const script=fileURLToPath(new URL('./src/index.js',import.meta.url));
function worker(bindings){
 return new Miniflare(convertV4MiniflareOptions({modules:[{type:'ESModule',path:script},{type:'ESModule',path:fileURLToPath(new URL('./src/legal.js',import.meta.url))}],compatibilityDate:'2026-10-16',d1Databases:{DB:'test'},bindings,outboundService:async request=>{
  const url=new URL(request.url);intercepted.push(url.href);
  if(url.origin==='https://api.github.com'){
   assert.equal(request.headers.get('Authorization'),'Bearer fixture-release-token');
   if(url.href===repo+'/releases/latest')return Response.json(latest.body,{status:latest.status});
   if(url.href===repo+'/releases/tags/v0.2.5')return Response.json(latest.body);
   if(url.href===repo+'/releases/assets/1')return new Response(null,{status:302,headers:{Location:'https://release-assets.githubusercontent.com/installer?sig=fixture'}});
   if(url.href===repo+'/releases/assets/2')return new Response(digest+'  Luminaria-0.2.5-Setup.exe\n');
  }
  if(url.href==='https://release-assets.githubusercontent.com/installer?sig=fixture'){
   assert.equal(request.headers.get('Authorization'),null);
   return new Response(installer,{headers:{'Content-Length':String(installer.length)}});
  }
  throw new Error('Unexpected outbound request '+url.href);
 }}));
}
async function prepare(mf){
 const db=await mf.getD1Database('DB');
 for(const sql of (await readFile(new URL('./schema.sql',import.meta.url),'utf8')).split(';').filter(x=>x.trim()))await db.prepare(sql).run();
}
const unconfigured=worker({RELEASE_REPO:'owner/private-app'});
const configured=worker({RELEASE_REPO:'owner/private-app',GITHUB_RELEASES_TOKEN:'fixture-release-token'});
const get=(mf,path)=>mf.dispatchFetch('https://identity.test'+path,{redirect:'manual'});
try{
 await prepare(unconfigured);await prepare(configured);
 assert.equal((await get(unconfigured,'/releases/latest')).status,503);
 const manifest=await (await get(configured,'/releases/latest')).json();
 assert.equal(manifest.version,'0.2.5');
 assert.equal(manifest.installer.sha256,digest);
 assert.equal(manifest.installer.url,'https://identity.test/releases/download/v0.2.5/Luminaria-0.2.5-Setup.exe');
 assert.ok(!JSON.stringify(manifest).includes('fixture-release-token'));
 const download=await get(configured,'/releases/download/v0.2.5/Luminaria-0.2.5-Setup.exe');
 assert.equal(download.status,200);
 assert.deepEqual(new Uint8Array(await download.arrayBuffer()),installer);
 assert.equal((await get(configured,'/releases/download/v0.2.5/other.exe')).status,404);
 assert.equal((await get(configured,'/releases/download/v0.2.4/Luminaria-0.2.5-Setup.exe')).status,404);
 latest={status:200,body:{...latest.body,assets:[latest.body.assets[0]]}};
 assert.equal((await get(configured,'/releases/latest')).status,409);
 latest={status:404,body:{message:'Not Found'}};
 assert.equal((await get(configured,'/releases/latest')).status,404);
 console.log('Release channel passed: unconfigured, manifest checksum, token stays server-side, streamed download, name/tag checks, incomplete and missing releases. GitHub responses were mocked; no real release was read.');
}finally{await unconfigured.dispose();await configured.dispose();}
