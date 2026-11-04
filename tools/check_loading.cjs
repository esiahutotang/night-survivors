const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = process.argv[2] || require('node:path').resolve(__dirname, '..');
const html = fs.readFileSync(root + '/docs/index.html', 'utf8');
const template = fs.readFileSync(root + '/default.tmpl', 'utf8');
const code = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
assert.equal(code, template.match(/<script>\s*([\s\S]*?)<\/script>/)[1]);
assert.ok(Buffer.from(html).subarray(0,1024).includes(Buffer.from('<meta charset="UTF-8">')));
assert.ok(!html.includes('\ufffd'));
function setup(fetcher) {
    const elements = {};
    const callbacks = {};
    const document = {
        getElementById(id) { return elements[id] ||= {hidden:false, textContent:'', removeAttribute(name) {delete this[name];}, addEventListener(){}}; },
        addEventListener(type, handler) { callbacks[type] = handler; }
    };
    const window = {fetch:fetcher, addEventListener(){}};
    vm.runInNewContext(code, {window,document,location:{href:'http://localhost/',origin:'http://localhost'},URL,Response,ReadableStream,setTimeout(){}});
    callbacks.DOMContentLoaded();
    return {window,elements};
}
(async () => {
    let controller;
    const source = new ReadableStream({start(c){controller=c;}});
    const first = setup(async () => new Response(source,{headers:{'Content-Length':'4'}}));
    const response = await first.window.fetch('/night-survivors.tar.gz?v=test');
    const reader = response.body.getReader();
    controller.enqueue(new Uint8Array([1,2]));
    assert.deepEqual(Array.from((await reader.read()).value),[1,2]);
    assert.equal(first.elements['loading-progress'].value,2);
    assert.equal(first.elements['loading-progress'].max,4);
    assert.ok(first.elements['loading-detail'].textContent.startsWith('50%'));
    controller.enqueue(new Uint8Array([3,4])); controller.close();
    assert.deepEqual(Array.from((await reader.read()).value),[3,4]);
    await reader.read();
    assert.equal(first.elements['loading-status'].textContent,'解压游戏资源');
    first.window.NightLoader.stage('ready');
    assert.equal(first.elements['loading-action'].hidden,false);
    first.window.NightLoader.complete();
    assert.equal(first.elements['loading-screen'].hidden,true);
    first.window.NightLoader.fail();
    assert.equal(first.elements['loading-screen'].hidden,true);
    const unknown = setup(async () => new Response('abc'));
    assert.equal(await (await unknown.window.fetch('/night-survivors.apk')).text(),'abc');
    assert.ok(!unknown.elements['loading-detail'].textContent.includes('%'));
    const compressed = setup(async () => new Response('abc',{headers:{'Content-Length':'1','Content-Encoding':'gzip'}}));
    await (await compressed.window.fetch('/night-survivors.tar.gz')).text();
    assert.ok(!compressed.elements['loading-detail'].textContent.includes('%'));
    const bad = setup(async () => new Response('missing',{status:404}));
    await assert.rejects(bad.window.fetch('/night-survivors.tar.gz'));
    assert.equal(bad.elements['loading-status'].textContent,'加载未完成');
    assert.equal(bad.elements['loading-action'].textContent,'重新加载');
    const broken = setup(async () => new Response(new ReadableStream({start(c){c.error(new Error('disconnect'));}})));
    await assert.rejects(async () => (await broken.window.fetch('/night-survivors.tar.gz')).text());
    assert.equal(broken.elements['loading-status'].textContent,'加载未完成');
    const untouchedResponse = new Response('runtime');
    const untouched = setup(async () => untouchedResponse);
    assert.equal(await untouched.window.fetch('https://cdn.example/runtime.wasm'),untouchedResponse);
    console.log('PASS: early UTF-8, matching template, real byte progress, unknown/encoded lengths, ready/first frame, HTTP/stream failures, untouched runtime responses');
})().catch(e => {console.error(e);process.exitCode=1;});
