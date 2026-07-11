/* Project specific Javascript goes here. */

/*
Formatting hack to get around crispy-forms unfortunate hardcoding
in helpers.FormHelper:

    if template_pack == 'bootstrap5':
        grid_colum_matcher = re.compile('\w*col-(xs|sm|md|lg|xl)-\d+\w*')
        using_grid_layout = (grid_colum_matcher.match(self.label_class) or
                             grid_colum_matcher.match(self.field_class))
        if using_grid_layout:
            items['using_grid_layout'] = True

Issues with the above approach:

1. Fragile: Assumes Bootstrap 4's API doesn't change (it does)
2. Unforgiving: Doesn't allow for any variation in template design
3. Really Unforgiving: No way to override this behavior
4. Undocumented: No mention in the documentation, or it's too hard for me to find
*/
$('.form-group').removeClass('row');

// Clipboard copy buttons (elements with class .clipboard).
// Copies the element's data-clipboard-text (falling back to its own text) using
// the browser's native async Clipboard API, with a document.execCommand fallback
// for non-secure contexts. This avoids depending on the clipboard.js library
// (which is not loaded on every page) and the "Illegal constructor" clash between
// that library's global `Clipboard` and the browser's built-in Clipboard class.
function copyTextToClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise(function (resolve, reject) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    if (ok) { resolve(); } else { reject(); }
  });
}

function flashClipboardTooltip(el, tip, message) {
  el.setAttribute('data-bs-original-title', message);
  tip.setContent({ '.tooltip-inner': message });
  tip.show();
  setTimeout(function () { tip.hide(); }, 1000);
}

// Bootstrap 5: tooltips are opt-in and must be initialized per element.
$('.clipboard').each(function () {
  var el = this;
  var tip = new bootstrap.Tooltip(el, { trigger: 'manual', placement: 'bottom' });
  el.addEventListener('click', function (event) {
    event.preventDefault();
    var text = el.getAttribute('data-clipboard-text');
    if (text === null) { text = el.textContent; }
    copyTextToClipboard(text).then(function () {
      flashClipboardTooltip(el, tip, 'Copied!');
    }).catch(function () {
      flashClipboardTooltip(el, tip, 'Failed!');
    });
  });
});
