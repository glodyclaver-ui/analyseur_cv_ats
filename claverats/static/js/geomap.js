/* =========================================================
   GeoMap - carte interactive 100 % locale (SVG, sans bibliothèque ni internet)
   API : GeoMap.mount(conteneur, { pins, route, onPinClick, selectedId, label })
   ========================================================= */
(function (global) {
    "use strict";
    var NS = "http://www.w3.org/2000/svg";
    var W = 720, H = 360;                       // monde en projection équirectangulaire
    var MIN_W = W / 64;
    var reduce = !!(global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches);
    var uid = 0;

    var land = (global.GEO_LAND || []).slice();
    var focus = (global.GEO_FOCUS || []).slice();
    var realCountries = null;
    var instances = [];

    function X(lon) { return (lon + 180) / 360 * W; }
    function Y(lat) { return (90 - lat) / 180 * H; }
    function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
    function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
    function el(name, attrs, parent) {
        var e = document.createElementNS(NS, name);
        for (var k in attrs) e.setAttribute(k, attrs[k]);
        if (parent) parent.appendChild(e);
        return e;
    }
    function div(cls, parent, html) {
        var d = document.createElement("div");
        d.className = cls;
        if (html != null) d.innerHTML = html;
        if (parent) parent.appendChild(d);
        return d;
    }
    function ringsPath(rings) {
        var d = "";
        rings.forEach(function (r) {
            r.forEach(function (p, i) { d += (i ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1); });
            d += "Z";
        });
        return d;
    }
    function bbox(rings) {
        var a = 1e9, b = 1e9, c = -1e9, d = -1e9;
        rings.forEach(function (r) { r.forEach(function (p) { a = Math.min(a, X(p[0])); c = Math.max(c, X(p[0])); b = Math.min(b, Y(p[1])); d = Math.max(d, Y(p[1])); }); });
        return { x0: a, y0: b, x1: c, y1: d };
    }
    function haversine(a, b) {
        var R = 6371, rad = Math.PI / 180;
        var dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
        var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return Math.round(2 * R * Math.asin(Math.sqrt(h)));
    }
    function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }

    /* ---------- Données réelles optionnelles (Natural Earth) ---------- */
    function geojsonToFeatures(gj) {
        var out = [];
        (gj.features || []).forEach(function (f, i) {
            var g = f.geometry; if (!g) return;
            var p = f.properties || {};
            var polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
            var rings = [];
            polys.forEach(function (poly) { poly.forEach(function (r) { rings.push(r); }); });
            var name = p.NAME_FR || p.name_fr || p.NAME || p.name || p.ADMIN || ("Pays " + (i + 1));
            out.push({ id: "c" + i, name: name, type: "country", info: "Pays" + (p.CONTINENT ? " • " + p.CONTINENT : ""), rings: rings, iso: p.ISO_A3 || p.iso_a3 || "" });
        });
        return out;
    }
    function loadCountries(url) {
        if (!global.fetch) return Promise.resolve(false);
        return fetch(url, { cache: "force-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (gj) {
            if (!gj || !gj.features || !gj.features.length) return false;
            realCountries = geojsonToFeatures(gj);
            instances.forEach(function (i) { i.drawLand(); });
            return true;
        }).catch(function () { return false; });
    }

    /* ---------- Instance ---------- */
    function Inst(box, opts) {
        this.box = box; this.opts = opts || {}; this.id = ++uid;
        this.view = { cx: W / 2, cy: H / 2, w: W };
        this.pins = []; this.pinEls = {}; this.hover = null; this.active = null;
        this.pointers = {}; this.moved = false; this.anim = null; this.hintShown = false;
        this.build();
        this.update(opts);
        instances.push(this);
    }
    Inst.prototype.build = function () {
        var self = this, b = this.box, u = this.id;
        b.innerHTML = "";
        var root = this.root = div("gm-root", b);
        root.tabIndex = 0;
        root.setAttribute("role", "group");
        root.setAttribute("aria-label", this.opts.label || "Carte interactive. Flèches pour déplacer, plus et moins pour zoomer, zéro pour recentrer.");
        var svg = this.svg = el("svg", { "class": "gm-svg", "preserveAspectRatio": "xMidYMid meet", "aria-hidden": "true" }, root);
        var defs = el("defs", {}, svg);
        defs.innerHTML =
            '<linearGradient id="gmo' + u + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gm-s-ocean-a"/><stop offset="1" class="gm-s-ocean-b"/></linearGradient>' +
            '<linearGradient id="gml' + u + '" x1="0" y1="0" x2="1" y2="1"><stop offset="0" class="gm-s-land-a"/><stop offset="1" class="gm-s-land-b"/></linearGradient>' +
            '<filter id="gms' + u + '" x="-5%" y="-5%" width="110%" height="115%"><feGaussianBlur stdDeviation="1.6"/></filter>' +
            '<filter id="gmh' + u + '" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="3.2"/></filter>' +
            '<pattern id="gmp' + u + '" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><line x1="0" y1="0" x2="0" y2="3" class="gm-hatch"/></pattern>';
        el("rect", { x: 0, y: 0, width: W, height: H, fill: "url(#gmo" + u + ")" }, svg);
        this.gGrid = el("g", { "class": "gm-grid" }, svg);
        for (var lo = -180; lo <= 180; lo += 10) el("line", { x1: X(lo), y1: 0, x2: X(lo), y2: H, "class": (lo % 30 === 0 ? "gm-gl major" : "gm-gl minor") }, this.gGrid);
        for (var la = -90; la <= 90; la += 10) el("line", { x1: 0, y1: Y(la), x2: W, y2: Y(la), "class": (la === 0 ? "gm-gl equator" : la % 30 === 0 ? "gm-gl major" : "gm-gl minor") }, this.gGrid);
        [23.44, -23.44].forEach(function (la) { el("line", { x1: 0, y1: Y(la), x2: W, y2: Y(la), "class": "gm-gl tropic" }, self.gGrid); });
        this.gShelf = el("g", { "class": "gm-shelf", filter: "url(#gmh" + u + ")" }, svg);
        this.gShadow = el("g", { "class": "gm-shadow", filter: "url(#gms" + u + ")", transform: "translate(0.9 1.6)" }, svg);
        this.gLand = el("g", { "class": "gm-land" }, svg);
        this.gWater = el("g", { "class": "gm-water" }, svg);
        this.gFocus = el("g", { "class": "gm-focus" }, svg);
        this.gRoute = el("g", { "class": "gm-route" }, svg);
        this.drawLand();

        this.gridLabels = div("gm-gridlabels", root);
        this.cityLayer = div("gm-cities", root);
        this.pinLayer = div("gm-pins", root);
        this.routeLabel = div("gm-routelabel", root); this.routeLabel.style.display = "none";
        this.badge = div("gm-badge", root); this.badge.style.display = "none";
        this.tip = div("gm-tip", root); this.tip.style.display = "none";
        this.hint = div("gm-hint", root); this.hint.style.opacity = 0;
        this.legend = div("gm-legend", root);
        this.live = div("gm-sr", root); this.live.setAttribute("aria-live", "polite");
        var ctl = div("gm-controls", root);
        function btn(txt, label, fn) {
            var x = document.createElement("button");
            x.type = "button"; x.className = "gm-btn"; x.textContent = txt; x.setAttribute("aria-label", label); x.title = label;
            x.addEventListener("click", function (e) { e.stopPropagation(); fn(); });
            ctl.appendChild(x);
        }
        btn("+", "Zoom avant", function () { self.zoomBy(1.6); });
        btn("−", "Zoom arrière", function () { self.zoomBy(1 / 1.6); });
        btn("⌖", "Recentrer sur les points", function () { self.clearActive(); self.fit(true); });

        this.cityEls = (global.GEO_CITIES || []).map(function (c) {
            var d = div("gm-city r" + c.r, self.cityLayer, '<i></i><span>' + esc(c.n) + '</span>');
            return { c: c, e: d };
        });

        this.bind();
        this.measure();
        this.sizedOk = this.cw > 120;
        if (global.ResizeObserver) { this.ro = new ResizeObserver(function () { self.measure(); if (!self.sizedOk && self.cw > 120) { self.sizedOk = true; self.fit(false); } self.render(); }); this.ro.observe(b); }
    };
    Inst.prototype.drawLand = function () {
        var self = this, u = this.id;
        [this.gShelf, this.gShadow, this.gLand, this.gFocus].forEach(function (g) { while (g.firstChild) g.removeChild(g.firstChild); });
        var feats = realCountries && realCountries.length ? realCountries : land;
        this.features = {};
        feats.forEach(function (f) {
            var d = ringsPath(f.rings);
            el("path", { d: d, "class": "gm-shelf-p" }, self.gShelf);
            el("path", { d: d }, self.gShadow);
            self.features[f.id] = f; f.box = f.box || bbox(f.rings);
            var p = el("path", { d: d, "class": "gm-p gm-" + f.type, "data-rid": f.id, fill: "url(#gml" + u + ")" }, self.gLand);
            el("path", { d: d, "class": "gm-hatch-p", fill: "url(#gmp" + u + ")" }, self.gLand);
            p.setAttribute("vector-effect", "non-scaling-stroke");
        });
        if (!realCountries) {
            focus.forEach(function (f) {
                self.features[f.id] = f; f.box = f.box || bbox(f.rings);
                var p = el("path", { d: ringsPath(f.rings), "class": "gm-p gm-focus-p", "data-rid": f.id }, self.gFocus);
                p.setAttribute("vector-effect", "non-scaling-stroke");
            });
            (global.GEO_WATER || []).forEach(function (r) { el("path", { d: ringsPath([r]), "class": "gm-lake" }, self.gWater).setAttribute("vector-effect", "non-scaling-stroke"); });
        }
        if (this.active && !this.features[this.active]) this.active = null;
        this.applyClasses();
    };
    Inst.prototype.measure = function () {
        var r = this.root.getBoundingClientRect();
        this.cw = Math.max(r.width, 50); this.ch = Math.max(r.height, 50); this.aspect = this.cw / this.ch;
        this.root.classList.toggle('gm-narrow', this.cw < 440);
    };

    /* ---------- Vue (centre / largeur) ---------- */
    Inst.prototype.norm = function (v) {
        var w = clamp(v.w, MIN_W, W);
        if (w / this.aspect > H) w = H * this.aspect;
        var h = w / this.aspect;
        return { w: w, cx: clamp(v.cx, w / 2, W - w / 2), cy: clamp(v.cy, h / 2, H - h / 2) };
    };
    Inst.prototype.rect = function (v) { v = v || this.view; var h = v.w / this.aspect; return { x: v.cx - v.w / 2, y: v.cy - h / 2, w: v.w, h: h }; };
    Inst.prototype.toPx = function (x, y) { var r = this.rect(); return { x: (x - r.x) / r.w * this.cw, y: (y - r.y) / r.h * this.ch }; };
    Inst.prototype.flyTo = function (target, instant) {
        var self = this, to = this.norm(target), from = { cx: this.view.cx, cy: this.view.cy, w: this.view.w };
        if (this.anim) cancelAnimationFrame(this.anim);
        if (instant || reduce) { this.view = to; this.render(); return; }
        var t0 = performance.now(), dur = 520;
        (function step(t) {
            var k = clamp((t - t0) / dur, 0, 1), e = 1 - Math.pow(1 - k, 3);
            self.view = { cx: from.cx + (to.cx - from.cx) * e, cy: from.cy + (to.cy - from.cy) * e, w: Math.exp(Math.log(from.w) + (Math.log(to.w) - Math.log(from.w)) * e) };
            self.render();
            if (k < 1) self.anim = requestAnimationFrame(step); else self.anim = null;
        })(t0);
    };
    Inst.prototype.zoomBy = function (f, ax, ay) {
        var r = this.rect(), nx = ax == null ? this.view.cx : ax, ny = ay == null ? this.view.cy : ay;
        var w = clamp(this.view.w / f, MIN_W, W), k = w / this.view.w;
        this.flyTo({ w: w, cx: nx - (nx - this.view.cx) * k, cy: ny - (ny - this.view.cy) * k }, ax != null);
    };
    Inst.prototype.fitTarget = function (pts) {
        if (!pts.length) return { cx: W / 2, cy: H / 2 - 12, w: W };
        var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        pts.forEach(function (p) { x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); });
        var w = Math.max((x1 - x0) * 1.75, (y1 - y0) * 1.75 * this.aspect, 120);
        return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: w };
    };
    Inst.prototype.fit = function (animate) {
        var pts = this.pts();
        this.flyTo(this.fitTarget(pts), !animate);
    };
    Inst.prototype.pts = function () {
        var pts = this.pins.filter(function (p) { return typeof p.lat === "number" && typeof p.lon === "number"; }).map(function (p) { return { x: X(p.lon), y: Y(p.lat) }; });
        var r = this.opts.route;
        if (r && r.a && r.b) { pts.push({ x: X(r.a.lon), y: Y(r.a.lat) }); pts.push({ x: X(r.b.lon), y: Y(r.b.lat) }); }
        return pts;
    };

    /* ---------- Données (pins + route) ---------- */
    Inst.prototype.update = function (opts) {
        var self = this, first = !this.ready;
        this.opts = Object.assign({}, this.opts, opts || {});
        this.pins = (this.opts.pins || []).filter(function (p) { return typeof p.lat === "number" && typeof p.lon === "number"; });
        var missing = (this.opts.pins || []).length - this.pins.length;
        this.pinLayer.innerHTML = ""; this.pinEls = {};
        this.pins.forEach(function (p, i) {
            var b = document.createElement("button");
            b.type = "button"; b.className = "gm-pin gm-k-" + (p.kind || "cluster") + (p.id === self.opts.selectedId ? " is-selected" : "");
            b.setAttribute("aria-label", p.label + (p.sub ? " : " + p.sub : ""));
            if (p.kind === "cluster" || !p.kind) b.setAttribute("aria-pressed", p.id === self.opts.selectedId ? "true" : "false");
            var dot = p.kind === "you" ? "" : p.kind === "offer" ? "" : esc(p.count != null ? p.count : "");
            b.innerHTML = '<span class="gm-pulse"></span><span class="gm-dot">' + dot + '</span><span class="gm-label"><b>' + esc(p.label) + '</b>' + (p.sub ? '<small>' + esc(p.sub) + '</small>' : '') + '</span>';
            b.addEventListener("click", function (e) {
                e.stopPropagation();
                if (self.opts.onPinClick) self.opts.onPinClick(p.id, p);
            });
            b.addEventListener("focus", function () { b.classList.add("show-label"); });
            b.addEventListener("blur", function () { b.classList.remove("show-label"); });
            self.pinLayer.appendChild(b);
            self.pinEls[p.id] = { e: b, p: p, i: i };
        });
        this.drawRoute();
        this.drawLegend(missing);
        this.ready = true;
        if (first || this.opts.refit) this.fit(false);
        this.render();
    };
    Inst.prototype.drawRoute = function () {
        var g = this.gRoute, r = this.opts.route; g.innerHTML = "";
        this.routeLabel.style.display = "none";
        if (!r || !r.a || !r.b) { this.routeGeom = null; return; }
        var ax = X(r.a.lon), ay = Y(r.a.lat), bx = X(r.b.lon), by = Y(r.b.lat);
        var mx = (ax + bx) / 2, my = (ay + by) / 2, dx = bx - ax, dy = by - ay, len = Math.sqrt(dx * dx + dy * dy) || 1;
        var off = Math.min(len * 0.22, 40) * (dx >= 0 ? -1 : 1);
        var cx = mx + (-dy / len) * off, cy = my + (dx / len) * off - Math.min(len * 0.08, 14);
        this.routeGeom = { mx: 0.25 * ax + 0.5 * cx + 0.25 * bx, my: 0.25 * ay + 0.5 * cy + 0.25 * by };
        var d = "M" + ax.toFixed(1) + " " + ay.toFixed(1) + "Q" + cx.toFixed(1) + " " + cy.toFixed(1) + " " + bx.toFixed(1) + " " + by.toFixed(1);
        var halo = el("path", { d: d, "class": "gm-route-halo" }, g); halo.setAttribute("vector-effect", "non-scaling-stroke");
        var line = el("path", { d: d, "class": "gm-route-line" }, g); line.setAttribute("vector-effect", "non-scaling-stroke");
        if (!reduce) {
            var dot = el("circle", { r: 1.6, "class": "gm-route-dot" }, g);
            var am = el("animateMotion", { dur: "3.6s", repeatCount: "indefinite", path: d }, dot);
        }
        var km = r.km != null ? r.km : haversine(r.a, r.b);
        this.routeLabel.textContent = r.label || (fmt(km) + " km");
        this.routeLabel.style.display = "";
    };
    Inst.prototype.drawLegend = function (missing) {
        var kinds = {};
        this.pins.forEach(function (p) { kinds[p.kind || "cluster"] = 1; });
        var h = "";
        if (kinds.cluster) h += '<span><i class="gm-lg cluster"></i>Candidats par ville</span>';
        if (kinds.you) h += '<span><i class="gm-lg you"></i>Vous</span>';
        if (kinds.offer) h += '<span><i class="gm-lg offer"></i>Offre</span>';
        if (missing > 0) h += '<span class="gm-miss">' + missing + ' lieu(x) non localisé(s)</span>';
        this.legend.innerHTML = h; this.legend.style.display = h ? "" : "none";
    };

    /* ---------- Rendu (positions des éléments HTML selon la vue) ---------- */
    Inst.prototype.render = function () {
        var r = this.rect(), self = this, scale = W / this.view.w;
        this.svg.setAttribute("viewBox", r.x.toFixed(2) + " " + r.y.toFixed(2) + " " + r.w.toFixed(2) + " " + r.h.toFixed(2));
        this.root.classList.toggle("gm-zoomed", scale > 1.15);
        this.root.classList.toggle("gm-z2", scale >= 2);
        this.root.classList.toggle("gm-z4", scale >= 4);

        // Étiquettes de grille
        var step = scale >= 4 ? 10 : scale >= 2 ? 20 : 30, gl = "", lat, lon, p;
        for (lat = -60; lat <= 60; lat += step) { p = this.toPx(0, Y(lat)); if (p.y > 18 && p.y < this.ch - 18) gl += '<span class="gm-gl-lat" style="top:' + p.y.toFixed(0) + 'px">' + Math.abs(lat) + '°' + (lat > 0 ? "N" : lat < 0 ? "S" : "") + '</span>'; }
        for (lon = -180 + step * (scale >= 2 ? 0 : 1); lon <= 180; lon += step * (scale >= 2 ? 1 : 2)) { p = this.toPx(X(lon), 0); if (p.x > 28 && p.x < this.cw - 60) gl += '<span class="gm-gl-lon" style="left:' + p.x.toFixed(0) + 'px">' + Math.abs(lon) + '°' + (lon > 0 ? "E" : lon < 0 ? "O" : "") + '</span>'; }
        this.gridLabels.innerHTML = gl;

        // Pins + anti-chevauchement des étiquettes
        var order = Object.keys(this.pinEls).map(function (k) { return self.pinEls[k]; });
        order.sort(function (a, b) { return (b.p.priority || b.p.count || 0) - (a.p.priority || a.p.count || 0); });
        var boxes = [], pinPx = [], dots = [];
        order.forEach(function (o) {
            var q = self.toPx(X(o.p.lon), Y(o.p.lat)), vis = q.x > -30 && q.x < self.cw + 30 && q.y > -30 && q.y < self.ch + 30, tries = 0;
            while (tries++ < 6 && dots.some(function (d) { return Math.abs(d.x - q.x) < 20 && Math.abs(d.y - q.y) < 20; })) { q = { x: q.x + 15, y: q.y - 17 }; }
            o.q = q; dots.push({ x: q.x, y: q.y, o: o });
        });
        order.forEach(function (o) {
            var q = o.q, vis = q.x > -30 && q.x < self.cw + 30 && q.y > -30 && q.y < self.ch + 30;
            o.e.style.display = vis ? "" : "none";
            o.e.style.transform = "translate(" + q.x.toFixed(1) + "px," + q.y.toFixed(1) + "px)";
            pinPx.push(q);
            if (!vis) return;
            var longest = Math.max(String(o.p.label).length * 6.4, (self.root.classList.contains('gm-narrow') ? 0 : String(o.p.sub || '').length * 5.4)), wLab = Math.min(190, 22 + longest), roomR = self.cw - q.x - 34, flip = roomR < wLab && q.x > roomR;
            var rc = flip ? { x0: q.x - 16 - wLab, x1: q.x - 12, y0: q.y - 11, y1: q.y + 11 } : { x0: q.x + 12, x1: q.x + 16 + wLab, y0: q.y - 11, y1: q.y + 11 };
            var hit = boxes.some(function (b) { return !(rc.x1 < b.x0 || rc.x0 > b.x1 || rc.y1 < b.y0 || rc.y0 > b.y1); }) ||
                dots.some(function (d) { return d.o !== o && !(rc.x1 < d.x - 13 || rc.x0 > d.x + 13 || rc.y1 < d.y - 13 || rc.y0 > d.y + 13); });
            var sel = o.p.id === self.opts.selectedId || o.p.kind === "you" || o.p.kind === "offer";
            o.e.classList.toggle("flip", flip);
            o.e.classList.toggle("label-off", hit && !sel);
            if (!hit || sel) boxes.push(rc);
        });

        // Villes de référence
        this.cityEls.forEach(function (o) {
            var q = self.toPx(X(o.c.lon), Y(o.c.lat)), need = o.c.r === 1 ? 1.7 : 3.6;
            var vis = scale >= need && q.x > 8 && q.x < self.cw - 8 && q.y > 8 && q.y < self.ch - 8;
            if (vis) vis = !pinPx.some(function (pp) { return Math.abs(pp.x - q.x) < 22 && Math.abs(pp.y - q.y) < 16; });
            o.e.style.display = vis ? "" : "none";
            if (vis) o.e.style.transform = "translate(" + q.x.toFixed(1) + "px," + q.y.toFixed(1) + "px)";
        });

        if (this.routeGeom) { var m = this.toPx(this.routeGeom.mx, this.routeGeom.my); this.routeLabel.style.transform = "translate(" + m.x.toFixed(1) + "px," + m.y.toFixed(1) + "px)"; }
    };

    /* ---------- Régions : survol / sélection ---------- */
    Inst.prototype.applyClasses = function () {
        var self = this;
        this.svg.querySelectorAll("[data-rid]").forEach(function (p) {
            var id = p.getAttribute("data-rid");
            p.classList.toggle("is-hover", id === self.hover);
            p.classList.toggle("is-active", id === self.active);
        });
        if (!this.badge) return;
        var f = this.active && this.features[this.active];
        if (f) { this.badge.style.display = ""; this.badge.innerHTML = '<b>' + esc(f.name) + '</b><span>' + esc(f.info || "") + '</span><button type="button" aria-label="Désélectionner">×</button>'; var self2 = this; this.badge.querySelector("button").onclick = function () { self2.clearActive(); self2.fit(true); }; }
        else this.badge.style.display = "none";
    };
    Inst.prototype.setHover = function (id, ev) {
        if (id === this.hover) { if (id) this.moveTip(ev); return; }
        this.hover = id; this.applyClasses();
        var f = id && this.features[id];
        if (!f) { this.tip.style.display = "none"; return; }
        this.tip.innerHTML = '<b>' + esc(f.name) + '</b><span>' + esc(f.info || "") + '</span>';
        this.tip.style.display = ""; this.moveTip(ev);
    };
    Inst.prototype.moveTip = function (ev) {
        if (!ev) return;
        var r = this.root.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
        var tw = this.tip.offsetWidth || 120;
        this.tip.style.transform = "translate(" + clamp(x + 14, 6, this.cw - tw - 6).toFixed(0) + "px," + clamp(y + 16, 6, this.ch - 50).toFixed(0) + "px)";
    };
    Inst.prototype.selectRegion = function (id) {
        var f = this.features[id]; if (!f) return;
        if (this.active === id) { this.clearActive(); this.fit(true); return; }
        this.active = id; this.applyClasses();
        this.live.textContent = f.name + " sélectionné";
        var b = f.box, cx = (b.x0 + b.x1) / 2, cy = (b.y0 + b.y1) / 2;
        this.flyTo({ cx: cx, cy: cy, w: Math.max((b.x1 - b.x0) * 1.5, (b.y1 - b.y0) * 1.5 * this.aspect, 70) });
    };
    Inst.prototype.clearActive = function () { this.active = null; this.applyClasses(); };

    /* ---------- Interactions : souris, tactile, clavier ---------- */
    Inst.prototype.bind = function () {
        var self = this, svg = this.root;
        svg.addEventListener("pointerdown", function (e) {
            if (e.target.closest(".gm-pin,.gm-controls,.gm-badge")) return;
            self.pointers[e.pointerId] = { x: e.clientX, y: e.clientY, t: e.target };
            self.moved = false; self.start = { x: e.clientX, y: e.clientY };
            self.pinch = null;
            if (e.pointerType !== "touch" || self.root.classList.contains("gm-zoomed")) { try { svg.setPointerCapture(e.pointerId); } catch (x) {} }
            if (self.anim) { cancelAnimationFrame(self.anim); self.anim = null; }
        });
        svg.addEventListener("pointermove", function (e) {
            var P = self.pointers[e.pointerId];
            if (!P) { if (e.pointerType !== "touch") { var t = e.target.closest && e.target.closest("[data-rid]"); self.setHover(t ? t.getAttribute("data-rid") : null, e); } return; }
            var ids = Object.keys(self.pointers);
            if (ids.length === 2) {
                var a = self.pointers[ids[0]], b = self.pointers[ids[1]];
                if (a === P) { a.x = e.clientX; a.y = e.clientY; } else { b.x = e.clientX; b.y = e.clientY; }
                var dist = Math.hypot(a.x - b.x, a.y - b.y);
                if (self.pinch) { var rr = self.root.getBoundingClientRect(), r = self.rect(); self.view = self.norm({ w: self.view.w * self.pinch / dist, cx: self.view.cx, cy: self.view.cy }); self.render(); }
                self.pinch = dist; self.moved = true; return;
            }
            var dx = e.clientX - P.x, dy = e.clientY - P.y;
            if (!self.moved && Math.hypot(e.clientX - self.start.x, e.clientY - self.start.y) < 5) return;
            if (e.pointerType === "touch" && !self.root.classList.contains("gm-zoomed")) return;
            self.moved = true; self.root.classList.add("gm-dragging");
            var r2 = self.rect();
            self.view = self.norm({ w: self.view.w, cx: self.view.cx - dx * r2.w / self.cw, cy: self.view.cy - dy * r2.h / self.ch });
            P.x = e.clientX; P.y = e.clientY; self.render();
        });
        function up(e) {
            var P = self.pointers[e.pointerId]; if (!P) return;
            delete self.pointers[e.pointerId]; self.pinch = null; self.root.classList.remove("gm-dragging");
            if (!self.moved && Object.keys(self.pointers).length === 0) {
                var t = document.elementFromPoint(e.clientX, e.clientY), reg = t && t.closest ? t.closest("[data-rid]") : null;
                if (reg) self.selectRegion(reg.getAttribute("data-rid")); else if (self.active) { self.clearActive(); self.fit(true); }
            }
        }
        svg.addEventListener("pointerup", up); svg.addEventListener("pointercancel", up);
        svg.addEventListener("pointerleave", function (e) { if (!self.pointers[e.pointerId]) self.setHover(null); });
        svg.addEventListener("wheel", function (e) {
            if (!(e.ctrlKey || e.metaKey)) { self.showHint("Ctrl + molette pour zoomer"); return; }
            e.preventDefault();
            var r = self.rect(), bx = svg.getBoundingClientRect();
            var ax = r.x + (e.clientX - bx.left) / self.cw * r.w, ay = r.y + (e.clientY - bx.top) / self.ch * r.h;
            self.zoomBy(e.deltaY < 0 ? 1.35 : 1 / 1.35, ax, ay);
        }, { passive: false });
        svg.addEventListener("dblclick", function (e) {
            if (e.target.closest(".gm-pin,.gm-controls")) return;
            var r = self.rect(), bx = svg.getBoundingClientRect();
            self.zoomBy(1.8, r.x + (e.clientX - bx.left) / self.cw * r.w, r.y + (e.clientY - bx.top) / self.ch * r.h);
        });
        svg.addEventListener("keydown", function (e) {
            if (e.target !== svg) return;
            var k = e.key, r = self.rect(), s = r.w * 0.15, h = true;
            if (k === "+" || k === "=") self.zoomBy(1.6);
            else if (k === "-" || k === "_") self.zoomBy(1 / 1.6);
            else if (k === "0") { self.clearActive(); self.fit(true); }
            else if (k === "ArrowLeft") self.flyTo({ w: self.view.w, cx: self.view.cx - s, cy: self.view.cy });
            else if (k === "ArrowRight") self.flyTo({ w: self.view.w, cx: self.view.cx + s, cy: self.view.cy });
            else if (k === "ArrowUp") self.flyTo({ w: self.view.w, cx: self.view.cx, cy: self.view.cy - s });
            else if (k === "ArrowDown") self.flyTo({ w: self.view.w, cx: self.view.cx, cy: self.view.cy + s });
            else if (k === "Escape") { self.clearActive(); self.fit(true); }
            else h = false;
            if (h) e.preventDefault();
        });
    };
    Inst.prototype.showHint = function (t) {
        var self = this; this.hint.textContent = t; this.hint.style.opacity = 1;
        clearTimeout(this.hintT); this.hintT = setTimeout(function () { self.hint.style.opacity = 0; }, 1400);
    };
    Inst.prototype.destroy = function () {
        if (this.ro) this.ro.disconnect();
        if (this.anim) cancelAnimationFrame(this.anim);
        var i = instances.indexOf(this); if (i >= 0) instances.splice(i, 1);
        this.box._gm = null;
    };

    var GeoMap = {
        mount: function (box, opts) {
            if (!box) return null;
            var old = box._gm;
            if (old && box.contains(old.root)) { old.update(opts); return old; }
            if (old) old.destroy();
            var inst = new Inst(box, opts); box._gm = inst; return inst;
        },
        loadCountries: loadCountries,
        haversine: haversine
    };
    global.GeoMap = GeoMap;
    if (document.readyState !== "loading") loadCountries("/static/data/world.geojson");
    else document.addEventListener("DOMContentLoaded", function () { loadCountries("/static/data/world.geojson"); });
})(window);
