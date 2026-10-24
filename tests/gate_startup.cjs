const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('web/app.js', 'utf8');
const gate = source.slice(source.indexOf('async function gateOpen()'), source.indexOf('async function showGate('));

(async () => {
  for (const scenario of ['locked', 'unavailable', 'unlocked']) {
    const screens = [];
    const context = vm.createContext({
      api: async () => {
        if (scenario === 'unavailable') throw new Error('Connection lost');
        return { unlocked: scenario === 'unlocked', reason: 'Sign in to continue.' };
      },
      showGate: async state => screens.push(state),
    });
    vm.runInContext(gate, context);
    assert.equal(await context.gateOpen(), scenario === 'unlocked');
    assert.equal(screens.length, scenario === 'unlocked' ? 0 : 1);
    if (scenario === 'unavailable') assert.match(screens[0].reason, /Cannot check sign-in/);
  }
  console.log('Startup gate passed: missing session and failed gate request block entry; verified session opens workspace.');
})().catch(error => { console.error(error); process.exitCode = 1; });
