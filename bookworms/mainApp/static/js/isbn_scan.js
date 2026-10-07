/**
 * Desktop ISBN camera scanner — camera only.
 * Decode runs ONLY in a same-origin Web Worker (vendored ZXing).
 * No continuous BarcodeDetector (can hang Chrome on live <video>).
 * Close always tears down tracks + Bootstrap backdrop.
 */
(function () {
    "use strict";

    var TICK_MS = 450;
    var MAX_W = 640;
    var WORKER_SRC = "/library/isbn-scan-assets/isbn_scan_worker.js?v=13";

    /** Soft-insert shelf card HTML returned by My Library AJAX add. */
    function insertLibraryShelfHtml(html) {
        if (!html) return false;
        var grid = document.getElementById("librarySelectGrid");
        if (!grid) return false;
        var empty = document.getElementById("libraryShelfEmpty");
        if (empty) empty.remove();
        var header = document.getElementById("libraryShelfHeader");
        if (header) header.hidden = false;
        var wrap = document.createElement("div");
        wrap.innerHTML = String(html).trim();
        var nodes = Array.prototype.slice.call(wrap.childNodes);
        var firstCard = grid.querySelector(".library-select-card");
        nodes.forEach(function (node) {
            if (node.nodeType !== 1) return;
            if (firstCard) {
                grid.insertBefore(node, firstCard);
            } else {
                grid.appendChild(node);
            }
        });
        return true;
    }
    window.insertLibraryShelfHtml = insertLibraryShelfHtml;

    function normalizeIsbn(raw) {
        var digits = String(raw || "")
            .replace(/[^0-9Xx]/g, "")
            .toUpperCase();
        if (digits.length === 13 && /^\d{13}$/.test(digits)) return digits;
        if (digits.length === 10 && /^[\dX]{10}$/.test(digits)) return digits;
        if (digits.length > 13) {
            var m = digits.match(/97[89]\d{10}/);
            if (m) return m[0];
            var tail = digits.slice(-13);
            if (/^\d{13}$/.test(tail)) return tail;
        }
        return null;
    }

    function sleep(ms) {
        return new Promise(function (r) {
            setTimeout(r, ms);
        });
    }

    /** Classic mechanical shutter click (Web Audio — no asset file). */
    function playCameraClick() {
        try {
            var AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            if (!playCameraClick._ctx) {
                playCameraClick._ctx = new AC();
            }
            var ctx = playCameraClick._ctx;
            if (ctx.state === "suspended") {
                ctx.resume();
            }
            var t0 = ctx.currentTime;
            var n = Math.max(1, Math.floor(ctx.sampleRate * 0.045));
            var buf = ctx.createBuffer(1, n, ctx.sampleRate);
            var ch = buf.getChannelData(0);
            for (var i = 0; i < n; i++) {
                ch[i] = (Math.random() * 2 - 1) * Math.exp(-i / (n * 0.07));
            }
            var src = ctx.createBufferSource();
            src.buffer = buf;
            var bp = ctx.createBiquadFilter();
            bp.type = "bandpass";
            bp.frequency.value = 2200;
            bp.Q.value = 0.9;
            var g = ctx.createGain();
            g.gain.setValueAtTime(0.85, t0);
            g.gain.exponentialRampToValueAtTime(0.01, t0 + 0.07);
            src.connect(bp);
            bp.connect(g);
            g.connect(ctx.destination);
            src.start(t0);
            src.stop(t0 + 0.08);

            var osc = ctx.createOscillator();
            var g2 = ctx.createGain();
            osc.type = "square";
            osc.frequency.setValueAtTime(200, t0);
            osc.frequency.exponentialRampToValueAtTime(55, t0 + 0.035);
            g2.gain.setValueAtTime(0.18, t0);
            g2.gain.exponentialRampToValueAtTime(0.001, t0 + 0.045);
            osc.connect(g2);
            g2.connect(ctx.destination);
            osc.start(t0);
            osc.stop(t0 + 0.05);
        } catch (e) {
            console.warn("[isbn-scan] shutter sound", e);
        }
    }

    function forceModalCleanup(modalEl) {
        try {
            modalEl.classList.remove("show");
            modalEl.style.display = "none";
            modalEl.setAttribute("aria-hidden", "true");
            modalEl.removeAttribute("aria-modal");
        } catch (e) {}
        document.querySelectorAll(".modal-backdrop").forEach(function (el) {
            el.remove();
        });
        document.body.classList.remove("modal-open");
        document.body.style.removeProperty("overflow");
        document.body.style.removeProperty("padding-right");
    }

    function initIsbnScan() {
        var openBtns = Array.prototype.slice.call(
            document.querySelectorAll(".js-isbn-scan-open, #isbnScanOpen")
        );
        var modalEl = document.getElementById("isbnScanModal");
        var statusEl = document.getElementById("isbnScanStatus");
        var video = document.getElementById("isbnScanVideo");
        var closeBtn = document.getElementById("isbnScanClose");
        var isbnInput =
            document.querySelector("#addIsbnForm input[name='isbn']") ||
            document.getElementById("id_isbn");
        var form =
            document.getElementById("addIsbnForm") ||
            (isbnInput && isbnInput.closest("form"));

        if (!openBtns.length || !modalEl || !video || !isbnInput) {
            console.warn("[isbn-scan] missing DOM nodes, abort init");
            return;
        }

        // Strip any leftover file-upload UI from older templates
        var legacyFile = document.getElementById("isbnScanFile");
        if (legacyFile) {
            var lab = modalEl.querySelector('label[for="isbnScanFile"]');
            if (lab) lab.remove();
            legacyFile.remove();
        }

        var locked = false;
        var running = false;
        var starting = false;
        var bsModal = null;
        var stream = null;
        var worker = null;
        var workerReady = false;
        var workerBusy = false;
        var workerReqId = 0;
        var loopGen = 0;
        var canvas = document.createElement("canvas");
        var ctx = canvas.getContext("2d", { willReadFrequently: true });
        var tickCount = 0;

        function setStatus(msg) {
            if (statusEl) statusEl.textContent = msg || "";
            if (msg) console.log("[isbn-scan]", msg);
        }

        function killWorker() {
            if (!worker) return;
            try {
                worker.onmessage = null;
                worker.onerror = null;
                worker.terminate();
            } catch (e) {}
            worker = null;
            workerReady = false;
            workerBusy = false;
        }

        function ensureWorker() {
            if (worker) return worker;
            try {
                worker = new Worker(WORKER_SRC);
            } catch (err) {
                setStatus("Worker error: " + (err.message || err));
                worker = null;
                return null;
            }
            workerReady = true;
            worker.onerror = function (ev) {
                console.error("[isbn-scan] worker onerror", ev);
                setStatus(
                    "Помилка worker: " +
                        (ev && ev.message ? ev.message : "див. консоль")
                );
                workerBusy = false;
            };
            return worker;
        }

        function stopTracks() {
            try {
                if (stream && stream.getTracks) {
                    stream.getTracks().forEach(function (t) {
                        try {
                            t.stop();
                        } catch (e) {}
                    });
                }
            } catch (e2) {}
            stream = null;
            try {
                var vs = video.srcObject;
                if (vs && vs.getTracks) {
                    vs.getTracks().forEach(function (t) {
                        try {
                            t.stop();
                        } catch (e3) {}
                    });
                }
            } catch (e4) {}
            video.srcObject = null;
            try {
                video.pause();
            } catch (e5) {}
        }

        function hardStop() {
            locked = true;
            running = false;
            starting = false;
            loopGen += 1;
            stopTracks();
            killWorker();
        }

        function dismissModal() {
            hardStop();
            if (bsModal) {
                try {
                    bsModal.hide();
                } catch (e) {}
            }
            // If Bootstrap hide is wedged, force-clean backdrop
            setTimeout(function () {
                if (document.body.classList.contains("modal-open")) {
                    forceModalCleanup(modalEl);
                }
                locked = false;
                starting = false;
                running = false;
            }, 200);
        }

        function finishWithIsbn(isbn) {
            if (locked) return;
            locked = true;
            running = false;
            loopGen += 1;
            playCameraClick();
            setStatus("Знайдено: " + isbn);
            isbnInput.value = isbn;
            isbnInput.dispatchEvent(new Event("input", { bubbles: true }));
            stopTracks();
            killWorker();
            if (bsModal) {
                try {
                    bsModal.hide();
                } catch (e) {}
            }
            setTimeout(function () {
                forceModalCleanup(modalEl);
                try {
                    if (form && typeof form.requestSubmit === "function") {
                        form.requestSubmit();
                    } else if (form) {
                        form.submit();
                    }
                } catch (e2) {}
            }, 80);
        }

        function acceptText(text) {
            if (locked || !text) return false;
            var isbn = normalizeIsbn(text);
            if (!isbn) {
                setStatus(
                    "Код «" +
                        String(text).slice(0, 24) +
                        "» не ISBN (978…/979…)"
                );
                return false;
            }
            finishWithIsbn(isbn);
            return true;
        }

        function openStream() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                return Promise.reject(
                    new Error("getUserMedia недоступний (потрібен HTTPS)")
                );
            }
            var attempts = [
                {
                    audio: false,
                    video: {
                        facingMode: { ideal: "environment" },
                        width: { ideal: 1280 },
                        height: { ideal: 720 },
                    },
                },
                {
                    audio: false,
                    video: { width: { ideal: 1280 }, height: { ideal: 720 } },
                },
                { audio: false, video: true },
            ];
            function tryAt(i) {
                if (i >= attempts.length) {
                    return Promise.reject(new Error("Немає доступу до камери"));
                }
                return navigator.mediaDevices
                    .getUserMedia(attempts[i])
                    .catch(function () {
                        return tryAt(i + 1);
                    });
            }
            return tryAt(0);
        }

        /** Full frame, downscaled — better than center-band alone for desktop webcams. */
        function grabFrame() {
            var vw = video.videoWidth;
            var vh = video.videoHeight;
            if (!vw || !vh) return null;
            var scale = vw > MAX_W ? MAX_W / vw : 1;
            var dw = Math.max(1, Math.floor(vw * scale));
            var dh = Math.max(1, Math.floor(vh * scale));
            if (canvas.width !== dw) canvas.width = dw;
            if (canvas.height !== dh) canvas.height = dh;
            ctx.drawImage(video, 0, 0, dw, dh);
            var imageData = ctx.getImageData(0, 0, dw, dh);
            return {
                width: dw,
                height: dh,
                buffer: imageData.data.buffer.slice(0),
            };
        }

        function decodeInWorker(frame) {
            return new Promise(function (resolve) {
                var w = ensureWorker();
                if (!w) {
                    resolve(null);
                    return;
                }
                if (workerBusy) {
                    resolve(null);
                    return;
                }
                workerBusy = true;
                var id = ++workerReqId;
                var timer = setTimeout(function () {
                    workerBusy = false;
                    resolve(null);
                }, 2500);
                function onMsg(ev) {
                    if (!ev.data || ev.data.id !== id) return;
                    clearTimeout(timer);
                    w.removeEventListener("message", onMsg);
                    workerBusy = false;
                    if (ev.data.error) {
                        console.warn("[isbn-scan] decode err", ev.data.error);
                    }
                    resolve(ev.data.text || null);
                }
                w.addEventListener("message", onMsg);
                try {
                    w.postMessage(
                        {
                            id: id,
                            width: frame.width,
                            height: frame.height,
                            buffer: frame.buffer,
                        },
                        [frame.buffer]
                    );
                } catch (e) {
                    clearTimeout(timer);
                    w.removeEventListener("message", onMsg);
                    workerBusy = false;
                    resolve(null);
                }
            });
        }

        async function scanLoop(gen) {
            running = true;
            setStatus("Сканування… наведіть штрихкод ISBN у кадр");
            while (!locked && running && gen === loopGen) {
                try {
                    if (
                        video.readyState >= 2 &&
                        video.videoWidth &&
                        !video.paused
                    ) {
                        var frame = grabFrame();
                        if (frame) {
                            tickCount += 1;
                            var text = await decodeInWorker(frame);
                            if (locked || gen !== loopGen) break;
                            if (text && acceptText(text)) return;
                            if (tickCount % 8 === 0) {
                                setStatus(
                                    "Шукаю ISBN… тримайте штрихкод рівно в кадрі (" +
                                        tickCount +
                                        ")"
                                );
                            }
                        }
                    }
                } catch (eLoop) {
                    console.warn("[isbn-scan] tick", eLoop);
                }
                await sleep(TICK_MS);
            }
            running = false;
        }

        function startLive() {
            hardStop();
            locked = false;
            starting = true;
            tickCount = 0;
            setStatus("Запит доступу до камери…");
            video.setAttribute("playsinline", "true");
            video.muted = true;
            video.playsInline = true;

            return openStream()
                .then(function (mediaStream) {
                    if (locked) {
                        mediaStream.getTracks().forEach(function (t) {
                            t.stop();
                        });
                        return null;
                    }
                    stream = mediaStream;
                    video.srcObject = mediaStream;
                    var p = video.play();
                    return p && typeof p.then === "function"
                        ? p.catch(function () {})
                        : null;
                })
                .then(function () {
                    starting = false;
                    if (locked) return;
                    if (!ensureWorker()) {
                        setStatus(
                            "Не вдалося запустити сканер (Worker). Перезавантажте сторінку."
                        );
                        return;
                    }
                    var gen = loopGen;
                    scanLoop(gen);
                })
                .catch(function (err) {
                    starting = false;
                    console.warn("[isbn-scan] camera failed", err);
                    hardStop();
                    setStatus(
                        "Камера: " +
                            (err && err.message ? err.message : String(err))
                    );
                });
        }

        function openScanModal() {
            // Unlock AudioContext on user gesture so shutter can play later
            try {
                playCameraClick._ctx =
                    playCameraClick._ctx ||
                    new (window.AudioContext || window.webkitAudioContext)();
                if (playCameraClick._ctx.state === "suspended") {
                    playCameraClick._ctx.resume();
                }
            } catch (e) {}
            if (!window.bootstrap || !window.bootstrap.Modal) {
                alert("Bootstrap Modal недоступний");
                return;
            }
            if (modalEl.parentElement !== document.body) {
                document.body.appendChild(modalEl);
            }
            bsModal = window.bootstrap.Modal.getOrCreateInstance(modalEl, {
                backdrop: true,
                keyboard: true,
            });
            bsModal.show();
        }

        openBtns.forEach(function (btn) {
            btn.addEventListener("click", openScanModal);
        });

        modalEl.addEventListener("shown.bs.modal", function () {
            if (starting || running) return;
            startLive();
        });

        modalEl.addEventListener("hide.bs.modal", function () {
            hardStop();
        });
        modalEl.addEventListener("hidden.bs.modal", function () {
            hardStop();
            setStatus("");
            locked = false;
            starting = false;
            running = false;
            forceModalCleanup(modalEl);
        });

        function onCloseClick(ev) {
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
            }
            dismissModal();
        }

        if (closeBtn) {
            closeBtn.addEventListener("pointerdown", onCloseClick, true);
            closeBtn.addEventListener("click", onCloseClick, true);
        }
        modalEl.querySelectorAll('[data-bs-dismiss="modal"]').forEach(function (btn) {
            btn.addEventListener("pointerdown", onCloseClick, true);
            btn.addEventListener("click", onCloseClick, true);
        });

        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape" && modalEl.classList.contains("show")) {
                onCloseClick(ev);
            }
        });
    }

    /** True when raw looks like a complete ISBN-10 or ISBN-13.
     *  Prefixes 978/979 wait for full 13 so we don't fire early at 10 digits.
     */
    function isCompleteIsbn(raw) {
        var digits = String(raw || "")
            .replace(/[^0-9Xx]/g, "")
            .toUpperCase();
        if (/^\d{13}$/.test(digits)) return true;
        if (/^97[89]/.test(digits)) return false;
        if (/^[\dX]{10}$/.test(digits)) return true;
        return false;
    }

    /**
     * Auto-submit «Додати за ISBN» when the field reaches 10/13 digits.
     * AJAX + live search-status messaging (catalogs).
     */
    function initAutoIsbnAdd() {
        var form = document.getElementById("addIsbnForm");
        var isbnInput =
            document.querySelector("#addIsbnForm input[name='isbn']") ||
            document.getElementById("id_isbn");
        if (!form || !isbnInput) return;

        var timer = null;
        var lastSent = "";
        var submitting = false;
        var statusBox = document.getElementById("isbnSearchStatus");
        var statusTitle = document.getElementById("isbnSearchStatusTitle");
        var statusLog = document.getElementById("isbnSearchStatusLog");
        var providers = [];
        try {
            providers = JSON.parse(
                (statusBox && statusBox.getAttribute("data-providers")) || "[]"
            );
        } catch (e) {
            providers = [];
        }
        if (!providers.length) {
            providers = [
                { id: "isbndb", label: "ISBNdb" },
                { id: "openlibrary", label: "Open Library" },
                { id: "googlebooks", label: "Google Books" },
                { id: "librarything", label: "LibraryThing" },
            ];
        }
        var progressTimer = null;
        var progressIdx = 0;

        function setHint(text) {
            var hint = document.getElementById("isbnAutoHint");
            if (hint) hint.textContent = text;
        }

        function showStatus(title) {
            if (!statusBox) return;
            statusBox.hidden = false;
            if (statusTitle) statusTitle.textContent = title || "Пошук у каталогах…";
        }

        function hideStatusLater() {
            if (!statusBox) return;
            setTimeout(function () {
                if (!submitting) statusBox.hidden = true;
            }, 8000);
        }

        function clearLog() {
            if (statusLog) statusLog.innerHTML = "";
        }

        function appendLogLine(label, status, detail) {
            if (!statusLog) return;
            var li = document.createElement("li");
            li.className = "isbn-search-status__row isbn-search-status__row--" + (status || "searching");
            var mark =
                status === "hit"
                    ? "✓"
                    : status === "miss" || status === "skip"
                      ? "·"
                      : "…";
            li.textContent =
                mark +
                " " +
                (label || "") +
                (detail ? " — " + detail : status === "searching" ? "…" : "");
            statusLog.appendChild(li);
            statusLog.scrollTop = statusLog.scrollHeight;
        }

        function stopProgress() {
            if (progressTimer) {
                clearInterval(progressTimer);
                progressTimer = null;
            }
        }

        function startProgress() {
            stopProgress();
            clearLog();
            progressIdx = 0;
            showStatus("Пошук у каталогах…");
            function tick() {
                if (progressIdx >= providers.length) progressIdx = 0;
                var p = providers[progressIdx++];
                if (statusTitle) {
                    statusTitle.textContent = "Шукаємо в " + (p.label || p.id) + "…";
                }
                appendLogLine(p.label || p.id, "searching", "");
            }
            tick();
            progressTimer = setInterval(tick, 1200);
        }

        function renderServerLog(log) {
            stopProgress();
            clearLog();
            if (!log || !log.length) return;
            var hitLabel = "";
            log.forEach(function (step) {
                if (!step || step.provider === "lookup") return;
                appendLogLine(step.label || step.provider, step.status, step.detail || "");
                if (step.status === "hit") hitLabel = step.label || step.provider;
            });
            if (hitLabel && statusTitle) {
                statusTitle.textContent = "Знайдено в " + hitLabel;
            } else if (statusTitle) {
                statusTitle.textContent = "Пошук завершено";
            }
        }

        function csrfToken() {
            var el = form.querySelector('[name="csrfmiddlewaretoken"]');
            return el ? el.value : "";
        }

        function submitIfReady() {
            if (submitting) return;
            var raw = (isbnInput.value || "").trim();
            if (!isCompleteIsbn(raw)) return;
            var key = raw.replace(/[^0-9Xx]/g, "").toUpperCase();
            if (key === lastSent) return;
            lastSent = key;
            submitting = true;
            // FormData skips disabled fields — capture body BEFORE locking the input.
            isbnInput.value = key;
            var body = new FormData(form);
            if (!body.get("isbn")) {
                body.set("isbn", key);
            }
            isbnInput.disabled = true;
            setHint("Шукаємо книгу в каталогах за ISBN…");
            startProgress();

            fetch(form.getAttribute("action") || window.location.href, {
                method: "POST",
                body: body,
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    Accept: "application/json",
                    "X-CSRFToken": csrfToken(),
                },
            })
                .then(function (r) {
                    return r.json().then(function (data) {
                        return { ok: r.ok, status: r.status, data: data || {} };
                    });
                })
                .then(function (res) {
                    renderServerLog(res.data.search_log);
                    if (res.data.needs_confirmation) {
                        setHint(res.data.detail || "Підтвердіть додавання примірника.");
                        hideStatusLater();
                        if (res.data.redirect) {
                            window.location.href = res.data.redirect;
                            return;
                        }
                        window.location.reload();
                        return;
                    }
                    if (res.data.pending_approval && res.data.redirect) {
                        setHint(res.data.detail || "Запит надіслано адміністратору.");
                        window.location.href = res.data.redirect;
                        return;
                    }
                    if (res.ok && res.data.ok !== false) {
                        var msg =
                            res.data.detail ||
                            (res.data.title ? "Додано: " + res.data.title : "Додано.");
                        setHint(msg);
                        showStatus(msg);
                        hideStatusLater();
                        // Soft-insert from DB HTML — same-URL location.href does not reload.
                        if (
                            res.data.shelf_html &&
                            insertLibraryShelfHtml(res.data.shelf_html)
                        ) {
                            isbnInput.value = "";
                            submitting = false;
                            lastSent = "";
                            isbnInput.disabled = false;
                            return;
                        }
                        window.location.reload();
                        return;
                    }
                    setHint(res.data.detail || "Книгу не знайдено.");
                    showStatus(res.data.detail || "Книгу не знайдено.");
                    hideStatusLater();
                    submitting = false;
                    lastSent = "";
                    isbnInput.disabled = false;
                })
                .catch(function (e) {
                    stopProgress();
                    console.warn("[isbn-auto]", e);
                    setHint("Помилка мережі під час пошуку. Спробуйте ще раз.");
                    showStatus("Помилка мережі");
                    submitting = false;
                    lastSent = "";
                    isbnInput.disabled = false;
                });
        }

        function onInput() {
            if (timer) clearTimeout(timer);
            var raw = (isbnInput.value || "").trim();
            if (!isCompleteIsbn(raw)) {
                setHint(
                    "Книга додається автоматично після введення повного ISBN (10 або 13)."
                );
                return;
            }
            // Debounce so paste/scan settle; 10-digit won't fire again when typing toward 13
            timer = setTimeout(submitIfReady, 450);
        }

        isbnInput.addEventListener("input", onInput);
        isbnInput.addEventListener("change", onInput);
        // If page re-rendered with a valid value already filled, don't auto-resubmit
    }

    function boot() {
        initAutoIsbnAdd();
        initIsbnScan();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
