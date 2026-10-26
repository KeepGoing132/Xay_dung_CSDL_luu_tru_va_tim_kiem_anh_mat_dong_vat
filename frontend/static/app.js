(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const profile = window.__PROFILE__;
  const featureInfo = window.__FEATURES__;
  const featureKeys = featureInfo.map((item) => item.key);
  const featureLabel = (key) => featureInfo.find((item) => item.key === key)?.label || key;
  const apiUrl = (url) => `${url}${url.includes("?") ? "&" : "?"}profile=${encodeURIComponent(profile)}`;
  const state = {
    stats: window.__INITIAL_STATS__ || {},
    history: [],
    imageWidth: 0,
    imageHeight: 0,
    previewUrl: null,
    imageReady: false,
    searching: false,
    toastTimer: null,
  };

  $$("svg:not(.svg-sprite)").forEach((svg) => {
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
  });

  const pageNames = {
    search: "Tìm kiếm ảnh",
    dataset: "Sức khỏe dữ liệu",
    processing: "Xử lý ảnh",
    history: "Lịch sử truy vấn",
    method: "Phương pháp",
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatNumber(value, digits = 1) {
    return Number(value || 0).toLocaleString("vi-VN", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function icon(name) {
    return `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
  }

  function showToast(title, message, isError = false) {
    const toast = $("#toast");
    $("#toast-title").textContent = title;
    $("#toast-message").textContent = message;
    toast.classList.toggle("is-error", isError);
    toast.classList.add("is-visible");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 5200);
  }

  $("#toast button").addEventListener("click", () => $("#toast").classList.remove("is-visible"));

  function activateView(name, updateHash = true) {
    if (!pageNames[name]) name = "search";
    $$(".view").forEach((view) => view.classList.toggle("is-active", view.id === `view-${name}`));
    $$(".nav-item").forEach((item) => {
      const active = item.dataset.view === name;
      item.classList.toggle("is-active", active);
      if (active) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
    $("#page-name").textContent = pageNames[name];
    $(".sidebar").classList.remove("is-open");
    $(".mobile-menu").setAttribute("aria-expanded", "false");
    if (updateHash) history.replaceState(null, "", `#${name}`);
    if (name === "dataset" || name === "history") refreshDashboard();
    if (name === "processing") refreshProcessing(true);
    window.FaunaMotion?.enter($(`#view-${name}`));
    window.scrollTo({ top: 0, behavior: window.FaunaMotion?.scrollBehavior() || "auto" });
  }

  $$("[data-view]").forEach((button) => button.addEventListener("click", () => activateView(button.dataset.view)));
  $$("[data-view-link]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
    activateView(link.dataset.viewLink);
  }));
  $(".mobile-menu").addEventListener("click", (event) => {
    const open = $(".sidebar").classList.toggle("is-open");
    event.currentTarget.setAttribute("aria-expanded", String(open));
  });

  const uploadZone = $("#upload-zone");
  const imageInput = $("#image-input");
  const imagePreview = $("#image-preview");
  const cropInputs = [$("#crop-x"), $("#crop-y"), $("#crop-size")];

  ["dragenter", "dragover"].forEach((name) => uploadZone.addEventListener(name, (event) => {
    event.preventDefault();
    uploadZone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((name) => uploadZone.addEventListener(name, (event) => {
    event.preventDefault();
    uploadZone.classList.remove("is-dragging");
  }));
  uploadZone.addEventListener("drop", (event) => {
    const file = event.dataTransfer.files[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    imageInput.files = transfer.files;
    showSelectedImage(file);
  });
  imageInput.addEventListener("change", () => showSelectedImage(imageInput.files[0]));

  function showSelectedImage(file) {
    if (!file) return clearImage();
    resetImagePreview();
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      showToast("Tệp không được hỗ trợ", "Hãy chọn ảnh JPG, PNG hoặc WebP.", true);
      clearImage();
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      showToast("Ảnh quá lớn", "Kích thước tối đa là 20 MB.", true);
      clearImage();
      return;
    }
    const previewUrl = URL.createObjectURL(file);
    state.previewUrl = previewUrl;
    imagePreview.onload = () => {
      if (state.previewUrl !== previewUrl) return;
      state.imageWidth = imagePreview.naturalWidth;
      state.imageHeight = imagePreview.naturalHeight;
      state.imageReady = true;
      setupCropControls();
      $("#image-meta").textContent = `${file.name} · ${state.imageWidth}×${state.imageHeight}`;
      $("#image-preview-wrap").classList.remove("is-hidden");
      uploadZone.classList.add("is-hidden");
      $("#clear-image").classList.remove("is-hidden");
      updateSearchButton();
      requestAnimationFrame(updateCropFrame);
    };
    imagePreview.onerror = () => {
      if (state.previewUrl !== previewUrl) return;
      clearImage();
      showToast("Không đọc được ảnh", "Tệp có thể bị hỏng. Hãy chọn một ảnh JPG, PNG hoặc WebP khác.", true);
    };
    imagePreview.src = previewUrl;
  }

  function resetImagePreview() {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
    state.imageWidth = state.imageHeight = 0;
    state.imageReady = false;
    imagePreview.onload = imagePreview.onerror = null;
    imagePreview.removeAttribute("src");
    $("#image-meta").textContent = "";
    $("#image-preview-wrap").classList.add("is-hidden");
    uploadZone.classList.remove("is-hidden");
    $("#clear-image").classList.add("is-hidden");
    $("#use-crop").checked = false;
    $("#crop-controls").classList.add("is-disabled");
    $("#crop-frame").classList.add("is-hidden");
    updateSearchButton();
  }
  function clearImage() {
    imageInput.value = "";
    resetImagePreview();
  }
  $("#clear-image").addEventListener("click", clearImage);

  function setupCropControls() {
    const maxSize = Math.min(state.imageWidth, state.imageHeight);
    const size = $("#crop-size");
    size.max = String(maxSize);
    size.value = String(maxSize);
    $("#crop-x").value = "0";
    $("#crop-y").value = "0";
    updateCropRanges();
  }

  function updateCropRanges() {
    const size = Number($("#crop-size").value);
    const x = $("#crop-x");
    const y = $("#crop-y");
    x.max = String(Math.max(0, state.imageWidth - size));
    y.max = String(Math.max(0, state.imageHeight - size));
    x.value = String(Math.min(Number(x.value), Number(x.max)));
    y.value = String(Math.min(Number(y.value), Number(y.max)));
    $("#crop-x-output").textContent = x.value;
    $("#crop-y-output").textContent = y.value;
    $("#crop-size-output").textContent = `${size}px`;
    cropInputs.forEach(updateRangeFill);
    updateCropFrame();
  }

  function updateCropFrame() {
    const frame = $("#crop-frame");
    if (!$("#use-crop").checked || !state.imageWidth) {
      frame.classList.add("is-hidden");
      return;
    }
    const imageRect = imagePreview.getBoundingClientRect();
    const wrapRect = $("#image-preview-wrap").getBoundingClientRect();
    // object-fit: contain centers the pixels inside the image element's box.
    const scale = Math.min(imageRect.width / state.imageWidth, imageRect.height / state.imageHeight);
    const insetX = (imageRect.width - state.imageWidth * scale) / 2;
    const insetY = (imageRect.height - state.imageHeight * scale) / 2;
    const x = Number($("#crop-x").value) * scale + imageRect.left - wrapRect.left + insetX;
    const y = Number($("#crop-y").value) * scale + imageRect.top - wrapRect.top + insetY;
    const size = Number($("#crop-size").value) * scale;
    Object.assign(frame.style, { left: `${x}px`, top: `${y}px`, width: `${size}px`, height: `${size}px` });
    frame.classList.remove("is-hidden");
  }

  $("#use-crop").addEventListener("change", (event) => {
    $("#crop-controls").classList.toggle("is-disabled", !event.target.checked);
    updateCropFrame();
  });
  cropInputs.forEach((input) => input.addEventListener("input", updateCropRanges));
  window.addEventListener("resize", updateCropFrame);

  const weightInputs = featureKeys.map((key) => $(`#${key}-weight`));
  function updateRangeFill(input) {
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const fill = ((Number(input.value) - min) / Math.max(max - min, 1)) * 100;
    input.style.setProperty("--fill", `${fill}%`);
  }
  function updateWeights() {
    let total = 0;
    weightInputs.forEach((input) => {
      const value = Number(input.value);
      total += value;
      $(`#${input.id.replace("-weight", "-output")}`).textContent = `${Math.round(value * 100)}%`;
      updateRangeFill(input);
    });
    $("#weight-total").textContent = `Tổng ${Math.round(total * 100)}%`;
    $("#weight-total").style.color = total > 0 ? "" : "var(--danger)";
    updateSearchButton();
  }
  weightInputs.forEach((input) => input.addEventListener("input", () => {
    $("#weight-preset").value = "custom";
    updateWeights();
  }));
  $("#weight-preset").addEventListener("change", (event) => {
    const preset = window.__WEIGHT_PRESETS__[Number(event.target.value)];
    if (!preset) return;
    weightInputs.forEach((input) => { input.value = preset.weights[input.name] ?? 0; });
    updateWeights();
  });
  updateWeights();

  function updateSearchButton() {
    const hasWeight = weightInputs.some((input) => Number(input.value) > 0);
    $("#search-button").disabled = state.searching || !state.imageReady || !imageInput.files.length || !state.stats.gallery_ready || !hasWeight;
  }

  $("#search-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("#search-button");
    if (button.disabled) return;
    const payload = new FormData();
    payload.append("image", imageInput.files[0]);
    weightInputs.forEach((input) => payload.append(input.name, input.value));
    payload.append("use_crop", String($("#use-crop").checked));
    if ($("#use-crop").checked) {
      payload.append("crop_x", $("#crop-x").value);
      payload.append("crop_y", $("#crop-y").value);
      payload.append("crop_size", $("#crop-size").value);
    }

    state.searching = true;
    button.classList.add("is-loading");
    button.disabled = true;
    $(".results-panel").setAttribute("aria-busy", "true");
    document.body.classList.add("is-searching");
    try {
      const response = await fetch(apiUrl("/api/search"), { method: "POST", body: payload });
      const data = await response.json();
      if (!response.ok) throw new Error(`${data.error?.code || "ERROR"}: ${data.error?.message || "Không thể tìm kiếm"}`);
      renderSearchResults(data);
      showToast("Tìm kiếm hoàn tất", `Đã xếp hạng ${data.candidate_count} ứng viên và lưu query #${data.query_id}.`);
      refreshDashboard(false);
    } catch (error) {
      showToast("Không thể tìm kiếm", error.message, true);
    } finally {
      state.searching = false;
      button.classList.remove("is-loading");
      $(".results-panel").setAttribute("aria-busy", "false");
      document.body.classList.remove("is-searching");
      updateSearchButton();
    }
  });

  function resultCard(item) {
    return `<article class="result-card">
      <span class="rank-badge">#${item.rank}</span>
      <img src="${item.image}" alt="Kết quả hạng ${item.rank}: ${escapeHtml(item.species_name)}" loading="lazy">
      <h3 title="${escapeHtml(item.species_name)}">${escapeHtml(item.species_name)}</h3>
      <p><span>ID ${item.image_id}</span><strong>${Number(item.scores?.total ?? item.total_score).toFixed(4)}</strong></p>
    </article>`;
  }

  function renderSearchResults(data) {
    $("#empty-results").classList.add("is-hidden");
    $("#results-content").classList.remove("is-hidden");
    $("#query-id").textContent = `#${data.query_id}`;
    $("#result-summary").textContent = `So sánh trên ${data.candidate_count} ứng viên · điểm chưa làm tròn khi xếp hạng`;
    $("#result-grid").innerHTML = data.items.map(resultCard).join("");

    const timing = data.timings;
    const metrics = [
      ["Ứng viên", data.candidate_count],
      ["Tiền xử lý", `${formatNumber(timing.preprocess_ms)} ms`],
      ["Trích xuất", `${formatNumber(timing.extract_ms)} ms`],
      ["Xếp hạng", `${formatNumber(timing.rank_ms)} ms`],
      ["Xử lý truy hồi", `${formatNumber(timing.processing_ms)} ms`],
      ["Tách nền", `${formatNumber(timing.segmentation_ms)} ms`],
      ["Chuẩn bị phản hồi", `${formatNumber(timing.preview_ms)} ms`],
      ["Tổng phía máy chủ", `${formatNumber(timing.request_ms)} ms`],
    ];
    $("#metric-row").innerHTML = metrics.map(([label, value]) => `<div class="metric"><small>${label}</small><strong>${value}</strong></div>`).join("");

    const maxScore = Math.max(...data.items.map((item) => item.scores.total), .001);
    $("#contribution-chart").innerHTML = data.items.map((item) => {
      const factor = 118 / maxScore;
      return `<div class="bar-column"><div class="stack-bar" style="height:${Math.max(item.scores.total * factor, 4)}px">
        ${featureKeys.map((key) => `<span class="${key}" style="height:${item.contributions[key] * factor}px" title="${escapeHtml(featureLabel(key))} ${item.contributions[key].toFixed(4)}"></span>`).join("")}
      </div><label>#${item.rank} · ${item.scores.total.toFixed(3)}</label></div>`;
    }).join("");

    $("#score-table-body").innerHTML = data.items.map((item) => `<tr>
      <td>#${item.rank}</td><td><img class="table-image" src="${item.image}" alt=""></td><td>${escapeHtml(item.species_name)}</td>
      ${featureKeys.map((key) => `<td>${item.scores[key].toFixed(4)}</td>`).join("")}
      <td>${item.scores.total.toFixed(4)}</td><td>${escapeHtml(featureLabel(item.strongest.toLowerCase()))}</td></tr>`).join("");

    $("#feature-rgb").src = data.query.rgb;
    $("#feature-hog").src = data.query.hog;
    $("#hog-caption").textContent = data.query.preview_notes?.hog || "Hướng gradient · HOG";
    $("#spatial-prior-figure").classList.toggle("is-hidden", !data.query.spatial_prior);
    if (data.query.spatial_prior) $("#feature-spatial-prior").src = data.query.spatial_prior;
    renderRegionalHsvChart(data.query.spatial_hsv_bins);
    renderVladChart(data.query.rootsift_vlad_clusters, data.query.preview_notes?.rootsift_vlad);
    $("#extra-feature-previews").innerHTML = Object.entries(data.query.extra_vectors || {}).map(([key, values]) => {
      const maximum = Math.max(...values, .001);
      return `<article class="extra-feature color-${key}"><strong>${escapeHtml(featureLabel(key))} · ${values.length} chiều</strong><p>Giá trị vector theo thứ tự cấu hình; rê chuột vào cột để xem từng chiều.</p><div class="vector-scroll"><div class="vector-bars">${values.map((value, index) => `<i style="height:${Math.max(value / maximum * 90, 1)}px" title="Chiều ${index}: ${value.toFixed(6)}"></i>`).join("")}</div></div></article>`;
    }).join("");

    $("#warning-list").innerHTML = data.warnings.map((warning) => {
      const text = warning === "candidate_cache_hit"
        ? "Đã dùng cache vector gallery đã xác thực để giảm thời gian tải cơ sở dữ liệu."
        : warning;
      return `<div class="warning-item">${escapeHtml(text)}</div>`;
    }).join("");
    window.FaunaMotion?.celebrate($("#results-content"));
    $("#results-content").scrollIntoView({ behavior: window.FaunaMotion?.scrollBehavior() || "auto", block: "start" });
  }

  function renderVladChart(values, note) {
    const figure = $("#vlad-figure");
    if (!figure || !Array.isArray(values) || !values.length) {
      figure?.classList.add("is-hidden");
      return;
    }
    figure.classList.remove("is-hidden");
    if (note) $("#vlad-caption").textContent = note;
    const max = Math.max(...values, .001);
    $("#vlad-chart").innerHTML = values.map((value, index) => `<span class="vlad-cluster" style="height:${Math.max(value / max * 88, 3)}%" title="Cụm ${index}: ${Number(value).toFixed(4)}"></span>`).join("");
  }

  function renderRegionalHsvChart(values) {
    const colors = ["#e95b45", "#f39a32", "#ded54f", "#68bd68", "#44bfc3", "#4d8de3", "#765ed6", "#cc5fb3"];
    const max = Math.max(...values, .001);
    $("#hsv-chart").innerHTML = values.map((value, index) => `<span class="hsv-bin" style="height:${Math.max(value / max * 88, 3)}%;--bin-color:${colors[index]}" title="Bin ${index}: ${Number(value).toFixed(4)}"></span>`).join("");
  }

  async function refreshDashboard(showFeedback = false) {
    try {
      const response = await fetch(apiUrl("/api/dashboard"));
      if (!response.ok) throw new Error("Không tải được dữ liệu dashboard");
      const data = await response.json();
      state.stats = data.stats;
      state.history = data.history;
      renderStats(data.stats);
      renderHistory(data.history);
      updateSearchButton();
      if (showFeedback) showToast("Đã làm mới", "Thống kê và lịch sử đã được cập nhật.");
    } catch (error) {
      if (showFeedback) showToast("Không thể làm mới", error.message, true);
    }
  }

  function renderStats(stats) {
    const splitTotals = stats.split_totals || {};
    const splits = Object.keys(splitTotals).filter((key) => Number(splitTotals[key] || 0) > 0);
    const splitNote = splits.length ? `Trong CSDL: ${splits.join(" · ")}` : "Chưa nhập ảnh nào vào CSDL";
    const datasetSplits = stats.dataset_splits || {};
    const validationCount = Number(datasetSplits.validation ?? stats.validation ?? 0);
    const validationNote = validationCount > 0
      ? "Chọn cấu hình và trọng số" : "Bộ ảnh hiện hành không tách validation";
    const testCount = Number(datasetSplits.test ?? stats.test ?? 0);
    const testNote = testCount > 0 ? "Tách riêng, không nhập CSDL" : "Chưa có tập test độc lập";
    const entries = [
      ["Tổng ảnh", stats.total_images, splitNote, false],
      ["Gallery hợp lệ", stats.valid_candidates, `${stats.approved_gallery} ảnh được duyệt; đã kiểm tra file và vector`, true],
      ["Validation", validationCount, validationNote, false],
      ["Test", testCount, testNote, false],
      ["Lượt truy vấn", stats.searches, "Đã lưu trong SQLite", false],
    ];
    $("#stats-grid").innerHTML = entries.map(([label, value, note, featured]) => `<article class="stat-card${featured ? " featured" : ""}"><small>${label}</small><strong>${Number(value).toLocaleString("vi-VN")}</strong><span>${note}</span></article>`).join("");
    const badge = $("#health-badge");
    badge.classList.toggle("is-warning", !stats.acceptance_ready);
    badge.innerHTML = stats.acceptance_ready
      ? `${icon("check")}Đủ 500 ứng viên hợp lệ`
      : `${icon("info")}Chưa đủ 500 ứng viên hợp lệ`;

    $("#gallery-issues").innerHTML = (stats.rejected_candidates || []).map((item) => `<div class="warning-item">Ảnh #${item.image_id} · ${escapeHtml(item.processed_path)}: ${escapeHtml(item.reason)}</div>`).join("");
    const maxSpecies = Math.max(...stats.by_species.map((item) => item.total), 1);
    const approvedBySpecies = Object.fromEntries((stats.by_species || []).map((item) => [item.species, item.total]));
    const galleryTotals = stats.dataset_gallery_by_species || {};
    const chartSpecies = Object.keys(galleryTotals).length
      ? Object.keys(galleryTotals).sort().map((name) => ({species: name, total: galleryTotals[name], approved: approvedBySpecies[name] || 0}))
      : (stats.by_species || []).map((item) => ({species: item.species, total: item.total, approved: item.total}));
    $("#species-chart").innerHTML = chartSpecies.map((item) => {
      const outer = Math.max(item.total / maxSpecies * 255, 4);
      const inner = item.total ? Math.max(item.approved / maxSpecies * 255, 0) : 0;
      return `<div class="species-bar" title="${escapeHtml(item.species)}: ${item.total} ảnh gallery, ${item.approved} đã duyệt"><span>${item.total}</span><i style="height:${outer}px"><b style="height:${inner}px"></b></i><small>${escapeHtml(item.species)}</small></div>`;
    }).join("") || `<p class="vector-meta">Chưa có ảnh gallery trong manifest nguồn.</p>`;
    $("#config-list").innerHTML = stats.configs.map((item) => {
      const type = String(item.feature_type).toLowerCase();
      return `<article class="config-item color-${type}"><span>${escapeHtml(item.feature_type)}</span><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.preprocess_version)}</small></div><code>${Number(item.dimension).toLocaleString("vi-VN")}D</code></article>`;
    }).join("");
    const navCount = $(".nav-count");
    if (navCount) navCount.textContent = stats.valid_candidates;
    window.FaunaMotion?.reveal($("#view-dataset"));
  }

  function renderHistory(rows) {
    $("#history-count").textContent = `${rows.length} bản ghi`;
    $("#history-list").innerHTML = rows.length ? rows.map((row) => {
      // SQLite CURRENT_TIMESTAMP is UTC but has no timezone suffix.
      const timestamp = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(row.created_at)
        ? `${row.created_at.replace(" ", "T")}Z` : row.created_at;
      const date = new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(timestamp));
      return `<button class="history-item" type="button" data-query-id="${row.query_id}"><span class="history-icon">#${row.query_id}</span><span><strong>${row.candidate_count} ứng viên</strong><small>${date}</small></span><small>${formatNumber(row.duration_ms)} ms</small></button>`;
    }).join("") : `<div class="history-placeholder"><h2>Chưa có truy vấn</h2><p>Thực hiện một lần tìm kiếm để bắt đầu.</p></div>`;
    $$(".history-item", $("#history-list")).forEach((button) => button.addEventListener("click", () => loadHistoryDetail(button.dataset.queryId, button)));
    window.FaunaMotion?.reveal($("#history-list"));
  }

  async function loadHistoryDetail(queryId, button) {
    $$(".history-item").forEach((item) => item.classList.toggle("is-active", item === button));
    const detail = $("#history-detail");
    detail.setAttribute("aria-busy", "true");
    detail.innerHTML = `<div class="history-placeholder"><div class="button-loading" style="display:flex"><i></i>Đang tải query #${queryId}…</div></div>`;
    try {
      const response = await fetch(apiUrl(`/api/history/${queryId}`));
      const data = await response.json();
      if (!response.ok) throw new Error(data.error?.message || "Không tải được truy vấn");
      detail.innerHTML = `<div class="results-heading"><div><p class="eyebrow"><span></span>Saved result</p><h2>Truy vấn #${queryId}</h2><p>Top 5 đã lưu nguyên vẹn trong SQLite</p></div></div><div class="history-results">${data.items.map(resultCard).join("")}</div>`;
      window.FaunaMotion?.reveal(detail);
    } catch (error) {
      detail.innerHTML = `<div class="history-placeholder"><h2>Không thể tải</h2><p>${escapeHtml(error.message)}</p></div>`;
    } finally {
      detail.setAttribute("aria-busy", "false");
    }
  }

  $("#refresh-history").addEventListener("click", () => refreshDashboard(true));
  let reviewOffset = 0;
  let processingBusy = false;
  let lastReviewSignature = "";
  let processingPoll = null;
  const reviewPageSize = 24;

  async function processingRequest(url, body) {
    const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || "Không thực hiện được tác vụ");
    return data;
  }

  function renderProcessingNotice(job) {
    const variants = {
      cancelled: { tone: "paused", title: "Tác vụ đã dừng", label: "Có thể tiếp tục", icon: "pause" },
      interrupted: { tone: "warning", title: "Tác vụ bị gián đoạn", label: "Chạy lại để tiếp tục", icon: "info" },
    };
    const variant = variants[job?.status] || { tone: "error", title: "Không thể hoàn tất tác vụ", label: "Cần kiểm tra", icon: "alert" };
    const notice = $("#processing-error");
    notice.dataset.state = variant.tone;
    $("#processing-notice-title").textContent = variant.title;
    $("#processing-notice-label").textContent = variant.label;
    $("#processing-notice-icon use").setAttribute("href", `#i-${variant.icon}`);
    let message = job?.error || "";
    if (job?.status === "cancelled" && message === "Đã dừng; ảnh và vector thành công được giữ để tiếp tục") {
      message = "Ảnh và vector đã xử lý thành công được giữ lại. Chạy lại tác vụ để tiếp tục từ phần đã hoàn thành.";
    } else if (job?.status === "interrupted" && message === "Server restarted; run again to resume validated images") {
      message = "Server đã khởi động lại. Chạy lại tác vụ để tiếp tục với các ảnh đã được kiểm tra.";
    }
    $("#processing-notice-message").textContent = message;
    notice.classList.toggle("is-hidden", !message);
  }

  function renderProcessingStatus(data) {
    const count = (value) => Number(value || 0).toLocaleString("vi-VN");
    $("#processing-cutout-count").textContent = count(data.cutouts);
    $("#processing-source-count").textContent = `Trên ${count(data.total)} ảnh nguồn`;
    $("#processing-imported-count").textContent = count(data.imported);
    $("#processing-approved-count").textContent = count(data.approved_gallery);
    $("#processing-output-folder").textContent = data.output_folder || "—";
    $("#processing-database").textContent = data.database || "—";

    const job = data.job;
    const statuses = { running: "Đang chạy", completed: "Hoàn tất", failed: "Có lỗi", cancelled: "Đã dừng", interrupted: "Bị gián đoạn" };
    const phases = { starting: "Đang chuẩn bị xử lý ảnh", remove_background: "Tách nền ảnh nguồn", extract_features: "Trích đặc trưng và lưu vào cơ sở dữ liệu" };
    $("#processing-job-status").textContent = job ? (statuses[job.status] || job.status) : "Chưa có tác vụ";
    $("#processing-job-status").dataset.state = job?.status || "idle";
    $("#processing-job").textContent = job ? (phases[job.phase] || "Xử lý ảnh")
      : "Chọn một thao tác ở trên để bắt đầu. Ảnh đã xử lý được giữ lại.";
    const total = Math.max(Number(job?.total) || 0, 0);
    const completed = Math.min(Math.max(Number(job?.completed) || 0, 0), total);
    $("#processing-progress-block").classList.toggle("is-hidden", !job || (!total && job.status !== "running"));
    const progress = $("#processing-progress");
    progress.max = Math.max(total, 1);
    if (total > 0) progress.value = completed;
    else progress.removeAttribute("value");
    $("#processing-progress-count").textContent = total ? `${count(completed)} / ${count(total)} ảnh` : "Đang chuẩn bị…";
    $("#processing-progress-percent").textContent = total ? `${Math.round(completed / total * 100)}%` : "";
    $("#processing-source").textContent = job?.source || "";
    $("#processing-source").title = job?.source || "";
    $("#processing-source").classList.toggle("is-hidden", !job?.source);
  }

  async function refreshProcessing(force = false) {
    clearTimeout(processingPoll);
    try {
      const response = await fetch(`/api/processing?offset=${reviewOffset}&limit=${reviewPageSize}&ready_only=${$("#review-ready-only").checked}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error?.message || "Không đọc được trạng thái");
      processingBusy = data.busy;
      $(".processing-panel").classList.toggle("is-processing", data.busy);
      renderProcessingStatus(data);
      $$("[data-processing-action]").forEach((button) => {
        button.disabled = data.busy || (button.dataset.processingAction === "extract_features" && !data.cutouts);
      });
      $("#processing-cancel").disabled = !data.busy;
      $("#processing-scope").disabled = data.busy;
      $("#review-approve").disabled = data.busy;
      $("#review-reject").disabled = data.busy;
      const job = data.job;
      renderProcessingNotice(job);
      const signature = JSON.stringify(data.items);
      if (force || signature !== lastReviewSignature) {
        lastReviewSignature = signature;
        $("#review-select-page").checked = false;
        const statusLabel = { approved: "Đã duyệt", pending: "Cần duyệt mask", rejected: "Đã loại", not_imported: "Chưa lưu đặc trưng" };
        $("#mask-review-grid").innerHTML = data.items.map((item) => `<article class="mask-review-card">
          <div class="mask-pair"><figure><img src="${item.original_url}" alt="Ảnh nguồn ${escapeHtml(item.species)}" loading="lazy"><figcaption>Ảnh nguồn</figcaption></figure>
          <figure class="transparent-preview">${item.mask_url ? `<img src="${item.mask_url}" alt="Mask tách nền" loading="lazy">` : `<div class="mask-placeholder">Chưa tách nền</div>`}<figcaption>PNG tách nền</figcaption></figure></div>
          <label><input class="mask-review-checkbox" type="checkbox" value="${item.source_id}" ${item.image_id ? "" : "disabled"}> ${escapeHtml(item.species)} · ${escapeHtml(item.split)}</label>
          <p>${statusLabel[item.quality_status] || item.quality_status}</p><small>${escapeHtml(item.source_path)}</small></article>`).join("") || "<p>Chưa có ảnh tách nền. Chạy bước 1 hoặc bỏ chọn bộ lọc để xem ảnh nguồn.</p>";
        window.FaunaMotion?.reveal($("#mask-review-grid"));
      }
      $("#review-page").textContent = data.page_total ? `Trang ${Math.floor(reviewOffset / reviewPageSize) + 1}/${Math.ceil(data.page_total / reviewPageSize)}` : "0 ảnh";
      $("#review-prev").disabled = reviewOffset === 0;
      $("#review-next").disabled = reviewOffset + reviewPageSize >= data.page_total;
      if (data.busy) processingPoll = setTimeout(() => refreshProcessing(), 1800);
      if (job?.status === "completed") refreshDashboard(false);
    } catch (error) {
      $("#processing-job").textContent = error.message;
      $("#processing-job-status").textContent = "Không tải được trạng thái";
      $("#processing-job-status").dataset.state = "failed";
      if (processingBusy) processingPoll = setTimeout(() => refreshProcessing(), 3000);
    }
  }

  $$("[data-processing-action]").forEach((button) => button.addEventListener("click", async () => {
    try {
      $$("[data-processing-action]").forEach((item) => item.disabled = true);
      const value = $("#processing-scope").value;
      await processingRequest("/api/processing", { action: button.dataset.processingAction, limit: value ? Number(value) : null });
      await refreshProcessing(true);
    } catch (error) { showToast("Không chạy được", error.message, true); refreshProcessing(); }
  }));
  $("#processing-cancel").addEventListener("click", async () => {
    try { await processingRequest("/api/processing/cancel", {}); refreshProcessing(); }
    catch (error) { showToast("Không dừng được", error.message, true); }
  });
  $("#review-select-page").addEventListener("change", (event) => {
    $$(".mask-review-checkbox:not(:disabled)").forEach((checkbox) => checkbox.checked = event.target.checked);
  });
  async function reviewMasks(status) {
    const ids = $$(".mask-review-checkbox:checked").map((checkbox) => Number(checkbox.value));
    if (!ids.length) return showToast("Chọn ảnh trước", "Xem mask rồi đánh dấu các ảnh muốn dùng hoặc loại.");
    try {
      await processingRequest("/api/processing/review", { source_ids: ids, quality_status: status });
      await refreshProcessing(true); refreshDashboard(false);
    } catch (error) { showToast("Không cập nhật được", error.message, true); }
  }
  $("#review-approve").addEventListener("click", () => reviewMasks("approved"));
  $("#review-reject").addEventListener("click", () => reviewMasks("rejected"));
  $("#review-prev").addEventListener("click", () => { reviewOffset = Math.max(0, reviewOffset - reviewPageSize); refreshProcessing(true); });
  $("#review-ready-only").addEventListener("change", () => { reviewOffset = 0; refreshProcessing(true); });
  $("#review-next").addEventListener("click", () => { reviewOffset += reviewPageSize; refreshProcessing(true); });
  const initialView = location.hash.slice(1);
  activateView(pageNames[initialView] ? initialView : "search", false);
  renderStats(state.stats);
  refreshDashboard(false);
})();
