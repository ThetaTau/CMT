// Asks for confirmation before submitting a form, or pressing a submit button, that
// carries data-confirm.
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
