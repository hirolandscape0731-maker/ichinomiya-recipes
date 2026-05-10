/* 一宮市 給食レシピアプリ — vanilla JS, no build step */
(function () {
  "use strict";

  const RECIPES = window.RECIPES || [];
  const MENUS = window.MENUS || [];
  const FAV_KEY = "ichinomiya-fav-v1";
  const ICONS = {
    "汁物": "🍲",
    "煮物・いため物・丼物": "🍚",
    "揚げ物": "🍤",
    "焼き物": "🔥",
    "和え物（サラダ）": "🥗",
    "ソース・タレ": "🥄",
    "最新のレシピ": "✨",
  };

  // Synonym dictionary: alternate names → canonical menu spelling
  // Menu PDFs use hiragana primarily.
  const SYNONYMS = {
    "ほうれん草": ["ほうれんそう"],
    "ホウレンソウ": ["ほうれんそう"],
    "コーン": ["とうもろこし", "コーン"],
    "とうもろこし": ["とうもろこし", "コーン"],
    "人参": ["にんじん"],
    "玉ねぎ": ["たまねぎ"],
    "たまねぎ": ["たまねぎ"],
    "じゃが芋": ["じゃがいも"],
    "じゃがいも": ["じゃがいも"],
    "豚肉": ["ぶたにく"],
    "鶏肉": ["とりにく", "けいにく"],
    "牛肉": ["ぎゅうにく"],
    "卵": ["たまご"],
    "豆腐": ["とうふ"],
    "わかめ": ["わかめ"],
    "ねぎ": ["ねぎ"],
    "白菜": ["はくさい"],
    "大根": ["だいこん"],
    "きゅうり": ["きゅうり"],
    "キャベツ": ["キャベツ", "きゃべつ"],
    "ナス": ["なす"],
    "なす": ["なす"],
    "もやし": ["もやし"],
    "トマト": ["トマト"],
    "ブロッコリー": ["ブロッコリー"],
    "鯖": ["さば"],
    "鮭": ["さけ"],
    "ひじき": ["ひじき"],
    "大豆": ["だいず"],
    "ごぼう": ["ごぼう"],
    "切り干し大根": ["きりぼしだいこん", "切干しだいこん", "切干だいこん"],
  };

  /* --- State --- */
  const state = {
    query: "",
    category: "all",
    selected: null,
    view: "list", // "list" | "detail" | "menu"
  };
  const favs = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]"));

  function saveFavs() { localStorage.setItem(FAV_KEY, JSON.stringify([...favs])); }
  function toggleFav(id) {
    if (favs.has(id)) favs.delete(id); else favs.add(id);
    saveFavs();
  }

  /* --- Helpers --- */
  function iconFor(category) { return ICONS[category] || "🍽️"; }
  function cardMediaHTML(r) {
    if (r.photo) {
      return `<img class="card-photo" src="${escapeAttr(r.photo)}" alt="${escapeAttr(r.name)}" loading="lazy">`;
    }
    return `<div class="card-icon">${iconFor(r.category)}</div>`;
  }
  function categories() {
    const set = new Set();
    for (const r of RECIPES) set.add(r.category);
    return [...set];
  }
  function matchesQuery(r, q) {
    if (!q) return true;
    const hay = (
      r.name + " " + r.category + " " +
      (r.ingredients || []).map((i) => i.name).join(" ") + " " +
      (r.raw_text || "")
    ).toLowerCase();
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    return terms.every((t) => hay.includes(t));
  }
  function filteredRecipes() {
    return RECIPES.filter((r) => {
      if (state.category === "favorites") {
        if (!favs.has(r.id)) return false;
      } else if (state.category !== "all") {
        if (r.category !== state.category) return false;
      }
      return matchesQuery(r, state.query);
    });
  }

  /* --- DOM refs --- */
  const $list = document.getElementById("recipe-list");
  const $count = document.getElementById("result-count");
  const $empty = document.getElementById("empty-state");
  const $filterBar = document.getElementById("filter-bar");
  const $listView = document.getElementById("list-view");
  const $detailView = document.getElementById("detail-view");
  const $menuView = document.getElementById("menu-view");
  const $detailContent = document.getElementById("detail-content");
  const $backBtn = document.getElementById("back-btn");
  const $favTab = document.getElementById("fav-tab");
  const $menuTab = document.getElementById("menu-tab");
  const $search = document.getElementById("search-input");
  const $clearBtn = document.getElementById("clear-search");

  /* --- Recipe list rendering --- */
  function renderFilters() {
    const cats = categories();
    const items = [
      { key: "all", label: "すべて" },
      ...cats.map((c) => ({ key: c, label: c })),
    ];
    $filterBar.innerHTML = "";
    for (const it of items) {
      const btn = document.createElement("button");
      btn.className = "chip" + (state.category === it.key ? " active" : "");
      btn.textContent = it.label;
      btn.addEventListener("click", () => {
        state.category = it.key;
        renderFilters();
        renderList();
      });
      $filterBar.appendChild(btn);
    }
  }
  function renderList() {
    const items = filteredRecipes();
    $count.textContent = `${items.length} 件のレシピ`;
    $list.innerHTML = "";
    if (items.length === 0) {
      $empty.hidden = false;
      return;
    }
    $empty.hidden = true;
    for (const r of items) {
      const li = document.createElement("li");
      li.className = "recipe-card";
      li.tabIndex = 0;
      li.innerHTML = `
        <button class="card-fav ${favs.has(r.id) ? "is-fav" : ""}" aria-label="お気に入り" data-id="${r.id}">★</button>
        ${cardMediaHTML(r)}
        <div class="card-name">${escapeHTML(r.name)}</div>
        <div class="card-meta">${escapeHTML(r.category)}</div>
      `;
      li.addEventListener("click", (e) => {
        if (e.target.classList.contains("card-fav")) return;
        showDetail(r);
      });
      li.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          showDetail(r);
        }
      });
      const favBtn = li.querySelector(".card-fav");
      favBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFav(r.id);
        favBtn.classList.toggle("is-fav");
      });
      $list.appendChild(li);
    }
  }

  function renderDetail(r) {
    const isFav = favs.has(r.id);
    const hasIngredients = (r.ingredients && r.ingredients.length > 0);
    const hasSteps = (r.instructions && r.instructions.length > 0);

    const detailMedia = r.photo
      ? `<img class="detail-photo" src="${escapeAttr(r.photo)}" alt="${escapeAttr(r.name)}">`
      : `<div class="detail-icon">${iconFor(r.category)}</div>`;
    let html = `
      ${detailMedia}
      <h2 class="detail-title">${escapeHTML(r.name)}</h2>
      <div class="detail-tags">
        <span class="tag section">${escapeHTML(r.category)}</span>
        ${r.servings ? `<span class="tag">${escapeHTML(r.servings)}</span>` : ""}
        ${r.date_jp ? `<span class="tag">${escapeHTML(r.date_jp)}</span>` : ""}
      </div>
      <button class="fav-large ${isFav ? "is-fav" : ""}" id="detail-fav">
        ${isFav ? "★ お気に入り解除" : "☆ お気に入りに追加"}
      </button>
    `;
    if (!hasIngredients && !hasSteps) {
      html += `
        <div class="parse-warning">
          このレシピは画像形式のPDFのため、テキスト抽出ができませんでした。
          下のボタンから元のPDFをご覧ください。
        </div>`;
    } else {
      if (hasIngredients) {
        html += `<h3 class="section-h">材料 ${r.servings ? `<span class="serving-note">(${escapeHTML(r.servings)})</span>` : ""}</h3>`;
        html += `<ul class="ingredients-list">`;
        let lastGroup = "";
        for (const ing of r.ingredients) {
          if (ing.group && ing.group !== lastGroup) {
            html += `<li class="ing-group">${escapeHTML(ing.group)}</li>`;
            lastGroup = ing.group;
          }
          html += `<li><span class="ing-name">${escapeHTML(ing.name)}</span><span class="ing-amount">${escapeHTML(ing.amount || "")}</span></li>`;
        }
        html += `</ul>`;
      }
      if (hasSteps) {
        html += `<h3 class="section-h">作り方</h3><ol class="steps-list">`;
        for (const step of r.instructions) html += `<li>${escapeHTML(step)}</li>`;
        html += `</ol>`;
      }
      if (r.notes) {
        html += `<h3 class="section-h">メモ</h3><div class="notes-box">${escapeHTML(r.notes)}</div>`;
      }
    }
    html += `<a href="${escapeAttr(r.pdf_url)}" target="_blank" rel="noopener" class="pdf-btn">📄 元のPDFを開く</a>`;
    $detailContent.innerHTML = html;

    document.getElementById("detail-fav").addEventListener("click", () => {
      toggleFav(r.id);
      renderDetail(r);
    });
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  /* --- Menu matching feature --- */
  function expandTerm(term) {
    const t = term.trim();
    if (!t) return [];
    const expansions = SYNONYMS[t] || [];
    const all = new Set([t, ...expansions]);
    return [...all];
  }

  function findRecipeForDish(dishName) {
    if (!dishName) return null;
    const dn = dishName.replace(/[（(].*?[)）]/g, "").trim();
    let best = null;
    let bestScore = 0;
    for (const r of RECIPES) {
      const rn = r.name;
      let score = 0;
      if (rn === dn) score = 100;
      else if (rn.includes(dn) || dn.includes(rn)) score = Math.min(rn.length, dn.length);
      if (score > bestScore) { bestScore = score; best = r; }
    }
    // Require at least 4-char containment to avoid false positives
    return bestScore >= 4 ? best : null;
  }

  function searchMenu({ date, schoolType, ingredients }) {
    const terms = ingredients.split(/\s+/).filter(Boolean);
    const expandedTerms = terms.map(expandTerm);
    const results = [];
    for (const day of MENUS) {
      if (date && day.date !== date) continue;
      if (schoolType) {
        // schoolType filter: 小学校 wants 小学校 OR 共通; 中学校 wants 中学校 OR 共通
        if (schoolType === "小学校" && !["小学校", "共通"].includes(day.school_type)) continue;
        if (schoolType === "中学校" && !["中学校", "共通"].includes(day.school_type)) continue;
      }
      const hay = (day.ingredients + " " + day.dishes.join(" ")).toLowerCase();
      const allTermsHit = expandedTerms.every((options) =>
        options.some((opt) => hay.includes(opt.toLowerCase()))
      );
      if (terms.length === 0 || allTermsHit) {
        results.push({
          ...day,
          term_marks: expandedTerms.map((options, idx) => ({
            term: terms[idx],
            hit: options.some((opt) => hay.includes(opt.toLowerCase())),
          })),
        });
      }
    }
    return results;
  }

  function renderMenuResults() {
    const date = document.getElementById("menu-date").value;
    const schoolType = document.getElementById("menu-school").value;
    const ingredients = document.getElementById("menu-ingredients").value.trim();
    const $out = document.getElementById("menu-results");

    if (!date && !ingredients) {
      $out.innerHTML = `<p class="hint">日付か食材を入力すると、その日の給食メニューを表示します。</p>`;
      return;
    }

    const results = searchMenu({ date, schoolType, ingredients });
    if (results.length === 0) {
      $out.innerHTML = `<div class="menu-no-result">該当する献立が見つかりませんでした。<br>日付・食材・学校種別を変えてお試しください。</div>`;
      return;
    }

    let html = "";
    // Group by date+school+area
    for (const day of results) {
      const headerMeta = `${day.school_type}${day.area ? "（" + day.area + "）" : ""}`;
      const marks = day.term_marks.map(m =>
        `<span class="mark ${m.hit ? "" : "miss"}">${m.hit ? "✓" : "×"} ${escapeHTML(m.term)}</span>`
      ).join("");

      html += `
        <div class="menu-day-group">
          <div class="menu-day-header">
            <span>📅 ${escapeHTML(day.date)}（${escapeHTML(day.weekday)}）</span>
            <span class="menu-day-meta">${escapeHTML(headerMeta)}</span>
          </div>
          ${marks ? `<div class="menu-match-marks">${marks}</div>` : ""}
          <ul class="menu-dish-list">
      `;
      for (const dish of day.dishes) {
        const matchedRecipe = findRecipeForDish(dish);
        html += `
          <li class="menu-dish">
            <div class="menu-dish-name">
              <span>🍽 ${escapeHTML(dish)}</span>
              ${matchedRecipe ? `<a class="menu-dish-link" href="#${encodeURIComponent(matchedRecipe.id)}" data-recipe-id="${matchedRecipe.id}">レシピを見る →</a>` : ""}
            </div>
          </li>
        `;
      }
      html += `</ul></div>`;
    }
    $out.innerHTML = html;

    $out.querySelectorAll(".menu-dish-link").forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const id = link.dataset.recipeId;
        const r = RECIPES.find((x) => x.id === id);
        if (r) showDetail(r);
      });
    });
  }

  function setupMenuView() {
    const $date = document.getElementById("menu-date");
    if (!$date.value) {
      // default: most recent menu date or today
      const dates = MENUS.map((m) => m.date).sort();
      const today = new Date().toISOString().slice(0, 10);
      $date.value = dates.includes(today) ? today : (dates[dates.length - 1] || today);
    }
    document.getElementById("menu-date").addEventListener("change", renderMenuResults);
    document.getElementById("menu-school").addEventListener("change", renderMenuResults);
    document.getElementById("menu-ingredients").addEventListener("input", renderMenuResults);
    renderMenuResults();
  }
  let menuViewInited = false;

  /* --- View switching --- */
  function showDetail(r) {
    state.selected = r;
    state.view = "detail";
    $listView.hidden = true;
    $menuView.hidden = true;
    $detailView.hidden = false;
    $backBtn.hidden = false;
    renderDetail(r);
    history.pushState({ id: r.id }, "", "#" + encodeURIComponent(r.id));
  }
  function showList() {
    state.selected = null;
    state.view = "list";
    $detailView.hidden = true;
    $menuView.hidden = true;
    $listView.hidden = false;
    $backBtn.hidden = true;
    $menuTab.classList.remove("active");
    renderList();
    if (location.hash) history.pushState({}, "", location.pathname);
  }
  function showMenuView() {
    state.view = "menu";
    $detailView.hidden = true;
    $listView.hidden = true;
    $menuView.hidden = false;
    $backBtn.hidden = false;
    $menuTab.classList.add("active");
    if (!menuViewInited) {
      setupMenuView();
      menuViewInited = true;
    }
  }

  /* --- Wiring --- */
  $backBtn.addEventListener("click", showList);
  $favTab.addEventListener("click", () => {
    if (state.view !== "list") {
      showList();
    }
    state.category = state.category === "favorites" ? "all" : "favorites";
    $favTab.classList.toggle("active", state.category === "favorites");
    renderFilters();
    renderList();
  });
  $menuTab.addEventListener("click", () => {
    if (state.view === "menu") showList();
    else showMenuView();
  });
  $search.addEventListener("input", (e) => {
    state.query = e.target.value.trim();
    $clearBtn.hidden = !state.query;
    renderList();
  });
  $clearBtn.addEventListener("click", () => {
    $search.value = "";
    state.query = "";
    $clearBtn.hidden = true;
    renderList();
    $search.focus();
  });
  window.addEventListener("popstate", (e) => {
    const id = e.state && e.state.id;
    if (id) {
      const r = RECIPES.find((x) => x.id === id);
      if (r) { showDetail(r); return; }
    }
    if (state.view !== "list") showList();
  });

  /* --- Utilities --- */
  function escapeHTML(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function escapeAttr(s) { return escapeHTML(s); }

  /* --- Today's lunch banner --- */
  const WEEKDAY_JP = ["日", "月", "火", "水", "木", "金", "土"];
  const BANNER_AREA = "東浅井";

  // bannerDate: the date currently shown in the banner (local date, no timezone shift)
  const _todayLocal = (() => {
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), n.getDate());
  })();
  let bannerDate = _todayLocal;

  function dateToISO(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  }
  function prevSchoolDay(d) {
    const p = new Date(d); p.setDate(p.getDate() - 1);
    while (p.getDay() === 0 || p.getDay() === 6) p.setDate(p.getDate() - 1);
    return p;
  }
  function nextSchoolDay(d) {
    const n = new Date(d); n.setDate(n.getDate() + 1);
    while (n.getDay() === 0 || n.getDay() === 6) n.setDate(n.getDate() + 1);
    return n;
  }

  function renderTodayBanner() {
    const dateISO = dateToISO(bannerDate);
    const m = bannerDate.getMonth() + 1;
    const day = bannerDate.getDate();
    const wd = WEEKDAY_JP[bannerDate.getDay()];
    document.getElementById("today-banner-date").textContent = `${m}月${day}日（${wd}曜日）`;

    const $body = document.getElementById("today-banner-body");
    const todayMenus = MENUS.filter((r) => r.date === dateISO && r.area === BANNER_AREA);
    if (todayMenus.length === 0) {
      $body.innerHTML = "";
      return;
    }

    // Collect all unique dishes across all records for today.
    const DISH_CANONICAL = { "牛乳":"milk","ぎゅうにゅう":"milk","ご飯":"rice","ごはん":"rice",
                              "パン":"bread","ぱん":"bread" };
    // Dishes from 中学校 and 小学校 often differ only by kanji vs hiragana (揚げパン vs あげパン).
    // Dedup key: strip grade suffixes, take the first continuous run of same-script chars (5 chars),
    // then append length bucket — this catches spelling variants while avoiding false positives.
    function dishDedupKey(s) {
      const stripped = s.replace(/[・･].*$/, "").trim();
      if (DISH_CANONICAL[stripped]) return DISH_CANONICAL[stripped];
      s = stripped;
      const lead = s.match(/^([ァ-ヶーｦ-ﾟ]+|[一-鿿]+|[ぁ-ん]+)/);
      const prefix = lead ? lead[0].slice(0, 5) : s.slice(0, 5);
      return prefix + "|" + Math.floor(s.length / 2); // length bucket prevents over-merging
    }
    const allDishes = [];
    const seenKey = new Set();
    // Prefer 共通 → 中学校 → 小学校 for canonical name selection
    const ordered = [...todayMenus].sort((a, b) => {
      const rank = { "共通": 0, "中学校": 1, "小学校": 2 };
      return (rank[a.school_type] ?? 3) - (rank[b.school_type] ?? 3);
    });
    for (const row of ordered) {
      for (const dish of row.dishes) {
        if (/^[<〈（(]/.test(dish)) continue; // skip sub-items like <肉団子>
        const key = dishDedupKey(dish);
        if (!seenKey.has(key)) {
          seenKey.add(key);
          allDishes.push(dish);
        }
      }
    }

    let html = `<ul class="today-dish-list">`;
    for (const dish of allDishes) {
      const recipe = findRecipeForDish(dish);
      html += `<li class="today-dish">
        <span class="today-dish-name">▸ ${escapeHTML(dish)}</span>
        ${recipe ? `<button class="today-recipe-link" data-recipe-id="${recipe.id}">レシピを見る →</button>` : ""}
      </li>`;
    }
    html += `</ul>`;
    $body.innerHTML = html;

    $body.querySelectorAll(".today-recipe-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        const r = RECIPES.find((x) => x.id === btn.dataset.recipeId);
        if (r) showDetail(r);
      });
    });
  }

  /* --- Banner arrow button navigation --- */
  document.getElementById("banner-prev").addEventListener("click", () => {
    bannerDate = prevSchoolDay(bannerDate);
    renderTodayBanner();
  });
  document.getElementById("banner-next").addEventListener("click", () => {
    bannerDate = nextSchoolDay(bannerDate);
    renderTodayBanner();
  });

  /* --- Banner swipe navigation --- */
  const $banner = document.getElementById("today-banner");
  let _swipeStartX = null;
  let _swipeStartY = null;
  $banner.addEventListener("touchstart", (e) => {
    _swipeStartX = e.touches[0].clientX;
    _swipeStartY = e.touches[0].clientY;
  }, { passive: true });
  $banner.addEventListener("touchend", (e) => {
    if (_swipeStartX === null) return;
    const dx = e.changedTouches[0].clientX - _swipeStartX;
    const dy = e.changedTouches[0].clientY - _swipeStartY;
    _swipeStartX = null;
    _swipeStartY = null;
    // Require clear horizontal gesture (dx > dy) and minimum distance
    if (Math.abs(dx) < 40 || Math.abs(dy) > Math.abs(dx)) return;
    if (dx < 0) {
      bannerDate = nextSchoolDay(bannerDate);
    } else {
      bannerDate = prevSchoolDay(bannerDate);
    }
    renderTodayBanner();
  }, { passive: true });

  /* --- Init --- */
  renderFilters();
  renderList();
  renderTodayBanner();
  if (location.hash) {
    const id = decodeURIComponent(location.hash.slice(1));
    const r = RECIPES.find((x) => x.id === id);
    if (r) showDetail(r);
  }
})();
