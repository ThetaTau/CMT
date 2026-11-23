// Case Competition pages: asks for confirmation before submitting a form, or pressing a submit
// button, that carries data-confirm (withdrawing, publishing, removing a judge).
(function () {
  "use strict";
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    var button = event.submitter;
    var message = (button && button.dataset.confirm) || form.dataset.confirm;
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });
})();

// The scores page: each entry's scores for each criterion open in a row under it. "Open every
// entry" opens them all and is remembered in this browser, because saving a decision reloads
// the page.
(function () {
  "use strict";
  var STORAGE_KEY = "competitionScoreDetails";

  function setAll(show) {
    if (!window.bootstrap) {
      return;
    }
    document.querySelectorAll(".competition-score-details").forEach(function (row) {
      var collapse = window.bootstrap.Collapse.getOrCreateInstance(row, { toggle: false });
      if (show) {
        collapse.show();
      } else {
        collapse.hide();
      }
    });
  }

  function remember(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (error) {
      // Storage can be switched off; the buttons still work for this page.
    }
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-competition-details]");
    if (!button) {
      return;
    }
    var show = button.dataset.competitionDetails === "show";
    remember(show ? "show" : "hide");
    setAll(show);
  });

  function restore() {
    var saved = null;
    try {
      saved = window.localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return;
    }
    if (saved === "show") {
      setAll(true);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", restore);
  } else {
    restore();
  }
})();
