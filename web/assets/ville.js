// Fiche ville : petite carte de situation, sans interaction superflue.
(function () {
  "use strict";
  var zone = document.getElementById("minicarte");
  if (!zone || !window.maplibregl) return;
  var centre = [Number(zone.getAttribute("data-lon")), Number(zone.getAttribute("data-lat"))];
  var carte = new maplibregl.Map({
    container: zone,
    style: window.Explora.style(),
    center: centre,
    zoom: 10.5,
    interactive: false,
    attributionControl: { compact: true }
  });
  carte.on("load", function () { window.Explora.fondDeSecours(carte, "../../"); });
  // La grille de l'en-tête peut changer de largeur après le chargement des polices.
  if (window.ResizeObserver) new ResizeObserver(function () { carte.resize(); }).observe(zone);
  var repere = document.createElement("div");
  repere.style.cssText =
    "width:16px;height:16px;border-radius:50%;background:var(--repere);" +
    "border:3px solid var(--surface);box-shadow:0 0 0 1px var(--encre)";
  new maplibregl.Marker({ element: repere }).setLngLat(centre).addTo(carte);
})();
