(function () {
    "use strict";

    function clampAge(n, ageMax) {
        n = parseInt(n, 10);
        if (Number.isNaN(n)) return 0;
        return Math.max(0, Math.min(ageMax, n));
    }

    /** Має збігатися з шириною thumb у style.css (18px → радіус 9). */
    var THUMB_RADIUS_PX = 9;
    /** Висота смуги треку - як у .reader-age-dual / ::-webkit-slider-runnable-track. */
    var TRACK_HEIGHT_PX = 10;

    /** Сірий зліва/справа, зелений лише між внутрішніми краями повзунків; по вертикалі - тільки TRACK_HEIGHT_PX. */
    function updateReaderAgeTrackBackground(dualEl, minVal, maxVal, ageMax) {
        if (!dualEl || ageMax <= 0) return;
        var W = dualEl.getBoundingClientRect().width;
        if (W < 1) return;

        var lo = Math.min(minVal, maxVal);
        var hi = Math.max(minVal, maxVal);
        var r = THUMB_RADIUS_PX;
        var t = Math.max(0, W - 2 * r);

        function cx(v) {
            return r + (v / ageMax) * t;
        }

        var cxLo = cx(lo);
        var cxHi = cx(hi);
        var gs = Math.round(Math.min(W, Math.max(0, cxLo + r)));
        var ge = Math.round(Math.min(W, Math.max(0, cxHi - r)));

        var img;
        if (ge <= gs) {
            img =
                "linear-gradient(to right, #dee2e6 0px, #dee2e6 " +
                W +
                "px)";
        } else {
            img =
                "linear-gradient(to right, #dee2e6 0px, #dee2e6 " +
                gs +
                "px, #198754 " +
                gs +
                "px, #198754 " +
                ge +
                "px, #dee2e6 " +
                ge +
                "px, #dee2e6 " +
                W +
                "px)";
        }

        dualEl.style.backgroundImage = img;
        dualEl.style.backgroundSize = W + "px " + TRACK_HEIGHT_PX + "px";
        dualEl.style.backgroundRepeat = "no-repeat";
        dualEl.style.backgroundPosition = "left center";
    }

    function resolveSource(minI, maxI, e) {
        if (e && e.target === minI) return "min";
        if (e && e.target === maxI) return "max";
        if (document.activeElement === minI) return "min";
        if (document.activeElement === maxI) return "max";
        return null;
    }

    function initReaderAgeForms() {
        document.querySelectorAll(".book-reader-age-form").forEach(function (form) {
            var minI = form.querySelector(".reader-age-min");
            var maxI = form.querySelector(".reader-age-max");
            var dualEl = form.querySelector(".reader-age-dual");
            if (!minI || !maxI || !dualEl) return;

            var ageMax = parseInt(minI.getAttribute("max"), 10);
            if (Number.isNaN(ageMax) || ageMax < 1) ageMax = 18;

            function sync(e) {
                var source = resolveSource(minI, maxI, e);
                var rawA = clampAge(minI.value, ageMax);
                var rawB = clampAge(maxI.value, ageMax);
                var a = rawA;
                var b = rawB;
                if (a > b) {
                    if (source === "min") {
                        b = a;
                        maxI.value = String(b);
                    } else if (source === "max") {
                        a = b;
                        minI.value = String(a);
                    } else {
                        a = Math.min(rawA, rawB);
                        b = Math.max(rawA, rawB);
                        minI.value = String(a);
                        maxI.value = String(b);
                    }
                }
                minI.value = String(a);
                maxI.value = String(b);
                updateReaderAgeTrackBackground(dualEl, a, b, ageMax);
            }

            minI.addEventListener("input", sync);
            maxI.addEventListener("input", sync);
            minI.addEventListener("change", sync);
            maxI.addEventListener("change", sync);
            sync();
            if (typeof ResizeObserver !== "undefined") {
                var ro = new ResizeObserver(function () {
                    sync();
                });
                ro.observe(dualEl);
            }
            requestAnimationFrame(function () {
                sync();
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initReaderAgeForms);
    } else {
        initReaderAgeForms();
    }
})();
