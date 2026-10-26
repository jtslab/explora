// Fond de carte IGN et utilitaires communs à la carte et aux fiches ville.
(function () {
  "use strict";

  var RAMPE = ["#f2e3b0", "#a9cfa0", "#4e9c8a", "#24607a", "#1b3354"];

  var PLAN_IGN =
    "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0" +
    "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM" +
    "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/png";

  function sombre() {
    var theme = document.documentElement.getAttribute("data-theme");
    if (theme) return theme === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  // Plan IGN désaturé : les points de couleur restent lisibles par-dessus.
  function style() {
    var nuit = sombre();
    return {
      version: 8,
      sources: {
        ign: {
          type: "raster",
          tiles: [PLAN_IGN],
          tileSize: 256,
          maxzoom: 18,
          attribution:
            '<a href="https://geoservices.ign.fr/" target="_blank" rel="noopener">© IGN, Géoplateforme</a>'
        }
      },
      layers: [
        { id: "fond", type: "background", paint: { "background-color": nuit ? "#1a2120" : "#eef0ea" } },
        {
          id: "plan-ign",
          type: "raster",
          source: "ign",
          paint: nuit
            ? { "raster-saturation": -0.85, "raster-brightness-max": 0.42, "raster-contrast": 0.1 }
            : { "raster-saturation": -0.7, "raster-opacity": 0.9 }
        }
      ]
    };
  }

  // Contours des départements, pour les aperçus où les tuiles IGN ne chargent pas.
  function fondDeSecours(carte, racine) {
    if (!document.body.hasAttribute("data-fond-secours")) return;
    fetch(racine + "data/departements.geojson")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (geo) {
        if (!geo) return;
        var nuit = sombre();
        carte.addSource("departements", { type: "geojson", data: geo });
        var avant = carte.getLayer("villes") ? "villes" : undefined;
        carte.addLayer({
          id: "departements-fond", type: "fill", source: "departements",
          paint: { "fill-color": nuit ? "#202a28" : "#fbfcf8" }
        }, avant);
        carte.addLayer({
          id: "departements-trait", type: "line", source: "departements",
          paint: { "line-color": nuit ? "#3a4744" : "#c9cfc5", "line-width": 0.7 }
        }, avant);
      })
      .catch(function () {});
  }

  function hex(c) {
    return [1, 3, 5].map(function (k) { return parseInt(c.slice(k, k + 2), 16); });
  }

  // Même calcul que `teinte` dans explora/site/generer.py.
  function teinte(score) {
    if (score === null || score === undefined) return { fond: "#cfd4cc", texte: "#18211f" };
    var pos = Math.max(0, Math.min(score, 100)) / 100 * (RAMPE.length - 1);
    var i = Math.min(Math.floor(pos), RAMPE.length - 2);
    var a = hex(RAMPE[i]), b = hex(RAMPE[i + 1]);
    var rgb = a.map(function (x, k) { return Math.round(x + (b[k] - x) * (pos - i)); });
    var clair = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 140;
    return {
      fond: "#" + rgb.map(function (x) { return x.toString(16).padStart(2, "0"); }).join(""),
      texte: clair ? "#10201c" : "#ffffff"
    };
  }

  function nombre(valeur, decimales, unite) {
    if (valeur === null || valeur === undefined) return "n.d.";
    var texte = valeur.toLocaleString("fr-FR", {
      minimumFractionDigits: decimales || 0,
      maximumFractionDigits: decimales || 0
    });
    return unite ? texte + " " + unite : texte;
  }

  window.Explora = { RAMPE: RAMPE, style: style, fondDeSecours: fondDeSecours, teinte: teinte, nombre: nombre };
})();
