// Lumi landing page: platform-aware download button, the hero's recorded run, the mark's motion and
// gentle reveal motion.
// No cookies, storage, trackers or third-party requests.
(() => {
  "use strict";

  const RELEASE = "https://github.com/adirh3/Lumi/releases/latest";
  const ASSET = `${RELEASE}/download`;

  const TARGETS = {
    windows: { label: "Download for Windows", note: "Windows x64 installer · No .NET install needed", href: `${ASSET}/Lumi-win-Setup.exe` },
    "win-arm": { label: "Download for Windows", note: "Windows ARM64 installer · No .NET install needed", href: `${ASSET}/Lumi-win-arm64-Setup.exe` },
    "mac-arm": { label: "Download for Mac", note: "Apple silicon installer (.pkg) · Intel Mac? Choose Intel under macOS below", href: `${ASSET}/Lumi-osx-arm64-Setup.pkg` },
    "mac-intel": { label: "Download for Mac", note: "Intel installer (.pkg) · Apple silicon Mac? Choose it under macOS below", href: `${ASSET}/Lumi-osx-x64-Setup.pkg` },
    linux: { label: "Download for Linux", note: "x64 AppImage · Portable archive on the release page", href: `${ASSET}/Lumi.AppImage` },
    "linux-arm": { label: "Download for Linux", note: "ARM64 AppImage · Portable archive on the release page", href: `${ASSET}/Lumi-linux-arm64.AppImage` },
    android: { label: "See desktop downloads", note: "Lumi runs on your computer; the Android app pairs with it", href: "#download" },
    ios: { label: "See desktop downloads", note: "Lumi runs on your computer; iPhone uses the mobile web app", href: "#download" },
  };

  // The platform card each build is offered in.
  const PLATFORM = {
    windows: "windows", "win-arm": "windows", "mac-arm": "mac", "mac-intel": "mac",
    linux: "linux", "linux-arm": "linux", android: "phone", ios: "phone",
  };

  function detectOs() {
    const ua = navigator.userAgent || "";
    const platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
    if (/android/i.test(ua)) return "android";
    if (/iphone|ipad|ipod/i.test(ua) || (/mac/i.test(platform) && navigator.maxTouchPoints > 1)) return "ios";
    if (/win/i.test(platform) || /windows/i.test(ua)) return "windows";
    if (/mac/i.test(platform) || /mac os x/i.test(ua)) return "mac";
    if (/cros/i.test(ua)) return null;
    if (/linux|x11/i.test(platform) || /linux/i.test(ua)) return "linux";
    return null;
  }

  // Chromium reports the processor architecture; other browsers don't.
  async function reportedArch() {
    try {
      const data = navigator.userAgentData;
      if (data && data.getHighEntropyValues) {
        const { architecture, bitness } = await data.getHighEntropyValues(["architecture", "bitness"]);
        if (architecture === "arm") return bitness === "32" ? "arm32" : "arm64";
        if (architecture === "x86") return bitness === "32" ? "x86" : "x64";
      }
    } catch {
      /* not reported */
    }
    return null;
  }

  // Browsers can't always tell Apple silicon from Intel. Chromium reports the architecture; elsewhere
  // the GPU name is a fair hint. When unsure, Apple silicon (every current Mac); Intel stays one tap away.
  async function detectMacArch() {
    const arch = await reportedArch();
    if (arch === "arm64" || arch === "arm32") return "mac-arm";
    if (arch === "x64" || arch === "x86") return "mac-intel";
    try {
      const gl = document.createElement("canvas").getContext("webgl");
      const renderer = gl ? String(gl.getParameter(gl.RENDERER) || "") : "";
      if (/intel|amd|radeon/i.test(renderer)) return "mac-intel";
    } catch {
      /* no WebGL: keep the default */
    }
    return "mac-arm";
  }

  // Windows and Linux builds come for x64 and ARM64. Firefox on Linux names the processor in
  // navigator.platform ("Linux aarch64"); when nothing says Arm, x64, with ARM64 one tap away.
  async function detectArmBuild(os) {
    const arch = await reportedArch();
    const named = !arch && /aarch64|arm64/i.test(`${navigator.platform || ""} ${navigator.userAgent || ""}`);
    if (arch !== "arm64" && !named) return os;
    return os === "windows" ? "win-arm" : "linux-arm";
  }

  function applyTarget(key) {
    const target = TARGETS[key];
    if (!target) return;
    document.querySelectorAll("[data-download-primary]").forEach((link) => {
      link.href = target.href;
      const label = link.querySelector("[data-download-label]");
      if (label) label.textContent = target.label;
    });
    document.querySelectorAll("[data-download-note]").forEach((note) => {
      note.textContent = target.note;
    });
    const platform = PLATFORM[key];
    const mark = (element, current) => {
      if (current) element.setAttribute("aria-current", "true");
      else element.removeAttribute("aria-current");
    };
    document.querySelectorAll("[data-platform]").forEach((link) => mark(link, link.dataset.platform === platform));
    document.querySelectorAll("[data-choice]").forEach((choice) => mark(choice, choice.dataset.choice === key));
    document.querySelectorAll("[data-platform-card]").forEach((card) => {
      card.classList.toggle("is-detected", card.dataset.platformCard === platform);
    });
  }

  async function setUpDownloads() {
    const os = detectOs();
    if (!os) return;
    if (os === "mac") {
      applyTarget(await detectMacArch());
      return;
    }
    // x64 right away; the browser's answer about the processor can switch it to ARM64.
    applyTarget(os);
    if (os === "windows" || os === "linux") {
      const build = await detectArmBuild(os);
      if (build !== os) applyTarget(build);
    }
  }

  // The hero's window plays a real recorded run on a loop, over its still first frame. It loads after the
  // page and plays from a blob so looping never depends on the server's range support. It pauses off
  // screen and has a Pause button. When motion isn't welcome (a reduced-motion or Save-Data preference)
  // or the browser blocks autoplay, the still stays and the same button offers to play the run instead.
  const LOOP_SOURCES = {
    1980: [['video/webm; codecs="av01.0.12M.08"', "webm"], ['video/mp4; codecs="avc1.640032"', "mp4"]],
    1320: [['video/webm; codecs="av01.0.08M.08"', "webm"], ['video/mp4; codecs="avc1.640032"', "mp4"]],
  };

  function setUpHeroLoop() {
    const frame = document.querySelector("[data-hero-loop]");
    const toggle = frame && frame.querySelector("[data-loop-toggle]");
    const hero = document.querySelector(".hero");
    if (!frame || !toggle || !window.fetch || !window.URL || !URL.createObjectURL) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const light = window.matchMedia("(prefers-color-scheme: light)");
    const saveData = navigator.connection && navigator.connection.saveData;
    const label = toggle.querySelector("[data-loop-label]");
    let video = null;
    let objectUrl = null;
    let generation = 0;
    let paused = false;
    let visible = true;
    // Set once the visitor presses Play, which overrides a reduced-motion or Save-Data preference.
    let chosen = false;

    const showState = (value) => {
      paused = value;
      toggle.dataset.state = value ? "paused" : "playing";
      label.textContent = value ? "Play" : "Pause";
    };

    // Play over the still; nothing moves or downloads until it's pressed.
    const offer = () => {
      showState(true);
      toggle.hidden = false;
    };

    const sync = () => {
      if (!video) return;
      if (paused || !visible) video.pause();
      else video.play().catch((error) => {
        if (error && error.name === "NotAllowedError") offer();
      });
    };

    const setPaused = (value) => {
      showState(value);
      hero.classList.toggle("is-paused", value);
      sync();
    };

    const teardown = () => {
      if (video) video.remove();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      video = null;
      objectUrl = null;
      frame.classList.remove("is-playing");
    };

    // Sources this browser says it plays, best first. A browser can still fail to decode one, so each is
    // tried in turn; if none plays, the still stays.
    const candidates = () => {
      const theme = light.matches ? "light" : "dark";
      const width = frame.clientWidth * (window.devicePixelRatio || 1) > 1400 ? 1980 : 1320;
      const probe = document.createElement("video");
      return LOOP_SOURCES[width]
        .filter(([type]) => probe.canPlayType(type))
        .map(([, ext]) => `assets/video/hero-${theme}-${width}.${ext}`);
    };

    const attempt = async (url, token) => {
      let blob;
      try {
        const response = await fetch(url);
        if (!response.ok) return false;
        blob = await response.blob();
      } catch {
        return false;
      }
      if (token !== generation) return true;
      teardown();
      objectUrl = URL.createObjectURL(blob);
      video = document.createElement("video");
      video.className = "hero-video";
      video.muted = true;
      video.defaultMuted = true;
      video.loop = true;
      video.playsInline = true;
      video.preload = "auto";
      video.setAttribute("muted", "");
      video.setAttribute("playsinline", "");
      video.setAttribute("aria-hidden", "true");
      video.addEventListener("playing", () => {
        frame.classList.add("is-playing");
        toggle.hidden = false;
      }, { once: true });
      const loaded = new Promise((resolve) => {
        video.addEventListener("loadeddata", () => resolve(true), { once: true });
        video.addEventListener("error", () => resolve(false), { once: true });
      });
      video.src = objectUrl;
      frame.insertBefore(video, toggle);
      sync();
      return loaded;
    };

    const build = async () => {
      const token = ++generation;
      teardown();
      if (!chosen && (reduce.matches || saveData)) {
        offer();
        return;
      }
      for (const url of candidates()) {
        if (await attempt(url, token)) return;
        if (token !== generation) return;
      }
      teardown();
      toggle.hidden = true;
    };

    toggle.addEventListener("click", () => {
      if (!video && paused && !chosen) {
        chosen = true;
        setPaused(false);
        build();
      } else {
        setPaused(!paused);
      }
    });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        sync();
      }).observe(frame);
    }
    reduce.addEventListener("change", build);
    light.addEventListener("change", build);
    if (document.readyState === "complete") build();
    else window.addEventListener("load", build, { once: true });
  }

  // The mark assembles itself on load (CSS); then you and the model circle Lumi once, and again on hover.
  function setUpMark() {
    const mark = document.querySelector("[data-lumi-mark]");
    if (!mark || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const orbit = () => {
      if (mark.classList.contains("is-orbiting")) return;
      mark.classList.add("is-orbiting");
      window.setTimeout(() => mark.classList.remove("is-orbiting"), 2300);
    };
    window.setTimeout(orbit, 2300);
    mark.closest("h1").addEventListener("pointerenter", orbit);
  }

  function setUpReveal() {
    const items = Array.from(document.querySelectorAll(".reveal"));
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!("IntersectionObserver" in window)) return;
    // Whatever is already on screen stays put; only what is below the fold rises in.
    items.forEach((el) => {
      if (el.getBoundingClientRect().top < window.innerHeight) el.classList.add("is-in");
    });
    document.documentElement.classList.add("js");
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: reduce ? "0px" : "0px 0px -8% 0px", threshold: 0.08 });
    items.filter((el) => !el.classList.contains("is-in")).forEach((el) => observer.observe(el));
  }

  function setUpTopbar() {
    const bar = document.querySelector(".topbar");
    if (!bar) return;
    const update = () => bar.classList.toggle("is-scrolled", window.scrollY > 8);
    update();
    window.addEventListener("scroll", update, { passive: true });
  }

  setUpReveal();
  setUpTopbar();
  setUpHeroLoop();
  setUpMark();
  setUpDownloads();
})();
