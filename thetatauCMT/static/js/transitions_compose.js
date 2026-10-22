/*
 * Transition Report compose page: heuristic warning when a prompt tagged
 * "systems" (see forms.ComposeReportForm._build_field) looks like it
 * contains an actual account password, not just where credentials are
 * stored. Past real transition documents this was modeled on (see
 * .github/copilot-memory/sessions/transitions-app.md, TRWI-13) pasted
 * plaintext passwords directly despite the prompt's own help text already
 * saying not to -- this is a nudge, not a block: it never prevents saving
 * or submitting.
 */
(function () {
  "use strict";

  var EMAIL_LINE = /^\s*[^\s@]+@[^\s@]+\.[^\s@]+\s*$/;
  var PASSWORD_WORD = /\b(password|passwd|pwd)\b\s*[:=]?\s*\S+/i;
  var BARE_TOKEN_LINE = /^\S{6,}$/;
  var PLAIN_WORD = /^[a-z]+$/i;

  function looksLikeCredentials(text) {
    if (PASSWORD_WORD.test(text)) {
      return true;
    }
    var lines = text.split(/\r?\n/);
    for (var i = 0; i < lines.length - 1; i++) {
      if (EMAIL_LINE.test(lines[i])) {
        var next = lines[i + 1].trim();
        if (BARE_TOKEN_LINE.test(next) && !PLAIN_WORD.test(next)) {
          return true;
        }
      }
    }
    return false;
  }

  function attach(field) {
    var warning = document.querySelector('[data-credential-warning-for="' + field.id + '"]');
    if (!warning) {
      return;
    }
    function update() {
      warning.style.display = looksLikeCredentials(field.value) ? "" : "none";
    }
    field.addEventListener("input", update);
    update();
  }

  // Contacts/Key Dates formsets (TRWI-13 proposal): "+ Add another" clones
  // the formset's own hidden <template id="<prefix>-empty-form"> (rendered
  // server-side from formset.empty_form, so field ids/names already match
  // what Django expects, just with the literal "__prefix__" placeholder in
  // place of a real index), string-replaces __prefix__ with the current
  // TOTAL_FORMS count, appends it, and bumps TOTAL_FORMS -- no page reload,
  // so there is no fixed limit on how many contacts/dates can be added.
  function addFormsetRow(prefix) {
    var totalFormsInput = document.getElementById("id_" + prefix + "-TOTAL_FORMS");
    var emptyFormTemplate = document.getElementById(prefix + "-empty-form");
    var rowsContainer = document.getElementById(prefix + "-rows");
    if (!totalFormsInput || !emptyFormTemplate || !rowsContainer) {
      return;
    }
    var index = parseInt(totalFormsInput.value, 10) || 0;
    var html = emptyFormTemplate.innerHTML.split("__prefix__").join(String(index));
    var wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    while (wrapper.firstChild) {
      rowsContainer.appendChild(wrapper.firstChild);
    }
    totalFormsInput.value = String(index + 1);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var fields = document.querySelectorAll("[data-warn-credentials]");
    for (var i = 0; i < fields.length; i++) {
      attach(fields[i]);
    }

    var addButtons = document.querySelectorAll("[data-add-formset-row]");
    for (var j = 0; j < addButtons.length; j++) {
      addButtons[j].addEventListener("click", function (event) {
        addFormsetRow(event.currentTarget.getAttribute("data-add-formset-row"));
      });
    }

    // A "Remove this row" button only ever appears on a not-yet-saved row
    // (an original blank row, or one just added above) -- saved rows use
    // the real DELETE checkbox instead (see compose_form.html), so simply
    // removing the DOM node here is safe: Django's own formset validation
    // already treats a row with no submitted data as empty and skips it.
    document.addEventListener("click", function (event) {
      if (!event.target.classList.contains("remove-formset-row")) {
        return;
      }
      var row = event.target.closest(".contacts_row_form, .key_dates_row_form");
      if (row) {
        row.remove();
      }
    });
  });
})();
