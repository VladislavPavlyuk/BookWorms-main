/**
 * Manual book cover photos — auto-detect + auto-shoot + hard crop (no desk bg).
 * Photos live only in JS `files[]`; deleted thumbs never reach the server.
 * Form submit builds FormData from `files[]` (file input is display-sync only).
 */
(function () {
    "use strict";

    var MAX = 8;
    var DETECT_MS = 280;
    var STABLE_NEED = 4;
    var COOLDOWN_MS = 2200;
    var ANALYSIS_W = 96;
    var ANALYSIS_H = 144;
    /** Must match .manual-photo-crop-guide CSS. */
    var GUIDE_W_FRAC = 0.64;
    var GUIDE_H_FRAC = 0.88;

    function playShutter() {
        try {
            var AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            if (!playShutter._ctx) playShutter._ctx = new AC();
            var ctx = playShutter._ctx;
            if (ctx.state === "suspended") ctx.resume();
            var t0 = ctx.currentTime;
            var osc = ctx.createOscillator();
            var g = ctx.createGain();
            osc.type = "square";
            osc.frequency.setValueAtTime(200, t0);
            osc.frequency.exponentialRampToValueAtTime(55, t0 + 0.04);
            g.gain.setValueAtTime(0.22, t0);
            g.gain.exponentialRampToValueAtTime(0.001, t0 + 0.05);
            osc.connect(g);
            g.connect(ctx.destination);
            osc.start(t0);
            osc.stop(t0 + 0.05);
        } catch (e) {}
    }

    function canvasToJpegFile(canvas, name) {
        var dataUrl = canvas.toDataURL("image/jpeg", 0.92);
        var parts = dataUrl.split(",");
        var mime = ((parts[0].match(/:(.*?);/) || [])[1]) || "image/jpeg";
        var bin = atob(parts[1] || "");
        var u8 = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
        try {
            return new File([u8], name, { type: mime });
        } catch (e) {
            var b = new Blob([u8], { type: mime });
            b._manualName = name;
            return b;
        }
    }

    function centerGuideRect(vw, vh) {
        var rw = Math.max(32, Math.floor(vw * GUIDE_W_FRAC));
        var rh = Math.max(32, Math.floor(vh * GUIDE_H_FRAC));
        return {
            x: Math.floor((vw - rw) / 2),
            y: Math.floor((vh - rh) / 2),
            w: rw,
            h: rh,
        };
    }

    /**
     * Aggressive edge trim: strip near-uniform desk from each side until
     * content density rises. Always returns ≤ source size.
     */
    function trimBackgroundCanvas(srcCanvas) {
        var w = srcCanvas.width;
        var h = srcCanvas.height;
        if (w < 24 || h < 24) return srcCanvas;
        var ctx;
        try {
            ctx = srcCanvas.getContext("2d", { willReadFrequently: true });
        } catch (e) {
            ctx = srcCanvas.getContext("2d");
        }
        var img;
        try {
            img = ctx.getImageData(0, 0, w, h);
        } catch (e2) {
            return srcCanvas;
        }
        var d = img.data;

        function sample(x, y) {
            var i = (y * w + x) * 4;
            return [d[i], d[i + 1], d[i + 2]];
        }

        function avgCorner(cx, cy) {
            var r = 0, g = 0, b = 0, n = 0;
            for (var dy = 0; dy < 8; dy++) {
                for (var dx = 0; dx < 8; dx++) {
                    var p = sample(
                        Math.max(0, Math.min(w - 1, cx + dx)),
                        Math.max(0, Math.min(h - 1, cy + dy))
                    );
                    r += p[0];
                    g += p[1];
                    b += p[2];
                    n++;
                }
            }
            return [r / n, g / n, b / n];
        }

        var c1 = avgCorner(1, 1);
        var c2 = avgCorner(w - 9, 1);
        var c3 = avgCorner(1, h - 9);
        var c4 = avgCorner(w - 9, h - 9);
        var br = (c1[0] + c2[0] + c3[0] + c4[0]) / 4;
        var bg = (c1[1] + c2[1] + c3[1] + c4[1]) / 4;
        var bb = (c1[2] + c2[2] + c3[2] + c4[2]) / 4;
        var thresh = 48;

        function isBgAt(x, y) {
            var p = sample(x, y);
            return (
                Math.abs(p[0] - br) < thresh &&
                Math.abs(p[1] - bg) < thresh &&
                Math.abs(p[2] - bb) < thresh
            );
        }

        function rowBgRatio(y) {
            var bgN = 0, n = 0;
            for (var x = 0; x < w; x += 2) {
                n++;
                if (isBgAt(x, y)) bgN++;
            }
            return n ? bgN / n : 1;
        }

        function colBgRatio(x, y0, y1) {
            var bgN = 0, n = 0;
            for (var y = y0; y <= y1; y += 2) {
                n++;
                if (isBgAt(x, y)) bgN++;
            }
            return n ? bgN / n : 1;
        }

        var maxTrim = Math.floor(Math.min(w, h) * 0.42);
        var top = 0, bottom = h - 1, left = 0, right = w - 1;
        var bgRow = 0.78;

        while (top < maxTrim && rowBgRatio(top) >= bgRow) top++;
        while (bottom > h - 1 - maxTrim && rowBgRatio(bottom) >= bgRow) bottom--;
        while (left < maxTrim && colBgRatio(left, top, bottom) >= bgRow) left++;
        while (right > w - 1 - maxTrim && colBgRatio(right, top, bottom) >= bgRow) {
            right--;
        }

        var pad = Math.max(2, (Math.min(w, h) * 0.008) | 0);
        left = Math.max(0, left - pad);
        top = Math.max(0, top - pad);
        right = Math.min(w - 1, right + pad);
        bottom = Math.min(h - 1, bottom + pad);
        var cw = right - left + 1;
        var ch = bottom - top + 1;
        if (cw < 24 || ch < 24) return srcCanvas;
        if (cw >= w && ch >= h) return srcCanvas;

        var out = document.createElement("canvas");
        out.width = cw;
        out.height = ch;
        out.getContext("2d").drawImage(srcCanvas, left, top, cw, ch, 0, 0, cw, ch);
        return out;
    }

    function cropBookFromVideo(video) {
        var vw = video.videoWidth;
        var vh = video.videoHeight;
        if (!vw || !vh) throw new Error("no video frame");

        var rect = centerGuideRect(vw, vh);
        var guided = document.createElement("canvas");
        guided.width = rect.w;
        guided.height = rect.h;
        guided
            .getContext("2d")
            .drawImage(video, rect.x, rect.y, rect.w, rect.h, 0, 0, rect.w, rect.h);

        var trimmed = trimBackgroundCanvas(guided);
        // Second pass on tighter crop
        if (trimmed.width < guided.width * 0.98 || trimmed.height < guided.height * 0.98) {
            trimmed = trimBackgroundCanvas(trimmed);
        }
        if (trimmed.width >= vw * 0.95 && trimmed.height >= vh * 0.95) {
            return guided;
        }
        return trimmed;
    }

    function scoreGuideFill(video) {
        if (!video.videoWidth) return 0;
        var rect = centerGuideRect(video.videoWidth, video.videoHeight);
        var c = document.createElement("canvas");
        c.width = ANALYSIS_W;
        c.height = ANALYSIS_H;
        var ctx = c.getContext("2d", { willReadFrequently: true });
        if (!ctx) return 0;
        try {
            ctx.drawImage(
                video,
                rect.x,
                rect.y,
                rect.w,
                rect.h,
                0,
                0,
                ANALYSIS_W,
                ANALYSIS_H
            );
        } catch (e) {
            return 0;
        }
        var img;
        try {
            img = ctx.getImageData(0, 0, ANALYSIS_W, ANALYSIS_H);
        } catch (e2) {
            return 0;
        }
        var d = img.data;
        var border = [];
        function pushPx(x, y) {
            var i = (y * ANALYSIS_W + x) * 4;
            border.push([d[i], d[i + 1], d[i + 2]]);
        }
        for (var x = 0; x < ANALYSIS_W; x += 2) {
            pushPx(x, 0);
            pushPx(x, ANALYSIS_H - 1);
        }
        for (var y = 0; y < ANALYSIS_H; y += 2) {
            pushPx(0, y);
            pushPx(ANALYSIS_W - 1, y);
        }
        var br = 0, bg = 0, bb = 0;
        for (var bi = 0; bi < border.length; bi++) {
            br += border[bi][0];
            bg += border[bi][1];
            bb += border[bi][2];
        }
        br /= border.length;
        bg /= border.length;
        bb /= border.length;

        var thresh = 30;
        var nonBg = 0;
        var total = 0;
        var sum = 0;
        var sum2 = 0;
        var x0 = (ANALYSIS_W * 0.15) | 0;
        var x1 = (ANALYSIS_W * 0.85) | 0;
        var y0 = (ANALYSIS_H * 0.12) | 0;
        var y1 = (ANALYSIS_H * 0.88) | 0;
        for (var yy = y0; yy < y1; yy += 2) {
            for (var xx = x0; xx < x1; xx += 2) {
                var i = (yy * ANALYSIS_W + xx) * 4;
                var r = d[i],
                    g = d[i + 1],
                    b = d[i + 2];
                var lum = 0.299 * r + 0.587 * g + 0.114 * b;
                sum += lum;
                sum2 += lum * lum;
                total++;
                if (
                    Math.abs(r - br) >= thresh ||
                    Math.abs(g - bg) >= thresh ||
                    Math.abs(b - bb) >= thresh
                ) {
                    nonBg++;
                }
            }
        }
        if (!total) return 0;
        var fill = nonBg / total;
        var mean = sum / total;
        var variance = sum2 / total - mean * mean;
        if (variance < 80) return fill * 0.3;
        return fill;
    }

    function init() {
        var form = document.getElementById("manualAddBookForm");
        var dest = document.getElementById("manualPhotos");
        var preview = document.getElementById("manualPhotoPreview");
        var openBtn = document.getElementById("manualPhotoCamera");
        var countEl = document.getElementById("manualPhotoCount");
        var modalEl = document.getElementById("manualPhotoCaptureModal");
        var video = document.getElementById("manualPhotoCaptureVideo");
        var statusEl = document.getElementById("manualPhotoCaptureStatus");
        var shutterBtn = document.getElementById("manualPhotoShutter");
        var guideEl = document.getElementById("manualPhotoCropGuide");

        if (!form || !dest || !preview || !openBtn || !modalEl || !video) {
            console.warn("[manual-photo] core DOM missing");
            return;
        }
        if (!guideEl) {
            guideEl = document.createElement("div");
            guideEl.id = "manualPhotoCropGuide";
            guideEl.className = "manual-photo-crop-guide";
            var stage = modalEl.querySelector(".manual-photo-capture-stage");
            if (stage) stage.appendChild(guideEl);
        }

        /** Sole source of truth — deleted entries never leave this array. */
        var files = [];
        var objectUrls = [];
        var stream = null;
        var bsModal = null;
        var starting = false;
        var busy = false;
        var detectTimer = null;
        var stableHits = 0;
        var lastAutoAt = 0;
        var gen = 0;
        var submitting = false;

        function setStatus(msg) {
            if (statusEl) statusEl.textContent = msg || "";
        }

        function stopDetect() {
            if (detectTimer != null) {
                clearTimeout(detectTimer);
                detectTimer = null;
            }
            gen += 1;
            stableHits = 0;
        }

        function stopStream() {
            stopDetect();
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
                video.srcObject = null;
            } catch (e3) {}
            try {
                video.pause();
            } catch (e4) {}
        }

        /** Mirror files[] → <input type=file> (best-effort). Always clear first. */
        function syncInput() {
            try {
                dest.value = "";
            } catch (e0) {}
            if (!files.length) return;
            if (typeof DataTransfer === "undefined") return;
            try {
                var dt = new DataTransfer();
                files.forEach(function (f) {
                    try {
                        if (typeof File !== "undefined" && f instanceof File) {
                            dt.items.add(f);
                        } else if (f) {
                            dt.items.add(
                                new File([f], f._manualName || f.name || "book.jpg", {
                                    type: f.type || "image/jpeg",
                                })
                            );
                        }
                    } catch (e) {}
                });
                dest.files = dt.files;
            } catch (e2) {
                console.warn("[manual-photo] syncInput", e2);
            }
        }

        function clearObjectUrls() {
            objectUrls.forEach(function (u) {
                try {
                    URL.revokeObjectURL(u);
                } catch (e) {}
            });
            objectUrls = [];
        }

        function render() {
            clearObjectUrls();
            preview.innerHTML = "";
            if (countEl) {
                countEl.textContent = files.length ? files.length + " / " + MAX : "";
            }
            if (aiBtn) aiBtn.disabled = !files.length || recognizing;
            files.forEach(function (f, idx) {
                var wrap = document.createElement("div");
                wrap.className = "manual-photo-thumb";
                var img = document.createElement("img");
                img.alt = "";
                var url = URL.createObjectURL(f);
                objectUrls.push(url);
                img.src = url;
                var rm = document.createElement("button");
                rm.type = "button";
                rm.className = "manual-photo-remove";
                rm.setAttribute("aria-label", "Видалити фото");
                rm.textContent = "×";
                rm.addEventListener("click", function (ev) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    files.splice(idx, 1);
                    syncInput();
                    render();
                    console.info("[manual-photo] deleted idx", idx, "left", files.length);
                });
                wrap.appendChild(img);
                wrap.appendChild(rm);
                preview.appendChild(wrap);
            });
        }

        function addFile(file) {
            if (!file || files.length >= MAX) return false;
            files.push(file);
            syncInput();
            render();
            recognizeAllCovers();
            return true;
        }

        var aiStatusEl = document.getElementById("manualPhotoAiStatus");
        var aiBtn = document.getElementById("manualPhotoRecognize");
        var recognizeUrlEl = document.getElementById("manualRecognizeUrl");
        var recognizing = false;

        function setAiStatus(msg) {
            if (aiStatusEl) aiStatusEl.textContent = msg || "";
        }

        function fillEmptyField(id, value) {
            if (!value) return;
            var el = document.getElementById(id);
            if (!el) return;
            if ((el.value || "").trim()) return; // don't overwrite user input
            el.value = value;
            try {
                el.dispatchEvent(new Event("input", { bubbles: true }));
                el.dispatchEvent(new Event("change", { bubbles: true }));
            } catch (e) {}
        }

        function setField(id, value) {
            if (value == null || value === "") return;
            var el = document.getElementById(id);
            if (!el) return;
            el.value = value;
            try {
                el.dispatchEvent(new Event("input", { bubbles: true }));
                el.dispatchEvent(new Event("change", { bubbles: true }));
            } catch (e) {}
        }

        function csrfToken() {
            var el = form.querySelector('[name="csrfmiddlewaretoken"]');
            return el ? el.value : "";
        }

        function recognizeAllCovers() {
            if (!files.length || recognizing) return;
            var url = recognizeUrlEl && recognizeUrlEl.value;
            if (!url) return;
            recognizing = true;
            if (aiBtn) aiBtn.disabled = true;
            setAiStatus(
                files.length > 1
                    ? "AI читає всі " + files.length + " фото…"
                    : "AI розпізнає обкладинку…"
            );
            var fd = new FormData();
            files.forEach(function (file, i) {
                fd.append(
                    "photos",
                    file,
                    file.name || file._manualName || "cover_" + (i + 1) + ".jpg"
                );
            });
            fetch(url, {
                method: "POST",
                body: fd,
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken(),
                },
            })
                .then(function (res) {
                    return res.text().then(function (text) {
                        var data = null;
                        try {
                            data = text ? JSON.parse(text) : null;
                        } catch (e) {
                            data = { detail: text.slice(0, 160) };
                        }
                        if (!res.ok) {
                            var msg =
                                (data && data.detail) ||
                                "HTTP " + res.status;
                            throw new Error(msg);
                        }
                        return data || {};
                    });
                })
                .then(function (data) {
                    fillEmptyField("manualIsbn", data.isbn);
                    fillEmptyField(
                        "manualTitle",
                        data.title ||
                            (data.raw_text
                                ? String(data.raw_text).split("\n")[0]
                                : "")
                    );
                    fillEmptyField("manualAuthors", data.authors);
                    fillEmptyField("manualPublisher", data.publisher);
                    fillEmptyField("manualPublishDate", data.publish_date);
                    setField(
                        "manualCoverText",
                        data.cover_text || data.raw_text || ""
                    );
                    var bits = [];
                    if (data.title || data.raw_text) bits.push("назва");
                    if (data.authors) bits.push("автори");
                    if (data.isbn) bits.push("ISBN");
                    else if (data.isbn_missing || data.note)
                        bits.push(data.note || "ISBN code not exists");
                    if (data.raw_text || data.cover_text) bits.push("повний текст");
                    var nScan = data.photos_scanned || files.length;
                    var extra =
                        nScan > 1
                            ? " (краще з " +
                              ((data.best_photo_index || 0) + 1) +
                              "/" +
                              nScan +
                              ")"
                            : "";
                    setAiStatus(
                        bits.length
                            ? "AI заповнив: " + bits.join(", ") + extra
                            : "AI не знайшов текст на обкладинці"
                    );
                })
                .catch(function (err) {
                    console.warn("[manual-photo] AI", err);
                    setAiStatus(
                        "AI: " +
                            (err && err.message ? err.message : String(err))
                    );
                })
                .finally(function () {
                    recognizing = false;
                    if (aiBtn) aiBtn.disabled = !files.length;
                });
        }

        if (aiBtn) {
            aiBtn.addEventListener("click", function () {
                if (!files.length) {
                    setAiStatus("Спочатку зробіть фото обкладинки.");
                    return;
                }
                recognizeAllCovers();
            });
        }

        var clearBtn = document.getElementById("manualClearAllBtn");
        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                if (recognizing || submitting) return;
                var ids = [
                    "manualIsbn",
                    "manualTitle",
                    "manualAuthors",
                    "manualPublisher",
                    "manualPublishDate",
                    "manualCoverText",
                ];
                ids.forEach(function (id) {
                    var el = document.getElementById(id);
                    if (el) el.value = "";
                });
                // Optional URL fields from Django form (may lack fixed ids)
                Array.prototype.forEach.call(form.elements, function (el) {
                    if (!el || !el.name) return;
                    if (el.type === "hidden" || el.type === "submit" || el.type === "button") {
                        return;
                    }
                    if (el.type === "file") {
                        el.value = "";
                        return;
                    }
                    if (el.type === "checkbox" || el.type === "radio") {
                        el.checked = false;
                        return;
                    }
                    if (
                        el.name === "cover_url" ||
                        el.name === "info_url" ||
                        el.name === "isbn" ||
                        el.name === "title" ||
                        el.name === "authors" ||
                        el.name === "publisher" ||
                        el.name === "publish_date" ||
                        el.name === "cover_text"
                    ) {
                        el.value = "";
                    }
                });
                files = [];
                syncInput();
                render();
                setAiStatus("");
                console.info("[manual-photo] cleared all fields");
            });
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

        function doSnap(reason) {
            if (busy) return false;
            if (files.length >= MAX) {
                setStatus("Максимум " + MAX + " фото.");
                stopDetect();
                return false;
            }
            if (!video.videoWidth) {
                setStatus("Камера ще не готова…");
                return false;
            }
            busy = true;
            setStatus(
                reason === "auto"
                    ? "Обкладинку розпізнано — зйомка + обрізка…"
                    : "Зйомка та обрізка…"
            );
            setTimeout(function () {
                try {
                    playShutter();
                    var cropped = cropBookFromVideo(video);
                    console.info(
                        "[manual-photo] crop",
                        video.videoWidth + "x" + video.videoHeight,
                        "→",
                        cropped.width + "x" + cropped.height
                    );
                    var name =
                        "book_" +
                        Date.now() +
                        "_" +
                        (files.length + 1) +
                        ".jpg";
                    var file = canvasToJpegFile(cropped, name);
                    addFile(file);
                    lastAutoAt = Date.now();
                    stableHits = 0;
                    setStatus(
                        "Знято " +
                            files.length +
                            "/" +
                            MAX +
                            " (обрізано " +
                            cropped.width +
                            "×" +
                            cropped.height +
                            "). Видалені з прев’ю не потраплять у базу."
                    );
                    if (files.length >= MAX) {
                        stopDetect();
                        if (bsModal) {
                            try {
                                bsModal.hide();
                            } catch (e) {}
                        }
                    }
                } catch (err) {
                    console.warn("[manual-photo] snap", err);
                    setStatus(
                        "Помилка зйомки: " +
                            (err && err.message ? err.message : String(err))
                    );
                } finally {
                    busy = false;
                }
            }, 30);
            return true;
        }

        function detectTick(myGen) {
            if (myGen !== gen) return;
            detectTimer = null;
            if (busy || files.length >= MAX || !stream) return;

            var score = 0;
            try {
                score = scoreGuideFill(video);
            } catch (e) {
                score = 0;
            }

            var ready = score >= 0.42;
            if (ready) {
                stableHits += 1;
                if (guideEl) guideEl.classList.add("manual-photo-crop-guide--ready");
                setStatus(
                    "Книгу видно (" +
                        Math.round(score * 100) +
                        "%). Стабілізація " +
                        stableHits +
                        "/" +
                        STABLE_NEED +
                        "…"
                );
            } else {
                stableHits = 0;
                if (guideEl) guideEl.classList.remove("manual-photo-crop-guide--ready");
                setStatus(
                    "Наведіть обкладинку в рамку — зйомка + автообрізка."
                );
            }

            if (
                stableHits >= STABLE_NEED &&
                Date.now() - lastAutoAt > COOLDOWN_MS
            ) {
                doSnap("auto");
            }

            detectTimer = setTimeout(function () {
                detectTick(myGen);
            }, DETECT_MS);
        }

        function startDetect() {
            stopDetect();
            var myGen = gen;
            detectTimer = setTimeout(function () {
                detectTick(myGen);
            }, 400);
        }

        function startCamera() {
            starting = true;
            stopStream();
            setStatus("Запит доступу до камери…");
            video.setAttribute("playsinline", "true");
            video.muted = true;
            video.playsInline = true;
            return openStream()
                .then(function (mediaStream) {
                    stream = mediaStream;
                    video.srcObject = mediaStream;
                    var p = video.play();
                    return p && typeof p.then === "function"
                        ? p.catch(function () {})
                        : null;
                })
                .then(function () {
                    starting = false;
                    setStatus(
                        "Наведіть обкладинку в рамку — зйомка + автообрізка."
                    );
                    startDetect();
                })
                .catch(function (err) {
                    starting = false;
                    console.warn("[manual-photo] camera", err);
                    stopStream();
                    setStatus(
                        "Камера: " +
                            (err && err.message ? err.message : String(err))
                    );
                });
        }

        /**
         * Never trust <input type=file> for photos — only files[] (post-delete).
         */
        form.addEventListener("submit", function (ev) {
            if (submitting) return;
            ev.preventDefault();
            ev.stopPropagation();
            submitting = true;
            stopStream();

            var fd = new FormData();
            Array.prototype.forEach.call(form.elements, function (el) {
                if (!el || !el.name) return;
                if (el === dest) return;
                if (el.type === "file") return;
                if (el.type === "submit" || el.type === "button") return;
                if ((el.type === "checkbox" || el.type === "radio") && !el.checked) {
                    return;
                }
                fd.append(el.name, el.value);
            });
            files.forEach(function (f, i) {
                var fname = f.name || f._manualName || "book_" + (i + 1) + ".jpg";
                fd.append("photos", f, fname);
            });
            console.info("[manual-photo] submit photos=", files.length);

            var action = form.getAttribute("action") || window.location.href;
            var method = (form.getAttribute("method") || "POST").toUpperCase();

            fetch(action, {
                method: method,
                body: fd,
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken(),
                    Accept: "application/json",
                },
                redirect: "follow",
            })
                .then(function (res) {
                    return res.text().then(function (text) {
                        var data = null;
                        try {
                            data = text ? JSON.parse(text) : null;
                        } catch (e) {
                            data = null;
                        }
                        if (data && typeof data === "object") {
                            if (data.ok) {
                                if (
                                    data.shelf_html &&
                                    typeof window.insertLibraryShelfHtml === "function" &&
                                    window.insertLibraryShelfHtml(data.shelf_html)
                                ) {
                                    var collapse = document.getElementById("manualAddBook");
                                    if (collapse && window.bootstrap) {
                                        var c = bootstrap.Collapse.getInstance(collapse);
                                        if (c) c.hide();
                                    }
                                    form.reset();
                                    return;
                                }
                                window.location.reload();
                                return;
                            }
                            if (!res.ok || data.ok === false) {
                                throw new Error(
                                    data.detail ||
                                        "Не збережено (photos=" +
                                            (data.photos_received || 0) +
                                            ")"
                                );
                            }
                        }
                        // Legacy HTML response / redirect follow
                        if (res.redirected && res.url) {
                            window.location.href = res.url;
                            return;
                        }
                        if (res.ok) {
                            window.location.reload();
                            return;
                        }
                        throw new Error(
                            "HTTP " + res.status + " " + String(text).slice(0, 120)
                        );
                    });
                })
                .catch(function (err) {
                    console.warn("[manual-photo] submit", err);
                    submitting = false;
                    alert(
                        "Не вдалося зберегти: " +
                            (err && err.message ? err.message : String(err))
                    );
                });
        });

        openBtn.addEventListener("click", function () {
            if (files.length >= MAX) {
                alert("Максимум " + MAX + " фото.");
                return;
            }
            if (!window.bootstrap || !window.bootstrap.Modal) {
                alert("Bootstrap Modal недоступний");
                return;
            }
            try {
                playShutter._ctx =
                    playShutter._ctx ||
                    new (window.AudioContext || window.webkitAudioContext)();
                if (playShutter._ctx.state === "suspended") {
                    playShutter._ctx.resume();
                }
            } catch (e) {}
            if (modalEl.parentElement !== document.body) {
                document.body.appendChild(modalEl);
            }
            bsModal = window.bootstrap.Modal.getOrCreateInstance(modalEl, {
                backdrop: true,
                keyboard: true,
            });
            bsModal.show();
        });

        var galleryBtn = document.getElementById("manualPhotoGallery");
        var galleryInput = document.getElementById("manualPhotoGalleryInput");
        if (galleryBtn && galleryInput) {
            galleryBtn.addEventListener("click", function () {
                if (files.length >= MAX) {
                    alert("Максимум " + MAX + " фото.");
                    return;
                }
                galleryInput.value = "";
                galleryInput.click();
            });
            galleryInput.addEventListener("change", function () {
                var picked = galleryInput.files ? Array.from(galleryInput.files) : [];
                var added = 0;
                picked.forEach(function (f) {
                    if (!f || !(f.type || "").match(/^image\//)) return;
                    if (addFile(f)) added += 1;
                });
                if (!added && picked.length) {
                    alert(files.length >= MAX ? "Максимум " + MAX + " фото." : "Не вдалося додати зображення.");
                }
                galleryInput.value = "";
            });
        }

        modalEl.addEventListener("shown.bs.modal", function () {
            if (starting) return;
            startCamera();
        });
        modalEl.addEventListener("hide.bs.modal", stopStream);
        modalEl.addEventListener("hidden.bs.modal", function () {
            stopStream();
            setStatus("");
            starting = false;
            busy = false;
            if (guideEl) guideEl.classList.remove("manual-photo-crop-guide--ready");
        });

        function onShutter(ev) {
            if (ev) {
                try {
                    ev.preventDefault();
                    ev.stopPropagation();
                } catch (e) {}
            }
            doSnap("manual");
        }
        if (shutterBtn) {
            shutterBtn.type = "button";
            shutterBtn.onclick = onShutter;
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();

/* Edit manually-added shelf books */
(function () {
    "use strict";

    function csrfToken() {
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (m) return decodeURIComponent(m[1]);
        var el = document.querySelector("#editManualBookForm input[name=csrfmiddlewaretoken]");
        return el ? el.value : "";
    }

    function showModal(modalEl) {
        // Escape .site-main { z-index:1 } stacking context so modal beats navbar (1030)
        if (modalEl.parentElement !== document.body) {
            document.body.appendChild(modalEl);
        }
        if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
            bootstrap.Modal.getOrCreateInstance(modalEl).show();
            return;
        }
        modalEl.classList.add("show");
        modalEl.style.display = "block";
        modalEl.removeAttribute("aria-hidden");
        modalEl.setAttribute("aria-modal", "true");
        document.body.classList.add("modal-open");
        if (!document.getElementById("editManualBookBackdrop")) {
            var bd = document.createElement("div");
            bd.className = "modal-backdrop fade show";
            bd.id = "editManualBookBackdrop";
            document.body.appendChild(bd);
        }
    }

    function initEditManual() {
        var modalEl = document.getElementById("editManualBookModal");
        var form = document.getElementById("editManualBookForm");
        if (!modalEl || !form) {
            console.warn("[edit-manual] modal/form missing");
            return;
        }
        if (modalEl.parentElement !== document.body) {
            document.body.appendChild(modalEl);
        }

        var existingBox = document.getElementById("editManualExistingPhotos");
        var statusEl = document.getElementById("editManualStatus");
        var saveBtn = document.getElementById("editManualSaveBtn");
        var submitting = false;

        function setStatus(msg) {
            if (statusEl) statusEl.textContent = msg || "";
        }

        document.querySelectorAll(".js-edit-manual-book").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var sid = btn.getAttribute("data-shelf-id") || "";
                var payloadEl = document.getElementById("edit-book-payload-" + sid);
                var data = {};
                try {
                    data = JSON.parse(
                        (payloadEl && payloadEl.textContent) || "{}"
                    );
                } catch (e) {
                    console.warn("[edit-manual] bad payload", e);
                    alert("Не вдалося відкрити редагування (пошкоджені дані).");
                    return;
                }
                form.action = data.edit_url || "";
                if (!form.action) {
                    alert("Немає URL збереження.");
                    return;
                }
                form.querySelector("#editManualIsbn").value = data.isbn || "";
                form.querySelector("#editManualTitle").value = data.title || "";
                form.querySelector("#editManualAuthors").value = data.authors || "";
                form.querySelector("#editManualPublisher").value = data.publisher || "";
                form.querySelector("#editManualPublishDate").value =
                    data.publish_date || "";
                var coverTextEl = form.querySelector("#editManualCoverText");
                if (coverTextEl) coverTextEl.value = data.cover_text || "";
                var photosInput = form.querySelector("#editManualPhotos");
                if (photosInput) photosInput.value = "";
                if (existingBox) existingBox.innerHTML = "";
                setStatus("");
                (data.photos || []).forEach(function (p) {
                    if (!existingBox || !p || !p.id || !p.url) return;
                    var wrap = document.createElement("label");
                    wrap.className = "manual-photo-thumb position-relative";
                    wrap.style.cssText = "display:inline-block;width:72px;";
                    var img = document.createElement("img");
                    img.src = p.url;
                    img.alt = "";
                    img.style.cssText =
                        "width:72px;height:96px;object-fit:cover;border-radius:4px;";
                    var span = document.createElement("span");
                    span.className = "small d-block text-center mt-1";
                    var cb = document.createElement("input");
                    cb.type = "checkbox";
                    cb.name = "delete_photo_ids";
                    cb.value = String(p.id);
                    span.appendChild(cb);
                    span.appendChild(document.createTextNode(" видалити"));
                    wrap.appendChild(img);
                    wrap.appendChild(span);
                    existingBox.appendChild(wrap);
                });
                showModal(modalEl);
            });
        });

        form.addEventListener("submit", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if (submitting) return;
            if (!form.action) {
                setStatus("Немає URL збереження.");
                return;
            }
            submitting = true;
            if (saveBtn) saveBtn.disabled = true;
            setStatus("Збереження…");

            var fd = new FormData();
            Array.prototype.forEach.call(form.elements, function (el) {
                if (!el || !el.name) return;
                if (el.type === "file") return;
                if (el.type === "submit" || el.type === "button") return;
                if ((el.type === "checkbox" || el.type === "radio") && !el.checked) {
                    return;
                }
                fd.append(el.name, el.value);
            });
            var photosInput = form.querySelector("#editManualPhotos");
            if (photosInput && photosInput.files) {
                Array.prototype.forEach.call(photosInput.files, function (f) {
                    if (f && f.size > 0) fd.append("photos", f, f.name || "book.jpg");
                });
            }

            fetch(form.action, {
                method: "POST",
                body: fd,
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken(),
                    Accept: "application/json",
                },
                redirect: "follow",
            })
                .then(function (res) {
                    return res.text().then(function (text) {
                        var data = null;
                        try {
                            data = text ? JSON.parse(text) : null;
                        } catch (e) {
                            data = null;
                        }
                        if (data && typeof data === "object") {
                            if (data.ok) {
                                window.location.reload();
                                return;
                            }
                            if (!res.ok || data.ok === false) {
                                throw new Error(data.detail || "Не збережено");
                            }
                        }
                        if (res.redirected && res.url) {
                            window.location.href = res.url;
                            return;
                        }
                        if (res.ok) {
                            window.location.reload();
                            return;
                        }
                        throw new Error(
                            "HTTP " + res.status + " " + String(text).slice(0, 160)
                        );
                    });
                })
                .catch(function (err) {
                    console.warn("[edit-manual] submit", err);
                    setStatus(err && err.message ? err.message : String(err));
                })
                .finally(function () {
                    submitting = false;
                    if (saveBtn) saveBtn.disabled = false;
                });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initEditManual);
    } else {
        initEditManual();
    }
})();
