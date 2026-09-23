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

    /** Живий бейдж сповіщень у навбарі (кожні 3 с) + звук при зростанні unread. */
    function initNotifBadgePoll() {
        var badge = document.getElementById("nav-notif-badge");
        if (!badge) return;
        var url = badge.getAttribute("data-count-url");
        if (!url) return;

        var lastCount = null; // null = ще не отримали baseline
        var soundUnlocked = false;
        var audio = null;

        function soundUrl() {
            var css = document.querySelector('link[href*="style.css"]');
            if (css && css.href) {
                return css.href.replace(/css\/style\.css.*$/, "sounds/notify.wav");
            }
            return "/static/sounds/notify.wav";
        }

        function ensureAudio() {
            if (!audio) {
                audio = new Audio(soundUrl());
                audio.preload = "auto";
                audio.volume = 0.7;
            }
            return audio;
        }

        function unlockSound() {
            if (soundUnlocked) return;
            soundUnlocked = true;
            try {
                var a = ensureAudio();
                a.muted = true;
                var p = a.play();
                if (p && typeof p.then === "function") {
                    p.then(function () {
                        a.pause();
                        a.currentTime = 0;
                        a.muted = false;
                    }).catch(function () {
                        a.muted = false;
                    });
                } else {
                    a.muted = false;
                }
            } catch (e) {
                /* ignore */
            }
        }

        ["pointerdown", "keydown", "touchstart"].forEach(function (ev) {
            document.addEventListener(ev, unlockSound, { once: true, passive: true });
        });

        function playNotify() {
            try {
                var a = ensureAudio();
                a.currentTime = 0;
                var p = a.play();
                if (p && typeof p.catch === "function") p.catch(function () {});
            } catch (e) {
                /* ignore */
            }
        }

        function render(n) {
            n = parseInt(n, 10) || 0;
            if (n > 0) {
                badge.textContent = n > 99 ? "99+" : String(n);
                badge.classList.remove("d-none");
            } else {
                badge.textContent = "";
                badge.classList.add("d-none");
            }
            if (lastCount !== null && n > lastCount) {
                playNotify();
            }
            lastCount = n;
        }

        function tick() {
            fetch(url, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            })
                .then(function (r) {
                    if (!r.ok) throw new Error("count " + r.status);
                    return r.json();
                })
                .then(function (data) {
                    render(data.unread_count);
                })
                .catch(function () {
                    /* ignore transient */
                });
        }

        tick();
        setInterval(tick, 3000);
        document.addEventListener("visibilitychange", function () {
            if (document.visibilityState === "visible") tick();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initNotifBadgePoll);
    } else {
        initNotifBadgePoll();
    }

    /** Показати / сховати пароль (login + register). */
    function initPasswordToggles() {
        document.querySelectorAll("[data-password-toggle]").forEach(function (btn) {
            if (btn.getAttribute("data-bound") === "1") return;
            btn.setAttribute("data-bound", "1");
            btn.addEventListener("click", function () {
                var group = btn.closest(".password-toggle") || btn.parentElement;
                var input = group && group.querySelector('input[type="password"], input[type="text"]');
                if (!input) return;
                var show = input.getAttribute("type") === "password";
                input.setAttribute("type", show ? "text" : "password");
                btn.setAttribute("aria-pressed", show ? "true" : "false");
                btn.setAttribute("aria-label", show ? "Сховати пароль" : "Показати пароль");
                btn.classList.toggle("is-visible", show);
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPasswordToggles);
    } else {
        initPasswordToggles();
    }

    /**
     * Пошук за назвою: після ≥3 символів і паузи 1 с — submit форми.
     * Не чіпаємо value під час composition (IME / мобільні клавіатури).
     */
    function initTitleAutoSearch() {
        var timer = null;
        document.querySelectorAll("[data-title-autosearch]").forEach(function (input) {
            if (input.getAttribute("data-autosearch-bound") === "1") return;
            input.setAttribute("data-autosearch-bound", "1");
            var composing = false;
            input.addEventListener("compositionstart", function () {
                composing = true;
                clearTimeout(timer);
            });
            input.addEventListener("compositionend", function () {
                composing = false;
                input.dispatchEvent(new Event("input", { bubbles: true }));
            });
            input.addEventListener("input", function () {
                if (composing) return;
                clearTimeout(timer);
                timer = setTimeout(function () {
                    if (composing) return;
                    var form = input.closest("form");
                    if (!form) return;
                    var v = (input.value || "").trim();
                    var current = "";
                    try {
                        current = (new URL(window.location.href).searchParams.get("q") || "").trim();
                    } catch (e) {
                        current = "";
                    }
                    var vLen = Array.from(v).length;
                    var curLen = Array.from(current).length;
                    if (vLen >= 3) {
                        if (v === current) return;
                        if (typeof form.requestSubmit === "function") form.requestSubmit();
                        else form.submit();
                        return;
                    }
                    if (curLen >= 3 && vLen < 3) {
                        var url = new URL(window.location.href);
                        url.searchParams.delete("q");
                        if (url.pathname === "/" || url.pathname.indexOf("/home") === 0) {
                            window.location.href = url.pathname + (url.search || "") + (url.hash || "");
                        } else {
                            window.location.href = "/";
                        }
                    }
                }, 1000);
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initTitleAutoSearch);
    } else {
        initTitleAutoSearch();
    }

    /**
     * Navbar height → --site-nav-h; sync advanced form q; filter toggle state.
     */
    function initNavChrome() {
        var nav = document.querySelector(".site-navbar");
        var syncNav = function () {
            if (!nav) return;
            var navH = Math.ceil(nav.getBoundingClientRect().height);
            document.documentElement.style.setProperty("--site-nav-h", navH + "px");
        };
        if (nav) {
            syncNav();
            window.addEventListener("resize", syncNav);
            window.addEventListener("orientationchange", syncNav);
            if (typeof ResizeObserver !== "undefined") {
                new ResizeObserver(syncNav).observe(nav);
            }
            var collapse = document.getElementById("siteNav");
            if (collapse) {
                collapse.addEventListener("shown.bs.collapse", syncNav);
                collapse.addEventListener("hidden.bs.collapse", syncNav);
            }
        }

        var adv = document.getElementById("advancedSearch");
        var toggle = document.getElementById("siteFilterToggle");
        var navQ = document.getElementById("siteNavbarSearchQ");
        var mirror = document.getElementById("advQMirror");
        var form = document.getElementById("advancedSearchForm");
        var scrollBeforeAdv = 0;

        function isHomePage() {
            var p = window.location.pathname || "/";
            return p === "/" || p === "";
        }

        function setToggleOpen(open) {
            if (!toggle) return;
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
            toggle.classList.toggle("is-open", open);
        }

        function scrollToY(y) {
            var top = Math.max(0, Math.round(y));
            if (typeof window.scrollTo === "function") {
                try {
                    window.scrollTo({ top: top, left: 0, behavior: "auto" });
                } catch (e) {
                    window.scrollTo(0, top);
                }
            } else {
                window.scrollTop = top;
                document.documentElement.scrollTop = top;
                document.body.scrollTop = top;
            }
        }

        if (adv && toggle) {
            setToggleOpen(adv.classList.contains("show"));
            adv.addEventListener("show.bs.collapse", function () {
                setToggleOpen(true);
                if (!isHomePage()) return;
                scrollBeforeAdv = window.scrollY || window.pageYOffset || 0;
            });
            adv.addEventListener("shown.bs.collapse", function () {
                if (!isHomePage()) return;
                /* Mobile panel scrolls itself — don't shove the page */
                if (window.matchMedia && window.matchMedia("(max-width: 991.98px)").matches) {
                    return;
                }
                var h = Math.ceil(adv.getBoundingClientRect().height);
                if (h > 0) scrollToY(scrollBeforeAdv + h);
            });
            adv.addEventListener("hide.bs.collapse", function () {
                setToggleOpen(false);
            });
            adv.addEventListener("hidden.bs.collapse", function () {
                if (!isHomePage()) return;
                if (window.matchMedia && window.matchMedia("(max-width: 991.98px)").matches) {
                    return;
                }
                scrollToY(scrollBeforeAdv);
            });
        }

        if (form && navQ && mirror) {
            form.addEventListener("submit", function () {
                mirror.value = navQ.value || "";
            });
        }

        /* Mobile: hide filter / feed / burger while typing; restore after 2s idle */
        if (navQ) {
            var chromeIdleTimer = null;
            var CHROME_IDLE_MS = 2000;

            function setChromeCompact(on) {
                document.documentElement.classList.toggle("search-chrome-compact", !!on);
                syncNav();
            }

            function onSearchTyping() {
                if (window.matchMedia && !window.matchMedia("(max-width: 991.98px)").matches) {
                    setChromeCompact(false);
                    return;
                }
                setChromeCompact(true);
                if (chromeIdleTimer) clearTimeout(chromeIdleTimer);
                chromeIdleTimer = setTimeout(function () {
                    setChromeCompact(false);
                    chromeIdleTimer = null;
                }, CHROME_IDLE_MS);
            }

            navQ.addEventListener("input", onSearchTyping);
            navQ.addEventListener("compositionend", onSearchTyping);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initNavChrome);
    } else {
        initNavChrome();
    }
})();
