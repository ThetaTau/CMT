// Draws the chapter family tree from the figure the page embeds with json_script.
(function () {
  "use strict";
  var chart = document.getElementById("family-tree-chart");
  var source = document.getElementById("family-tree-figure");
  if (!chart || !source || !window.Plotly) {
    return;
  }
  var figure = JSON.parse(source.textContent);
  // Roughly one label's width per person on the bottom row, so names do not overlap.
  var PERSON_WIDTH = 110;

  function layout() {
    var textColor = window.getComputedStyle(document.body).color;
    var leaves = (figure.layout.meta && figure.layout.meta.leafCount) || 1;
    return Object.assign({}, figure.layout, {
      width: Math.max(chart.parentElement.clientWidth, leaves * PERSON_WIDTH),
      font: Object.assign({}, figure.layout.font, { color: textColor }),
      legend: Object.assign({}, figure.layout.legend, { font: { color: textColor } })
    });
  }

  var config = {
    displaylogo: false,
    modeBarButtonsToRemove: ["select2d", "lasso2d"],
    toImageButtonOptions: { filename: chart.dataset.filename || "family-tree" }
  };

  function redraw() {
    window.Plotly.react(chart, figure.data, layout(), config);
  }

  window.Plotly.newPlot(chart, figure.data, layout(), config).then(function () {
    chart.on("plotly_click", function (event) {
      var point = event.points && event.points[0];
      var url = point && point.customdata;
      if (typeof url === "string" && url.charAt(0) === "/") {
        window.location.assign(url);
      }
    });
  });
  window.addEventListener("resize", redraw);
  // The theme switcher changes data-bs-theme on <html>; redraw so labels stay readable.
  new MutationObserver(redraw).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-bs-theme"]
  });
})();
