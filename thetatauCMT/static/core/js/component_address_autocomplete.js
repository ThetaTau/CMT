/**
 * component_address_autocomplete.js
 *
 * Attaches a Google Places autocomplete to every input marked
 * `.component-address-autocomplete` and copies the selected address
 * components into the 5 sibling fields:
 *   {prefix}_0  street (street_number + " " + route)
 *   {prefix}_1  city
 *   {prefix}_2  state  (<select>, US 2-letter code)
 *   {prefix}_3  postal code
 *   {prefix}_4  country (<select>, long name)
 *
 * The autocomplete input itself is NOT part of the form submission — it's
 * a UX helper.  Users can also just type the split fields by hand if they
 * don't pick a suggestion (or if Google Maps fails to load).
 */
(function () {
  "use strict";

  function extractComponents(place) {
    var out = {
      street_number: "",
      route: "",
      locality: "",
      sublocality: "",
      postal_town: "",
      postal_code: "",
      state: "",
      country: "",
    };
    var comps = (place && place.address_components) || [];
    for (var i = 0; i < comps.length; i++) {
      var comp = comps[i];
      var types = comp.types || [];
      for (var j = 0; j < types.length; j++) {
        var t = types[j];
        if (t === "street_number") out.street_number = comp.short_name;
        else if (t === "route") out.route = comp.long_name;
        else if (t === "locality") out.locality = comp.long_name;
        else if (t === "sublocality" || t === "sublocality_level_1") out.sublocality = comp.long_name;
        else if (t === "postal_town") out.postal_town = comp.long_name;
        else if (t === "postal_code") out.postal_code = comp.short_name;
        else if (t === "administrative_area_level_1") out.state = comp.long_name;
        else if (t === "country") out.country = comp.long_name;
      }
    }
    return out;
  }

  function setField(prefix, idx, value) {
    var el = document.getElementById(prefix + "_" + idx);
    if (!el || value == null) return;
    if (el.tagName === "SELECT") {
      var options = el.options;
      var matched = false;
      for (var i = 0; i < options.length; i++) {
        if (options[i].value === value) {
          el.selectedIndex = i;
          matched = true;
          break;
        }
      }
      if (matched) {
        el.dispatchEvent(new Event("change", { bubbles: true }));
      }
    } else {
      el.value = value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function fillFieldsFromPlace(input, place) {
    var prefix = input.getAttribute("data-target-prefix");
    if (!prefix) return;
    var parts = extractComponents(place);
    var street = [parts.street_number, parts.route].filter(Boolean).join(" ").trim();
    var city = parts.locality || parts.sublocality || parts.postal_town || "";
    setField(prefix, 0, street);
    setField(prefix, 1, city);
    setField(prefix, 2, parts.state);
    setField(prefix, 3, parts.postal_code);
    setField(prefix, 4, parts.country);
  }

  function attach(input) {
    if (input.dataset.addressAcInit === "1") return;
    input.dataset.addressAcInit = "1";
    var ac = new google.maps.places.Autocomplete(input, {
      types: ["address"],
      fields: ["address_components", "formatted_address"],
    });
    ac.addListener("place_changed", function () {
      var place = ac.getPlace();
      if (place && place.address_components) {
        fillFieldsFromPlace(input, place);
      }
    });
    // Prevent Enter in the autocomplete from submitting the form while a
    // suggestion is highlighted.
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") e.preventDefault();
    });
  }

  function init() {
    if (!(window.google && window.google.maps && window.google.maps.places)) {
      window.setTimeout(init, 250);
      return;
    }
    var inputs = document.querySelectorAll(".component-address-autocomplete");
    for (var i = 0; i < inputs.length; i++) attach(inputs[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
