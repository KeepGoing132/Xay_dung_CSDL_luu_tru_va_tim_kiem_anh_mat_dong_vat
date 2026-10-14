(() => {
  "use strict";

  const body = document.body;
  const toggle = document.querySelector("#motion-toggle");
  const canvas = document.querySelector("#ambient-canvas");
  const halo = document.querySelector("#cursor-halo");
  const bursts = document.querySelector("#motion-bursts");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
  const context = canvas?.getContext("2d");
  const registered = new WeakSet();
  const animations = new Set();
  const pointer = { x: -1000, y: -1000, active: false };
  let userPaused = false;
  let enabled = false;
  let frame = 0;
  let lastTime = 0;
  let width = 0;
  let height = 0;
  let particles = [];
  let hovered = null;

  try { userPaused = localStorage.getItem("faunafind-motion-paused") === "true"; }
  catch { /* Motion still works when browser storage is unavailable. */ }

  function animate(element, keyframes, options) {
    if (!enabled || !element?.animate || document.hidden) return;
    const animation = element.animate(keyframes, options);
    animations.add(animation);
    const release = () => animations.delete(animation);
    animation.addEventListener("finish", release, { once: true });
    animation.addEventListener("cancel", release, { once: true });
  }

  function animateCharts(root) {
    root.querySelectorAll(".contribution-chart, .species-chart, #hsv-chart").forEach((chart) => {
      chart.querySelectorAll(".stack-bar, .hsv-bin, .species-bar i").forEach((bar, index) => {
        bar.style.setProperty("--bar-delay", `${index * 65}ms`);
      });
      chart.classList.add("chart-animate");
    });
  }

  const observer = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-shown");
      animateCharts(entry.target);
      observer.unobserve(entry.target);
    });
  }, { threshold: .06 }) : null;

  function reveal(root = document) {
    const selector = ".page-intro > div, .section-header, .panel, .stat-card, .result-card, .method-flow, .method-card, .method-note, .mask-review-card, .config-item, .metric, .analysis-card, .feature-details, .history-item";
    root.querySelectorAll(selector).forEach((element, index) => {
      if (registered.has(element)) return;
      registered.add(element);
      element.style.setProperty("--reveal-delay", `${Math.min(index % 7, 5) * 60}ms`);
      element.classList.add("motion-reveal");
      if (element.matches(".result-card, .stat-card, .method-card, .mask-review-card")) {
        element.dataset.motionTilt = "";
      }
      if (observer) observer.observe(element);
      else element.classList.add("is-shown");
    });
    animateCharts(root);
  }

  function enter(view) {
    if (!view) return;
    reveal(view);
    animate(view, [
      { opacity: .2, transform: "translateY(22px) scale(.99)" },
      { opacity: 1, transform: "translateY(0) scale(1)" },
    ], { duration: 650, easing: "cubic-bezier(.16,1,.3,1)" });
    const heading = view.querySelector("h1");
    animate(heading, [
      { opacity: .25, transform: "translateY(14px)", filter: "blur(6px)" },
      { opacity: 1, transform: "translateY(0)", filter: "blur(0)" },
    ], { duration: 850, easing: "cubic-bezier(.16,1,.3,1)" });
    animateCharts(view);
  }

  function burst(x, y, amount = 14) {
    if (!enabled || !bursts || document.hidden) return;
    const colors = ["#ffba79", "#9a8aff", "#76b7ff", "#8ae9b7", "#ff8ba6"];
    const count = Math.min(amount, Math.max(0, 60 - bursts.childElementCount));
    for (let index = 0; index < count; index += 1) {
      const spark = document.createElement("i");
      spark.className = "motion-spark";
      spark.style.left = `${x}px`;
      spark.style.top = `${y}px`;
      spark.style.setProperty("--spark-color", colors[index % colors.length]);
      bursts.append(spark);
      const angle = Math.random() * Math.PI * 2;
      const distance = 28 + Math.random() * 85;
      animate(spark, [
        { transform: "translate(0,0) scale(0)", opacity: 0 },
        { transform: `translate(${Math.cos(angle) * distance * .25}px,${Math.sin(angle) * distance * .25}px) scale(1.2)`, opacity: 1, offset: .18 },
        { transform: `translate(${Math.cos(angle) * distance}px,${Math.sin(angle) * distance + 24}px) rotate(150deg) scale(0)`, opacity: 0 },
      ], { duration: 650 + Math.random() * 350, easing: "cubic-bezier(.2,.7,.2,1)" });
      setTimeout(() => spark.remove(), 1100);
    }
  }

  function celebrate(root) {
    reveal(root);
    const card = root.querySelector(".result-card");
    if (!card) return;
    const rect = card.getBoundingClientRect();
    // Wait for scrollIntoView to settle so sparks appear beside the actual card.
    setTimeout(() => {
      if (!card.isConnected) return;
      const current = card.getBoundingClientRect();
      if (current.top >= 0 && current.top < innerHeight) burst(current.left + current.width / 2, current.top + 20, 26);
    }, rect.top > innerHeight ? 650 : 300);
  }

  function resize() {
    if (!context) return;
    width = innerWidth;
    height = innerHeight;
    const ratio = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    const count = width < 620 ? 22 : 54;
    particles = Array.from({ length: count }, (_, index) => ({
      x: Math.random() * width, y: Math.random() * height,
      vx: (Math.random() - .5) * .34, vy: (Math.random() - .5) * .34,
      radius: index % 5 === 0 ? 2.2 : 1.1,
      color: index % 4 === 0 ? "255,170,110" : "152,162,255",
    }));
  }

  function draw(time) {
    frame = 0;
    if (!enabled || document.hidden || !context) return;
    frame = requestAnimationFrame(draw);
    if (time - lastTime < 1000 / 30) return;
    const delta = Math.min((time - lastTime) / 16.67, 3);
    lastTime = time;
    context.clearRect(0, 0, width, height);
    particles.forEach((particle, index) => {
      particle.x = (particle.x + particle.vx * delta + width) % width;
      particle.y = (particle.y + particle.vy * delta + height) % height;
      context.fillStyle = `rgba(${particle.color},.6)`;
      context.beginPath();
      context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
      context.fill();
      for (let next = index + 1; next < particles.length; next += 1) {
        const other = particles[next];
        const distance = Math.hypot(particle.x - other.x, particle.y - other.y);
        if (distance > 120) continue;
        context.strokeStyle = `rgba(134,146,237,${(1 - distance / 120) * .13})`;
        context.beginPath(); context.moveTo(particle.x, particle.y); context.lineTo(other.x, other.y); context.stroke();
      }
      if (pointer.active && Math.hypot(particle.x - pointer.x, particle.y - pointer.y) < 160) {
        context.strokeStyle = "rgba(194,181,255,.18)";
        context.beginPath(); context.moveTo(particle.x, particle.y); context.lineTo(pointer.x, pointer.y); context.stroke();
      }
    });
    if (halo && pointer.active) halo.style.transform = `translate3d(${pointer.x - 230}px,${pointer.y - 230}px,0)`;
  }

  function clearHover() {
    hovered?.classList.remove("is-hovered");
    hovered = null;
  }

  function syncMotion() {
    enabled = !userPaused && !reduced.matches;
    body.classList.toggle("motion-paused", !enabled);
    body.classList.toggle("motion-suspended", document.hidden);
    toggle?.setAttribute("aria-pressed", String(enabled));
    const label = reduced.matches ? "Animation đã tắt theo cài đặt giảm chuyển động của thiết bị" : enabled ? "Tắt animation" : "Bật animation";
    if (toggle) { toggle.setAttribute("aria-label", label); toggle.title = label; }
    cancelAnimationFrame(frame);
    frame = 0;
    if (!enabled) {
      animations.forEach((animation) => animation.cancel());
      bursts?.replaceChildren();
      clearHover();
    } else {
      animations.forEach((animation) => document.hidden ? animation.pause() : animation.play());
    }
    if (enabled && !document.hidden && context) {
      lastTime = performance.now();
      frame = requestAnimationFrame(draw);
    }
  }

  toggle?.addEventListener("click", () => {
    if (reduced.matches) return;
    userPaused = !userPaused;
    try { localStorage.setItem("faunafind-motion-paused", String(userPaused)); }
    catch { /* Preference applies to this page even without persistent storage. */ }
    syncMotion();
  });
  reduced.addEventListener("change", syncMotion);
  document.addEventListener("visibilitychange", syncMotion);
  addEventListener("resize", resize, { passive: true });
  finePointer.addEventListener("change", () => { pointer.active = false; clearHover(); });
  document.addEventListener("pointermove", (event) => {
    if (!enabled || !finePointer.matches || event.pointerType === "touch") return;
    pointer.x = event.clientX; pointer.y = event.clientY; pointer.active = true;
    if (halo) halo.style.opacity = "1";
    const card = event.target.closest("[data-motion-tilt]");
    if (card !== hovered) { clearHover(); hovered = card; card?.classList.add("is-hovered"); }
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    card.style.setProperty("--tilt-x", `${(y - .5) * -8}deg`);
    card.style.setProperty("--tilt-y", `${(x - .5) * 8}deg`);
    card.style.setProperty("--shine-x", `${x * 100}%`);
    card.style.setProperty("--shine-y", `${y * 100}%`);
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => {
    pointer.active = false; if (halo) halo.style.opacity = "0"; clearHover();
  });
  document.addEventListener("click", (event) => {
    const control = event.target.closest("button:not(:disabled), .upload-zone, summary");
    if (!control || control === toggle) return;
    const rect = control.getBoundingClientRect();
    burst(event.detail ? event.clientX : rect.left + rect.width / 2, event.detail ? event.clientY : rect.top + rect.height / 2, 9);
  });

  window.FaunaMotion = { reveal, enter, celebrate, scrollBehavior: () => enabled ? "smooth" : "auto" };
  body.classList.add("motion-ready");
  resize();
  syncMotion();
  reveal();
})();
