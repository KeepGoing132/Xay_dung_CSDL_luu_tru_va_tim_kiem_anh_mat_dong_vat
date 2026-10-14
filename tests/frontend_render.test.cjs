// Exercise the real render functions against a small DOM stub; no browser required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../frontend/static/app.js'), 'utf8');
const nodes = new Map();
const node = (selector) => {
  if (!nodes.has(selector)) nodes.set(selector, {
    innerHTML: '', textContent: '', src: '',
    classList: {add() {}, remove() {}, toggle() {}}, scrollIntoView() {},
  });
  return nodes.get(selector);
};
const keys = ['hsv', 'hog', 'lbp', 'spatial_hsv', 'color_moments', 'glcm'];
const sandbox = {
  $: node, featureKeys: keys, featureLabel: (key) => key,
  profile: 'expanded512-v1', latestResult: null,
  escapeHtml: (s) => String(s).replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
  formatNumber: (n) => Number(n).toFixed(1), resultCard: () => '<article></article>',
  renderHsvChart: () => {}, icon: () => '', window: {},
};
vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('  function renderSearchResults('), source.indexOf('  $("#export-results").addEventListener')), sandbox);
vm.runInContext(source.slice(source.indexOf('  function renderStats('), source.indexOf('  function renderHistory(')), sandbox);
const data = {
  query_id: 4, candidate_count: 500,
  timings: {preprocess_ms: 1, extract_ms: 2, rank_ms: 3, processing_ms: 6, segmentation_ms: 0, preview_ms: 4, request_ms: 11},
  items: Array.from({length: 5}, (_, index) => ({
    image_id: index + 1, rank: index + 1, image: 'data:image/png;base64,AA', species_name: 'cat', strongest: 'GLCM',
    scores: {...Object.fromEntries(keys.map((key) => [key, .6])), total: .6},
    contributions: Object.fromEntries(keys.map((key) => [key, .1])),
  })),
  query: {rgb: 'rgb', hog: 'hog', lbp: 'lbp', hsv_bins: [],
    dimensions: {hsv: 128, hog: 34596, lbp: 160, spatial_hsv: 512, color_moments: 36, glcm: 48},
    extra_vectors: {spatial_hsv: [.2, .8], color_moments: [.3, .4], glcm: [.1, .2]}},
  warnings: ['<bad path>'],
};
sandbox.renderSearchResults(data);
assert.equal((node('#score-table-body').innerHTML.match(/<td>/g) || []).length, 55);
assert.equal((node('#contribution-chart').innerHTML.match(/<span class=/g) || []).length, 30);
assert.equal((node('#extra-feature-previews').innerHTML.match(/<article/g) || []).length, 3);
assert.match(node('#vector-meta').textContent, /35[.,]480/);
assert.match(node('#vector-meta').textContent, /Kích thước vector/);
assert.match(node('#metric-row').innerHTML, /Tổng phía máy chủ/);
assert.match(node('#warning-list').innerHTML, /&lt;bad path&gt;/);
data.query.spatial_prior = 'prior-map';
data.query.preview_notes = {hog: 'Hai mức HOG', lbp: 'LBP ba bán kính'};
data.query.dimensions = {hsv: 128, hog: 9864, lbp: 864, spatial_hsv: 512, color_moments: 36, glcm: 40};
sandbox.renderSearchResults(data);
assert.match(node('#vector-meta').textContent, /11[.,]444/);
assert.equal(node('#feature-spatial-prior').src, 'prior-map');
assert.equal(node('#lbp-caption').textContent, 'LBP ba bán kính');
sandbox.renderStats({total_images: 6, approved_gallery: 5, valid_candidates: 4, validation: 1, test: 0,
  searches: 0, acceptance_ready: false, by_species: [], configs: [],
  rejected_candidates: [{image_id: 3, processed_path: '<broken.png>', reason: 'INVALID_IMAGE'}]});
assert.match(node('#stats-grid').innerHTML, /Gallery hợp lệ/);
assert.match(node('#gallery-issues').innerHTML, /Ảnh #3/);
assert.match(node('#gallery-issues').innerHTML, /&lt;broken.png&gt;/);
assert.equal(node('.nav-count').textContent, 4);
console.log('Frontend: six score columns, six contributions, vector previews, timings, health and escaping passed');
