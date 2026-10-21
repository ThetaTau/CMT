// Asks for confirmation before submitting any form that carries data-confirm.
(function () {
  "use strict";
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm) {
      return;
    }
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
})();
