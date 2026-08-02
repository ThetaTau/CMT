/*
 * What's New behaviour (TWI-6).
 *
 * Three surfaces, one endpoint:
 *   - the modal in `guides/_whats_new_modal.html`, shown at most once per session;
 *   - "Got it" forms (`.tt-whats-new-ack`) on the home page and the archive;
 *   - "Take me there" links (`[data-whats-new-visit]`), which acknowledge on the way out.
 *
 * Every acknowledgement is a POST to `guides:acknowledge` carrying `{kind, id}`
 * plus the affordance that produced it. The "Got it" forms are real forms with a
 * `next` field, so with JavaScript off they still work -- this file only upgrades
 * them to stay on the page.
 */
(function () {
  "use strict";

  var MODAL_ID = "tt-whats-new-modal";

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function track(event, properties) {
    if (window.posthog) {
      window.posthog.capture(event, properties);
    }
  }

  function post(url, payload, options) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      keepalive: !!(options && options.keepalive),
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(payload || {}),
    });
  }

  function itemOf(el) {
    var card = el.closest("[data-whats-new-kind]");
    if (!card) {
      return null;
    }
    return { kind: card.dataset.whatsNewKind, id: parseInt(card.dataset.whatsNewId, 10) };
  }

  // --- The modal ------------------------------------------------------------
  // Marking it seen happens on show, not on render: RMPSignMiddleware runs after
  // the view, so a page can render in full and then be swapped for a redirect.

  function setupModal() {
    var el = document.getElementById(MODAL_ID);
    if (!el || !window.bootstrap) {
      return;
    }
    var items = Array.prototype.map
      .call(el.querySelectorAll("[data-whats-new-kind]"), function (card) {
        return { kind: card.dataset.whatsNewKind, id: parseInt(card.dataset.whatsNewId, 10) };
      })
      .filter(function (item) {
        return item.kind && !isNaN(item.id);
      });

    el.addEventListener("shown.bs.modal", function () {
      post(el.dataset.seenUrl, {}).catch(function () {});
      track("whats_new_shown", { count: items.length });
    });

    // Closing the modal is the acknowledgement -- by the × as much as by "Got it",
    // because a user who closes it has been shown everything in it.
    el.addEventListener("hidden.bs.modal", function () {
      if (items.length) {
        post(el.dataset.ackUrl, { items: items, source: "modal" }).catch(function () {});
      }
      track("whats_new_dismissed", { count: items.length });
    });

    window.bootstrap.Modal.getOrCreateInstance(el).show();
  }

  // --- "Got it" -------------------------------------------------------------

  function setupAckForms() {
    document.addEventListener("submit", function (event) {
      var form = event.target.closest(".tt-whats-new-ack");
      if (!form) {
        return;
      }
      var item = itemOf(form);
      if (!item || isNaN(item.id)) {
        return; // Let the plain form post handle it.
      }
      event.preventDefault();
      var source = (form.querySelector("[name=source]") || {}).value || "badge";
      var card = form.closest("[data-whats-new-kind]");
      post(form.action, { items: [item], source: source })
        .then(function () {
          if (card) {
            card.remove();
          }
        })
        .catch(function () {});
      track("whats_new_acknowledged", { kind: item.kind, id: item.id, source: source });
    });
  }

  // --- "Take me there" ------------------------------------------------------

  function setupVisitLinks() {
    document.addEventListener("click", function (event) {
      var link = event.target.closest("[data-whats-new-visit]");
      if (!link || !link.dataset.ackUrl) {
        return;
      }
      var item = itemOf(link);
      if (!item || isNaN(item.id)) {
        return;
      }
      // Following a link *is* reading the announcement, so record it -- with
      // `keepalive`, because the navigation starts before the request finishes.
      post(link.dataset.ackUrl, { items: [item], source: "visited" }, { keepalive: true }).catch(function () {});
      track("whats_new_visited", { kind: item.kind, id: item.id });
    });
  }

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    setupAckForms();
    setupVisitLinks();
    setupModal();
  });
})();
