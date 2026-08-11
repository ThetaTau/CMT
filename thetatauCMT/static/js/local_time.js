/*
 * Renders event times in the viewer's own time zone.
 *
 * Markup contract:
 *   <time data-local-time datetime="2026-08-15T19:00:00-04:00"
 *         data-event-date="2026-08-15">7:00 PM</time>
 *
 * The element's server-rendered contents are the event's own wall-clock time, so
 * the page still reads correctly without JavaScript. When the script runs the
 * text is replaced with the same instant in the browser's zone.
 *
 *   data-local-time="short"  time only (dense listings such as the month grid)
 *   data-local-time          time plus the zone abbreviation, e.g. "9:00 PM EDT"
 *
 * `data-event-date` is the event's own calendar day. When converting moves the
 * event onto a different day for this viewer, the local date is shown too, so a
 * 10pm Pacific event does not silently read as a bare time in the wrong cell.
 *
 * Anything carrying `data-local-time-zone` gets the viewer's zone written into
 * it, and the surrounding `data-local-time-note` element is unhidden, so a
 * "times shown in ..." sentence never appears with a blank zone.
 */
(function () {
  "use strict";

  function browserZone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch (err) {
      return "";
    }
  }

  function zoneAbbreviation(when, zone) {
    try {
      var parts = new Intl.DateTimeFormat("en-US", {
        timeZone: zone || undefined,
        timeZoneName: "short",
      }).formatToParts(when);
      for (var i = 0; i < parts.length; i += 1) {
        if (parts[i].type === "timeZoneName") {
          return parts[i].value;
        }
      }
    } catch (err) {
      /* fall through to the raw zone name */
    }
    return zone;
  }

  function localDateKey(when) {
    function pad(n) {
      return (n < 10 ? "0" : "") + n;
    }
    return when.getFullYear() + "-" + pad(when.getMonth() + 1) + "-" + pad(when.getDate());
  }

  function renderElement(el, zone) {
    var when = new Date(el.getAttribute("datetime"));
    if (isNaN(when.getTime())) {
      return;
    }
    var text = when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    var eventDate = el.getAttribute("data-event-date");
    if (eventDate && eventDate !== localDateKey(when)) {
      text = when.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + text;
    }
    if (el.getAttribute("data-local-time") !== "short") {
      var abbreviation = zoneAbbreviation(when, zone);
      if (abbreviation) {
        text += " " + abbreviation;
      }
    }
    el.textContent = text;
    el.setAttribute("title", zone ? "Your local time (" + zone + ")" : "Your local time");
  }

  function init() {
    var zone = browserZone();
    var elements = document.querySelectorAll("time[data-local-time]");
    Array.prototype.forEach.call(elements, function (el) {
      renderElement(el, zone);
    });
    if (!zone) {
      return;
    }
    var labels = document.querySelectorAll("[data-local-time-zone]");
    Array.prototype.forEach.call(labels, function (el) {
      var abbreviation = zoneAbbreviation(new Date(), zone);
      el.textContent = abbreviation && abbreviation !== zone ? abbreviation + " (" + zone + ")" : zone;
      var note = el.closest("[data-local-time-note]");
      if (note) {
        note.classList.remove("d-none");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
