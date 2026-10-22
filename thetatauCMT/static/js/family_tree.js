// Draws the chapter family tree from the figure the page embeds with json_script.
(function () {
  "use strict";
  var chart = document.getElementById("family-tree-chart");
  var source = document.getElementById("family-tree-figure");
  if (!chart || !source || !window.Plotly) {
    return;
  }
  var Plotly = window.Plotly;
  var figure = JSON.parse(source.textContent);
  var meta = figure.layout.meta || {};
  var tools = document.getElementById("family-tree-tools");
  // Roughly one label's width per person, so names do not overlap.
  var PERSON_WIDTH = 110;
  // Any closer together and the names overlap, so only the markers are drawn.
  var MIN_LABEL_WIDTH = 60;
  var ZOOM_STEP = 1.5;
  var MIN_SPAN = 2;
  // Browsers cannot draw an image much wider than this.
  var MAX_IMAGE_WIDTH = 16000;
  var MARGIN = (figure.layout.margin.l || 0) + (figure.layout.margin.r || 0);
  var full = figure.layout.xaxis.range.slice();
  var fullSpan = full[1] - full[0];
  var personTraces = [];
  figure.data.forEach(function (trace, index) {
    if (trace.mode === "markers+text") {
      personTraces.push(index);
    }
  });
  var view;
  var labelsShown;

  function plotWidth(width) {
    return Math.max(width - MARGIN, 1);
  }

  function clamp(range) {
    var span = Math.max(range[1] - range[0], MIN_SPAN);
    if (span >= fullSpan) {
      return full.slice();
    }
    var start = Math.min(Math.max(range[0], full[0]), full[1] - span);
    return [start, start + span];
  }

  // Readable names, centered on the member found with the search or opened from a profile.
  function startingView() {
    var span = plotWidth(chart.clientWidth) / PERSON_WIDTH;
    var center = typeof meta.focusX === "number" ? meta.focusX : full[0] + span / 2;
    return clamp([center - span / 2, center + span / 2]);
  }

  function wantsLabels(range, width) {
    return plotWidth(width) / (range[1] - range[0]) >= MIN_LABEL_WIDTH;
  }

  function traces(showLabels) {
    return figure.data.map(function (trace, index) {
      if (personTraces.indexOf(index) === -1) {
        return trace;
      }
      return Object.assign({}, trace, { mode: showLabels ? "markers+text" : "markers" });
    });
  }

  function layout(range, width, colors) {
    var textColor = colors ? colors.text : window.getComputedStyle(document.body).color;
    var background = colors ? { paper_bgcolor: colors.background, plot_bgcolor: colors.background } : {};
    return Object.assign({}, figure.layout, background, {
      width: width,
      xaxis: Object.assign({}, figure.layout.xaxis, { range: range }),
      font: Object.assign({}, figure.layout.font, { color: textColor }),
      legend: Object.assign({}, figure.layout.legend, { font: { color: textColor } })
    });
  }

  var config = {
    displaylogo: false,
    doubleClick: "reset",
    modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toImage"]
  };

  function updateButtons() {
    if (!tools) {
      return;
    }
    var span = view[1] - view[0];
    var whole = span >= fullSpan - 1e-6;
    var disabled = { "zoom-in": span <= MIN_SPAN + 1e-6, "zoom-out": whole, fit: whole };
    Object.keys(disabled).forEach(function (action) {
      var control = tools.querySelector('[data-tree-action="' + action + '"]');
      if (control) {
        control.disabled = disabled[action];
      }
    });
  }

  function draw() {
    labelsShown = wantsLabels(view, chart.clientWidth);
    updateButtons();
    return Plotly.react(chart, traces(labelsShown), layout(view, chart.clientWidth), config);
  }

  // Dragging, the zoom buttons and double-clicking all end up here.
  function followView() {
    var range = chart.layout && chart.layout.xaxis && chart.layout.xaxis.range;
    if (!range) {
      return;
    }
    view = [Number(range[0]), Number(range[1])];
    updateButtons();
    var show = wantsLabels(view, chart.clientWidth);
    if (show !== labelsShown) {
      labelsShown = show;
      Plotly.restyle(chart, { mode: show ? "markers+text" : "markers" }, personTraces);
    }
  }

  function zoom(factor) {
    var center = (view[0] + view[1]) / 2;
    var span = (view[1] - view[0]) * factor;
    Plotly.relayout(chart, { "xaxis.range": clamp([center - span / 2, center + span / 2]) });
  }

  // Everything on this page, not just the part on screen, on white so it prints well.
  function download() {
    var width = Math.min(Math.max(chart.clientWidth, Math.round(fullSpan * PERSON_WIDTH) + MARGIN), MAX_IMAGE_WIDTH);
    var picture = {
      data: traces(wantsLabels(full, width)),
      layout: layout(full.slice(), width, { text: "#212529", background: "#ffffff" })
    };
    Plotly.downloadImage(picture, {
      format: "png",
      width: width,
      height: figure.layout.height,
      filename: chart.dataset.filename || "family-tree"
    });
  }

  view = startingView();
  draw().then(function () {
    chart.on("plotly_click", function (event) {
      var point = event.points && event.points[0];
      var url = point && point.customdata;
      if (typeof url === "string" && url.charAt(0) === "/") {
        window.location.assign(url);
      }
    });
    chart.on("plotly_relayout", followView);
    if (tools) {
      tools.addEventListener("click", function (event) {
        var control = event.target.closest("[data-tree-action]");
        var action = control && control.dataset.treeAction;
        if (action === "zoom-in") {
          zoom(1 / ZOOM_STEP);
        } else if (action === "zoom-out") {
          zoom(ZOOM_STEP);
        } else if (action === "fit") {
          Plotly.relayout(chart, { "xaxis.range": full.slice() });
        } else if (action === "download") {
          download();
        }
      });
      tools.hidden = false;
    }
  });
  window.addEventListener("resize", draw);
  // The theme switcher changes data-bs-theme on <html>; redraw so labels stay readable.
  new MutationObserver(draw).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-bs-theme"]
  });
})();
