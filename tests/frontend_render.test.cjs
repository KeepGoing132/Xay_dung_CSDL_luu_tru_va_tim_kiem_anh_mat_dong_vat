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
const keys = ['hog', 'spatial_hsv', 'rootsift_vlad', 'gabor'];
const sandbox = {
  $: node, featureKeys: keys, featureLabel: (key) => key,
  escapeHtml: (s) => String(s).replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
  formatNumber: (n) => Number(n).toFixed(1), resultCard: () => '<article></article>',
  renderRegionalHsvChart: () => {}, renderVladChart: () => {}, icon: () => '', window: {},
};
vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('  function renderSearchResults('), source.indexOf('  function renderVladChart(')), sandbox);
vm.runInContext(source.slice(source.indexOf('  function renderStats('), source.indexOf('  function renderHistory(')), sandbox);
const data = {
  query_id: 4, candidate_count: 500,
  timings: {preprocess_ms: 1, extract_ms: 2, rank_ms: 3, processing_ms: 6, segmentation_ms: 0, preview_ms: 4, request_ms: 11},
  items: Array.from({length: 5}, (_, index) => ({
    image_id: index + 1, rank: index + 1, image: 'data:image/png;base64,AA', species_name: 'cat', strongest: 'HOG',
    scores: {...Object.fromEntries(keys.map((key) => [key, .6])), total: .6},
    contributions: Object.fromEntries(keys.map((key) => [key, .1])),
  })),
  query: {rgb: 'rgb', hog: 'hog', spatial_hsv_bins: [],
    dimensions: {hog: 512, spatial_hsv: 512, rootsift_vlad: 4096, gabor: 96},
    extra_vectors: {spatial_hsv: [.2, .8], gabor: [.3, .4]}, rootsift_vlad_clusters: [.5, .5]},
  warnings: ['<bad path>'],
};
sandbox.renderSearchResults(data);
assert.equal((node('#score-table-body').innerHTML.match(/<td>/g) || []).length, 45);
assert.equal((node('#contribution-chart').innerHTML.match(/<span class=/g) || []).length, 20);
assert.equal((node('#extra-feature-previews').innerHTML.match(/<article/g) || []).length, 2);
assert.match(node('#metric-row').innerHTML, /Tổng phía máy chủ/);
assert.match(node('#warning-list').innerHTML, /&lt;bad path&gt;/);
data.query.spatial_prior = 'prior-map';
data.query.preview_notes = {hog: 'HOG hai mức; PCA còn 512 chiều'};
data.query.dimensions = {hog: 512, spatial_hsv: 512, rootsift_vlad: 4096, gabor: 96};
sandbox.renderSearchResults(data);
assert.equal(node('#feature-spatial-prior').src, 'prior-map');
assert.equal(node('#hog-caption').textContent, 'HOG hai mức; PCA còn 512 chiều');
sandbox.renderStats({total_images: 6, approved_gallery: 5, valid_candidates: 4, validation: 1, test: 0, split_totals: {gallery: 5, validation: 1, test: 0}, dataset_splits: {gallery: 5, validation: 1, test: 2},
  searches: 0, acceptance_ready: false, by_species: [], configs: [],
  rejected_candidates: [{image_id: 3, processed_path: '<broken.png>', reason: 'INVALID_IMAGE'}]});
assert.match(node('#stats-grid').innerHTML, /Gallery hợp lệ/);
assert.match(node('#gallery-issues').innerHTML, /Ảnh #3/);
assert.match(node('#gallery-issues').innerHTML, /&lt;broken.png&gt;/);
assert.equal(node('.nav-count').textContent, 4);
console.log('Frontend: four descriptors, two vector previews, timings, health and escaping passed');
