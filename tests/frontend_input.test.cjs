// Run the complete application script with DOM/network doubles to test user events.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../frontend/static/app.js'), 'utf8');

function setup() {
  const nodes = new Map();
  const node = (selector) => {
    if (!nodes.has(selector)) {
      const classes = new Set();
      const element = {
        id: selector.slice(1), name: selector.slice(1).replace('-weight', ''),
        files: [], checked: false, disabled: false, events: {}, dataset: {},
        style: {setProperty() {}}, innerHTML: '', textContent: '',
        classList: {
          add: (name) => classes.add(name), remove: (name) => classes.delete(name),
          contains: (name) => classes.has(name),
          toggle(name, force = !classes.has(name)) { if (force) classes.add(name); else classes.delete(name); },
        },
        addEventListener(name, callback) { this.events[name] = callback; },
        setAttribute() {}, removeAttribute(name) { delete this[name]; },
        getBoundingClientRect: () => ({width: 512, height: 512, left: 0, top: 0}),
        querySelectorAll: () => [], scrollIntoView() {},
      };
      let value = selector.endsWith('-weight') ? '0.5' : '';
      Object.defineProperty(element, 'value', {
        get: () => value,
        set(next) { value = next; if (selector === '#image-input' && next === '') element.files = []; },
      });
      nodes.set(selector, element);
    }
    return nodes.get(selector);
  };
  const requests = [];
  const revoked = [];
  let nextUrl = 0;
  const stats = {gallery_ready: true, by_species: [], configs: [], valid_candidates: 500};
  const context = {
    document: {querySelector: node, querySelectorAll: () => [], body: node('body')},
    window: {__PROFILE__: 'foreground4-hogpca512-v1', __FEATURES__: [
      {key: 'hog'}, {key: 'spatial_hsv'}, {key: 'rootsift_vlad'}, {key: 'gabor'}],
      __INITIAL_STATS__: stats, __WEIGHT_PRESETS__: [], addEventListener() {}, scrollTo() {}},
    location: {hash: '', href: 'http://localhost/'}, history: {replaceState() {}},
    URL: {createObjectURL: () => `blob:${++nextUrl}`, revokeObjectURL: (url) => revoked.push(url)},
    requestAnimationFrame: (callback) => callback(), setTimeout: () => 1, clearTimeout() {},
    FormData: class {constructor() {this.fields = new Map();} append(key, value) {this.fields.set(key, value);}},
    fetch: (url, options) => new Promise((resolve) => requests.push({url, options, resolve})),
  };
  vm.runInNewContext(source, context);
  const choose = (file = {name: 'cat.png', type: 'image/png', size: 100}) => {
    node('#image-input').files = [file];
    node('#image-input').events.change();
  };
  const decode = () => {
    const image = node('#image-preview');
    image.naturalWidth = image.naturalHeight = 512;
    image.onload();
  };
  return {node, choose, decode, requests, revoked, stats};
}

test('invalid replacement clears the previous image and disables search', () => {
  for (const bad of [{name: 'notes.txt', type: 'text/plain', size: 10},
    {name: 'large.png', type: 'image/png', size: 21 * 1024 * 1024}]) {
    const ui = setup();
    ui.choose(); ui.decode();
    assert.equal(ui.node('#search-button').disabled, false);
    ui.choose(bad);
    assert.equal(ui.node('#search-button').disabled, true);
    assert.equal(ui.node('#image-preview-wrap').classList.contains('is-hidden'), true);
    assert.equal(ui.node('#image-input').files.length, 0);
    assert.ok(ui.revoked.includes('blob:1'));
  }
});

test('replacement cannot be searched before decoding and broken images report an error', () => {
  const ui = setup();
  ui.choose(); ui.decode();
  ui.choose({name: 'broken.png', type: 'image/png', size: 50});
  assert.equal(ui.node('#search-button').disabled, true);
  assert.equal(typeof ui.node('#image-preview').onerror, 'function');
  ui.node('#image-preview').onerror();
  assert.equal(ui.node('#image-input').files.length, 0);
  assert.equal(ui.node('#search-button').disabled, true);
  assert.equal(ui.node('#toast').classList.contains('is-error'), true);
});

test('late decode cannot restore an image after clearing it', () => {
  const ui = setup();
  ui.choose();
  const lateDecode = ui.node('#image-preview').onload;
  ui.node('#clear-image').events.click();
  lateDecode();
  assert.equal(ui.node('#image-preview-wrap').classList.contains('is-hidden'), true);
  assert.equal(ui.node('#search-button').disabled, true);
});

test('crop overlay follows contained pixels, including horizontal and vertical letterboxing', () => {
  for (const sample of [
    {width: 512, height: 512, left: 17, top: 0, size: 155},
    {width: 1024, height: 512, left: 0, top: 69, size: 86},
    {width: 256, height: 512, left: 94.5, top: 0, size: 155},
  ]) {
    const ui = setup();
    const preview = ui.node('#image-preview');
    preview.getBoundingClientRect = () => ({width: 344, height: 310, left: 100, top: 80});
    ui.node('#image-preview-wrap').getBoundingClientRect = () => ({width: 344, height: 310, left: 100, top: 80});
    ui.choose();
    preview.naturalWidth = sample.width;
    preview.naturalHeight = sample.height;
    preview.onload();
    ui.node('#use-crop').checked = true;
    ui.node('#crop-size').value = '256';
    ui.node('#crop-size').events.input();
    const frame = ui.node('#crop-frame');
    assert.equal(frame.style.left, `${sample.left}px`);
    assert.equal(frame.style.top, `${sample.top}px`);
    assert.equal(frame.style.width, `${sample.size}px`);
    assert.equal(frame.style.height, `${sample.size}px`);
  }
});

test('history interprets SQLite timestamps as UTC and preserves explicit offsets', async () => {
  const ui = setup();
  const timestamps = ['2026-10-15 11:55:35', '2026-10-15T11:55:35Z', '2026-10-15T18:55:35+07:00'];
  const dashboard = ui.requests.find((request) => request.url.startsWith('/api/dashboard'));
  dashboard.resolve({ok: true, json: async () => ({stats: ui.stats, history: timestamps.map((created_at, index) => ({
    query_id: index + 1, candidate_count: 500, duration_ms: 10, created_at,
  }))})});
  await new Promise(setImmediate);
  const expected = new Intl.DateTimeFormat('vi-VN', {dateStyle: 'short', timeStyle: 'short'})
    .format(new Date('2026-10-15T11:55:35Z'));
  assert.equal(ui.node('#history-list').innerHTML.split(`<small>${expected}</small>`).length - 1, 3);
});

test('weight changes and dashboard refresh cannot submit a second in-flight search', async () => {
  const ui = setup();
  ui.choose(); ui.decode();
  const submit = () => ui.node('#search-form').events.submit({preventDefault() {}});
  const pending = submit();
  assert.equal(ui.node('#search-button').disabled, true);
  ui.node('#spatial_hsv-weight').events.input();
  const dashboard = ui.requests.find((request) => request.url.startsWith('/api/dashboard'));
  dashboard.resolve({ok: true, json: async () => ({stats: ui.stats, history: []})});
  await new Promise(setImmediate);
  assert.equal(ui.node('#search-button').disabled, true);
  await submit();
  const searches = ui.requests.filter((request) => request.url.startsWith('/api/search'));
  assert.equal(searches.length, 1);
  searches[0].resolve({ok: false, json: async () => ({error: {message: 'Test error'}})});
  await pending;
  assert.equal(ui.node('#search-button').disabled, false);
});
