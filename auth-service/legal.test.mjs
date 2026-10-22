import assert from 'node:assert/strict';
import worker from './src/index.js';
import {legalPage} from './src/legal.js';

const env={get DB(){throw Error('Public legal pages must not touch the account database');}};
for(const path of ['/terms','/privacy','/terms-of-service','/privacy-policy']){
 const response=await worker.fetch(new Request('https://identity.example'+path),env,{});
 assert.equal(response.status,200);
 assert.match(response.headers.get('content-type'),/text\/html/);
 assert.match(response.headers.get('content-security-policy'),/frame-ancestors 'none'/);
 assert.equal(response.headers.get('set-cookie'),null);
 const html=await response.text();
 assert.match(html,/October 21, 2026/);
 assert.match(html,/mailto:dessellebusiness@gmail.com/);
 assert.doesNotMatch(html,/<script|<iframe|<form|johnnycox4431836/i);
 const head=await worker.fetch(new Request('https://identity.example'+path,{method:'HEAD'}),env,{});
 assert.equal(head.status,200);assert.equal(await head.text(),'');
}
assert.equal(legalPage('/not-a-policy'),null);
assert.match(await legalPage('/privacy').text(),/730 days/);
assert.match(await legalPage('/privacy').text(),/does not itself delete/);
console.log('Public terms/privacy pages passed: GET/HEAD, aliases, no auth/DB/cookies, security headers and current data handling.');
