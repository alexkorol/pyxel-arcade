// Pyxel Arcade — catalog + in-page player.
// All game data lives in demos/manifest.json; demos run via the Pyxel Web
// Launcher, which loads each .py straight from this repo (master resolves to
// the latest commit, so pushed updates are playable immediately).

(function () {
    'use strict';

    var state = {
        manifest: null,
        games: [],
        activeTags: new Set(),
        query: '',
        sort: 'newest',
        randomOrder: null,
    };

    var el = {
        arcade: document.getElementById('view-arcade'),
        play: document.getElementById('view-play'),
        grid: document.getElementById('game-grid'),
        chips: document.getElementById('tag-chips'),
        search: document.getElementById('search'),
        sort: document.getElementById('sort'),
        surprise: document.getElementById('surprise'),
        count: document.getElementById('result-count'),
        playTitle: document.getElementById('play-title'),
        playFrame: document.getElementById('play-frame'),
        playControls: document.getElementById('play-controls'),
        playDesc: document.getElementById('play-desc'),
        playTags: document.getElementById('play-tags'),
        playCode: document.getElementById('play-code'),
        playFullscreen: document.getElementById('play-fullscreen'),
        playShare: document.getElementById('play-share'),
    };

    // ---- data ------------------------------------------------------

    fetch('demos/manifest.json')
        .then(function (r) {
            if (!r.ok) throw new Error('manifest fetch failed: ' + r.status);
            return r.json();
        })
        .then(function (manifest) {
            state.manifest = manifest;
            state.games = manifest.games;
            buildTagChips();
            bindToolbar();
            buildDailyBanner();
            window.addEventListener('hashchange', route);
            route();
        })
        .catch(function (err) {
            el.grid.innerHTML = '<p class="empty-note">Could not load the game list (' +
                escapeHtml(String(err.message || err)) + '). Try refreshing.</p>';
        });

    function findGame(slug) {
        return state.games.find(function (g) { return g.slug === slug; });
    }

    // ---- local play stats & daily challenge -------------------------

    function loadPlays() {
        try { return JSON.parse(localStorage.getItem('arcade.plays')) || {}; }
        catch (e) { return {}; }
    }

    function trackPlay(slug) {
        var plays = loadPlays();
        var rec = plays[slug] || { n: 0 };
        rec.n += 1;
        rec.last = Date.now();
        plays[slug] = rec;
        try { localStorage.setItem('arcade.plays', JSON.stringify(plays)); } catch (e) {}
    }

    function todayKey() {
        var d = new Date();
        return d.getUTCFullYear() * 10000 + (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
    }

    // Everyone who visits on the same (UTC) day gets the same cartridge and,
    // for seed-aware games, the same world seed.
    function dailyGame() {
        var seeded = state.games.filter(function (g) { return g.seeded; });
        var pool = seeded.length ? seeded : state.games;
        return pool[todayKey() % pool.length];
    }

    function codeUrl(game) {
        return state.manifest.repo + '/blob/master/demos/' + game.slug + '.py';
    }

    // ---- routing ---------------------------------------------------

    function route() {
        var hash = location.hash || '#/';
        if (/^#\/daily\b/.test(hash)) {
            showPlay(dailyGame(), { seed: todayKey(), daily: true });
            return;
        }
        var m = hash.match(/^#\/game\/([a-z0-9_]+)/);
        var game = m ? findGame(m[1]) : null;
        if (game) {
            showPlay(game);
        } else {
            if (m) location.hash = '#/'; // unknown slug: fall back to grid
            showArcade();
        }
    }

    function showArcade() {
        // Drop the iframe src so the game (and its audio) actually stops.
        el.playFrame.removeAttribute('src');
        el.play.hidden = true;
        el.arcade.hidden = false;
        document.title = 'Pyxel Arcade';
        render();
    }

    function showPlay(game, opts) {
        opts = opts || {};
        el.arcade.hidden = true;
        el.play.hidden = false;
        document.title = game.title + ' — Pyxel Arcade';

        el.playTitle.textContent = opts.daily
            ? game.title + ' — daily world'
            : game.title;
        el.playDesc.textContent = opts.daily
            ? 'Today’s shared seed: everyone forging the daily world gets this exact one. ' +
              game.description
            : game.description;
        el.playCode.href = codeUrl(game);

        el.playControls.innerHTML = game.controls.map(function (pair) {
            return '<tr><td>' + escapeHtml(pair[0]) + '</td><td>' +
                escapeHtml(pair[1]) + '</td></tr>';
        }).join('');

        el.playTags.innerHTML = game.tags.map(function (t) {
            return '<span class="chip">' + escapeHtml(t) + '</span>';
        }).join('');

        var src = state.manifest.launcher + game.slug;
        if (opts.seed) src += '&seed=' + opts.seed;
        if (el.playFrame.getAttribute('src') !== src) {
            el.playFrame.setAttribute('src', src);
            trackPlay(game.slug);
        }
        window.scrollTo(0, 0);
    }

    el.playFullscreen.addEventListener('click', function () {
        var frame = el.playFrame;
        if (frame.requestFullscreen) frame.requestFullscreen();
        else if (frame.webkitRequestFullscreen) frame.webkitRequestFullscreen();
    });

    // Share links point at the static OG page (games/<slug>.html) so the
    // pasted URL unfurls with a preview image; it redirects humans back here.
    el.playShare.addEventListener('click', function () {
        var base = location.href.split('#')[0].replace(/index\.html$/, '');
        var url;
        if (/^#\/daily\b/.test(location.hash)) {
            url = base + '#/daily';
        } else {
            var m = location.hash.match(/^#\/game\/([a-z0-9_]+)/);
            if (!m) return;
            url = base + 'games/' + m[1] + '.html';
        }
        var done = function () {
            el.playShare.textContent = 'copied!';
            setTimeout(function () { el.playShare.textContent = 'share'; }, 1500);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url).then(done, function () {
                prompt('Copy this link:', url);
            });
        } else {
            prompt('Copy this link:', url);
        }
    });

    // ---- toolbar ---------------------------------------------------

    function buildTagChips() {
        var tags = new Set();
        state.games.forEach(function (g) {
            g.tags.forEach(function (t) { tags.add(t); });
        });
        el.chips.innerHTML = '';
        Array.from(tags).sort().forEach(function (tag) {
            var chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'chip';
            chip.textContent = tag;
            chip.addEventListener('click', function () {
                if (state.activeTags.has(tag)) state.activeTags.delete(tag);
                else state.activeTags.add(tag);
                chip.classList.toggle('on');
                render();
            });
            el.chips.appendChild(chip);
        });
    }

    function bindToolbar() {
        el.search.addEventListener('input', function () {
            state.query = el.search.value.trim().toLowerCase();
            render();
        });
        el.sort.addEventListener('change', function () {
            state.sort = el.sort.value;
            if (state.sort === 'random') state.randomOrder = null;
            render();
        });
        el.surprise.addEventListener('click', function () {
            var pool = visibleGames();
            if (!pool.length) pool = state.games;
            var pick = pool[Math.floor(Math.random() * pool.length)];
            location.hash = '#/game/' + pick.slug;
        });
    }

    function buildDailyBanner() {
        var banner = document.getElementById('daily-banner');
        var game = dailyGame();
        if (!game) return;
        banner.innerHTML = '<span class="daily-label">daily world</span> ' +
            escapeHtml(game.title) +
            ' <span class="daily-sub">— same seed for everyone today. can your legends beat theirs?</span>';
        banner.hidden = false;
    }

    // ---- grid rendering --------------------------------------------

    function visibleGames() {
        return state.games.filter(function (g) {
            if (state.activeTags.size) {
                var hasAll = Array.from(state.activeTags).every(function (t) {
                    return g.tags.indexOf(t) !== -1;
                });
                if (!hasAll) return false;
            }
            if (state.query) {
                var hay = (g.title + ' ' + g.description + ' ' + g.tags.join(' ')).toLowerCase();
                if (hay.indexOf(state.query) === -1) return false;
            }
            return true;
        });
    }

    function sortGames(list) {
        var out = list.slice();
        if (state.sort === 'alpha') {
            out.sort(function (a, b) { return a.title.localeCompare(b.title); });
        } else if (state.sort === 'random') {
            if (!state.randomOrder) {
                state.randomOrder = {};
                state.games.forEach(function (g) {
                    state.randomOrder[g.slug] = Math.random();
                });
            }
            var order = state.randomOrder;
            out.sort(function (a, b) { return order[a.slug] - order[b.slug]; });
        } else { // newest
            out.sort(function (a, b) { return b.added.localeCompare(a.added); });
        }
        return out;
    }

    function render() {
        var list = sortGames(visibleGames());
        el.count.textContent = list.length === state.games.length
            ? state.games.length + ' cartridges'
            : list.length + ' of ' + state.games.length + ' cartridges';

        if (!list.length) {
            el.grid.innerHTML = '<p class="empty-note">Nothing matches — clear a filter or two.</p>';
            return;
        }

        el.grid.innerHTML = list.map(cardHtml).join('');
    }

    function cardHtml(game) {
        var playHref = '#/game/' + game.slug;
        var tags = game.tags.map(function (t) {
            return '<span class="tag">' + escapeHtml(t) + '</span>';
        }).join('');
        if (game.touch) tags += '<span class="tag tag-touch">touch ok</span>';
        var rec = loadPlays()[game.slug];
        if (rec && rec.n) {
            tags += '<span class="tag tag-played">played ×' + rec.n + '</span>';
        }

        return '<article class="game-card">' +
            '<a class="card-thumb" href="' + playHref + '" aria-label="Play ' + escapeHtml(game.title) + '">' +
            '<img src="demos/' + game.slug + '.webp" ' +
            'onerror="this.onerror=null;this.src=\'demos/' + game.slug + '.png\'" ' +
            'alt="' + escapeHtml(game.title) + ' screenshot" loading="lazy">' +
            '</a>' +
            '<div class="card-body">' +
            '<h2 class="card-title"><a href="' + playHref + '">' + escapeHtml(game.title) + '</a></h2>' +
            '<p class="card-desc">' + escapeHtml(game.description) + '</p>' +
            '<div class="card-meta">' + tags + '</div>' +
            '<div class="card-links">' +
            '<a href="' + playHref + '">play</a>' +
            '<a href="' + codeUrl(game) + '" target="_blank" rel="noopener">code</a>' +
            '</div></div></article>';
    }

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
})();
