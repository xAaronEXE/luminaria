const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const listeners=new Map(),requests=[];let busy=true,host;
 const context={Map,Set,document:{createElement(){host={html:'',setAttribute(){},set innerHTML(v){this.html=v;this.cancel=[...v.matchAll(/data-cancel-queued="(\d+)"/g)].map(m=>({dataset:{cancelQueued:m[1]}}));this.retry=[...v.matchAll(/data-retry-queued="(\d+)"/g)].map(m=>({dataset:{retryQueued:m[1]}}))},querySelectorAll(selector){return selector.includes('cancel')?this.cancel||[]:this.retry||[]}};return host},querySelector:()=>({prepend(){}})},chat:'a',active:()=>busy,esc:String,icon:()=>'',toast(){},refresh:async()=>{busy=true},api:(url,method,body)=>new Promise((resolve,reject)=>requests.push({url,body,resolve,reject})),window:{addEventListener(type,fn){listeners.set(type,fn)}}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/message-queue.js'),'utf8'),context);
 const flush=()=>new Promise(resolve=>setImmediate(resolve));
 context.window.luminariaQueue.enqueue('a',{text:'first',attachments:[],reasoning:false});assert.equal(requests.length,0);assert(host.html.includes('Queued'));
 context.window.luminariaQueue.enqueue('a',{text:'cancel me',attachments:[],reasoning:false});host.cancel[1].onclick();assert(!host.html.includes('cancel me'));
 context.chat='b';busy=false;listeners.get('studio-state')();assert.equal(requests.length,0);
 context.chat='a';listeners.get('studio-state')();assert.equal(requests.length,1);assert.equal(requests[0].url,'/chats/a/run');
 context.window.luminariaQueue.enqueue('a',{text:'second',attachments:[],reasoning:false});assert.equal(requests.length,1);
 requests[0].resolve({});await flush();assert(!host.html.includes('first'));assert(host.html.includes('second'));
 busy=false;listeners.get('studio-state')();assert.equal(requests.length,2);requests[1].reject(Error('Fixture network failure'));await flush();assert(host.html.includes('Not sent'));assert(host.html.includes('second'));
 host.retry[0].onclick();assert.equal(requests.length,3);requests[2].resolve({});await flush();assert(!host.html.includes('second'));
 busy=true;context.window.luminariaQueue.enqueue('a',{text:'unsent',attachments:[],reasoning:false});let warned=false;listeners.get('beforeunload')({preventDefault(){warned=true}});assert(warned);
 console.log('Message queue passed: active-run queueing, cancellation, chat isolation, one send at a time, retained errors/retry, unload warning.');
})().catch(e=>{console.error(e);process.exitCode=1});
