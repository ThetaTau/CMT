/*
 * Client-side search / filter for catalog card grids (TWI-9, reused by TWI-9b).
 *
 * There is no search endpoint: every card the viewer is allowed to see is already
 * in the DOM -- server-side visibility filtering happened in guides.services -- so
 * filtering is a text match over what is on the page. That keeps the catalog to one
 * bounded set of queries no matter how much someone types.
 *
 * Markup contract (see templates/guides/_catalog_card.html):
 *   #tt-catalog-search        text input
 *   #tt-catalog-mine          optional "only my role's tools" checkbox
 *   #tt-catalog-chips         optional container of [data-catalog-chip="<area key>"] buttons
 *   #tt-catalog-expand        optional "expand all" / "collapse all" button
 *   #tt-catalog-count         optional live region for the result count
 *   #tt-catalog-empty         optional "nothing matched" paragraph
 *   #tt-catalog-mine-section  optional pinned panel, opened only by the role switch
 *   .tt-catalog-card          one card, carrying data-catalog-text / -area / -mine
 *   .tt-catalog-section       a group heading + its cards, carrying data-catalog-area
 *   [data-catalog-panel]      optional Bootstrap collapse inside a section
 *   [data-catalog-tally]      optional per-section count of matching cards
 *
 * Every hook is optional, so a page can use the cards without the chips, or the
 * search box without the role switch, or the sections without collapsing them.
 */
(function () {
  "use strict";

  var SEARCH_EVENT_DELAY = 900;

  function track(event, props) {
    if (window.posthog) {
      window.posthog.capture(event, props || {});
    }
  }

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    // The role guide page has no cards but is instrumented from here rather than
    // from a file of its own (TWI-13).
    var guidePage = document.querySelector("[data-role-guide-page]");
    if (guidePage) {
      track("role_guide_viewed", { role: guidePage.getAttribute("data-role-guide-page") });
    }

    var cards = Array.prototype.slice.call(document.querySelectorAll(".tt-catalog-card"));
    if (!cards.length) {
      return;
    }
    var search = document.getElementById("tt-catalog-search");
    var mine = document.getElementById("tt-catalog-mine");
    var chips = document.getElementById("tt-catalog-chips");
    var expandAll = document.getElementById("tt-catalog-expand");
    var count = document.getElementById("tt-catalog-count");
    var empty = document.getElementById("tt-catalog-empty");
    var sections = Array.prototype.slice.call(document.querySelectorAll(".tt-catalog-section"));
    // A pinned summary of the viewer's own duties (the forms landing). It is not
    // part of the result set -- it holds no cards, the counts ignore it, and only
    // the role switch opens it.
    var mineSection = document.getElementById("tt-catalog-mine-section");
    var mineAutoOpened = false;
    var area = "";
    var searchTimer = null;
    // Sections the filters opened on the user's behalf. Only these are closed
    // again when the filters clear, so a panel someone opened by hand stays open.
    var autoOpened = [];

    var collapsible = typeof bootstrap !== "undefined" && !!bootstrap.Collapse;

    function panelOf(section) {
      return section.querySelector("[data-catalog-panel]");
    }

    function isOpen(section) {
      var panel = panelOf(section);
      return !!panel && panel.classList.contains("show");
    }

    function setOpen(section, open) {
      var panel = panelOf(section);
      if (!panel || !collapsible) {
        return;
      }
      // `toggle: false` so merely constructing the instance does not flip it.
      var instance = bootstrap.Collapse.getOrCreateInstance(panel, { toggle: false });
      if (open) {
        instance.show();
      } else {
        instance.hide();
      }
    }

    function syncExpandLabel() {
      if (!expandAll) {
        return;
      }
      var closed = collapsibleSections().filter(function (section) {
        return !section.hidden && !isOpen(section);
      });
      expandAll.textContent = closed.length ? "Expand all" : "Collapse all";
    }

    function collapsibleSections() {
      return mineSection ? sections.concat([mineSection]) : sections;
    }

    // Lower-case once rather than on every keystroke.
    cards.forEach(function (card) {
      card.ttText = (card.getAttribute("data-catalog-text") || "").toLowerCase();
      card.ttArea = card.getAttribute("data-catalog-area") || "";
      card.ttMine = card.getAttribute("data-catalog-mine") === "1";
    });

    function apply() {
      var terms = search && search.value ? search.value.toLowerCase().split(/\s+/).filter(Boolean) : [];
      var onlyMine = !!(mine && mine.checked);
      var filtered = !!(area || onlyMine || terms.length);
      var shown = 0;

      cards.forEach(function (card) {
        var visible = true;
        if (area && card.ttArea !== area) {
          visible = false;
        }
        if (visible && onlyMine && !card.ttMine) {
          visible = false;
        }
        if (visible && terms.length) {
          visible = terms.every(function (term) {
            return card.ttText.indexOf(term) !== -1;
          });
        }
        card.hidden = !visible;
        if (visible) {
          shown += 1;
        }
      });

      // Hide a group heading once nothing under it survives, so the page does
      // not read as a list of empty sections.
      sections.forEach(function (section) {
        var matches = section.querySelectorAll(".tt-catalog-card:not([hidden])").length;
        section.hidden = !matches;
        var tally = section.querySelector("[data-catalog-tally]");
        if (tally) {
          tally.textContent = matches;
        }
        // A collapsed panel would hide the very matches the filter just found,
        // so a live filter opens what it matched.
        if (filtered && matches && panelOf(section) && !isOpen(section) && autoOpened.indexOf(section) === -1) {
          autoOpened.push(section);
          setOpen(section, true);
        }
      });
      if (!filtered && autoOpened.length) {
        autoOpened.forEach(function (section) {
          setOpen(section, false);
        });
        autoOpened = [];
      }

      // The pinned panel indexes duties, not search results, so a text or area
      // filter takes it off the page rather than filtering it.
      if (mineSection) {
        mineSection.hidden = !!(area || terms.length);
      }

      if (count) {
        count.textContent = filtered
          ? shown + " of " + cards.length + " shown"
          : cards.length + " things you can do";
      }
      if (empty) {
        empty.hidden = shown !== 0;
      }
      syncExpandLabel();
    }

    if (search) {
      search.addEventListener("input", function () {
        apply();
        // Report the search, not the typing: wait until they stop.
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(function () {
          if (search.value.trim()) {
            track("catalog_searched", { query_length: search.value.trim().length });
          }
        }, SEARCH_EVENT_DELAY);
      });
    }
    if (mine) {
      mine.addEventListener("change", function () {
        // Narrowing to your own role is the one filter the pinned panel answers,
        // so it -- and only it -- opens the panel.
        if (mineSection && (mine.checked || mineAutoOpened)) {
          setOpen(mineSection, mine.checked);
          mineAutoOpened = mine.checked;
        }
        apply();
      });
    }
    if (chips) {
      chips.addEventListener("click", function (event) {
        var button = event.target.closest("[data-catalog-chip]");
        if (!button) {
          return;
        }
        area = button.getAttribute("data-catalog-chip") || "";
        Array.prototype.forEach.call(chips.querySelectorAll("[data-catalog-chip]"), function (other) {
          var active = other === button;
          other.classList.toggle("btn-primary", active);
          other.classList.toggle("btn-outline-secondary", !active);
        });
        apply();
      });
    }
    if (expandAll) {
      expandAll.addEventListener("click", function () {
        var open = expandAll.textContent.trim() === "Expand all";
        collapsibleSections().forEach(function (section) {
          setOpen(section, open && !section.hidden);
        });
        // Opening everything by hand supersedes the filters' bookkeeping.
        autoOpened = [];
        mineAutoOpened = false;
        expandAll.textContent = open ? "Collapse all" : "Expand all";
        track("catalog_expand_all", { expanded: open });
      });
    }
    collapsibleSections().forEach(function (section) {
      var panel = panelOf(section);
      if (panel) {
        panel.addEventListener("shown.bs.collapse", syncExpandLabel);
        panel.addEventListener("hidden.bs.collapse", syncExpandLabel);
      }
    });

    document.addEventListener("click", function (event) {
      var link = event.target.closest("[data-catalog-link]");
      if (link) {
        track("feature_link_clicked", { feature: link.getAttribute("data-catalog-link") });
      }
    });

    apply();

    // Role guides and the What's New feed deep link to "#area-<key>"; without
    // this the anchor lands on a closed panel. Also bound to `hashchange`,
    // because following such a link while already on this page never reloads.
    function openFromHash() {
      var target = window.location.hash ? document.querySelector(window.location.hash) : null;
      if (target && target.classList.contains("tt-catalog-section")) {
        setOpen(target, true);
        target.scrollIntoView({ block: "start" });
        syncExpandLabel();
      }
    }
    window.addEventListener("hashchange", openFromHash);
    openFromHash();

    track("catalog_viewed", { cards: cards.length });
  });
})();
