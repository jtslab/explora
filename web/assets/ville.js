// Fiche ville : petite carte de situation, sans interaction superflue.
(function () {
  "use strict";

  // Filtre de la liste des formations (utile pour les grandes villes : plus de 1 000 lignes à Paris).
  var champ = document.getElementById("filtre-formations");
  if (champ) {
    var bloc = document.getElementById("formations");
    var normaliser = function (t) {
      return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    };
    var groupes = Array.prototype.map.call(bloc.querySelectorAll("details"), function (d) {
      return {
        d: d,
        ouvert: d.open,
        compte: d.querySelector("summary small"),
        total: d.querySelector("summary small").textContent,
        lignes: Array.prototype.map.call(d.querySelectorAll("li[data-n]"), function (li) {
          return { li: li, n: Number(li.dataset.n), texte: normaliser(li.textContent + " " + d.querySelector("summary span").textContent) };
        })
      };
    });
    champ.addEventListener("input", function () {
      var mots = normaliser(champ.value).split(/\s+/).filter(Boolean);
      var total = 0;
      groupes.forEach(function (g) {
        var vus = 0;
        g.lignes.forEach(function (l) {
          var ok = mots.every(function (m) { return l.texte.indexOf(m) !== -1; });
          l.li.hidden = !ok;
          if (ok) vus += l.n;
        });
        g.d.hidden = vus === 0;
        g.compte.textContent = mots.length ? vus + " / " + g.total : g.total;
        g.d.open = mots.length ? vus > 0 : g.ouvert;
        total += vus;
      });
      bloc.querySelector(".aucune").hidden = total > 0;
    });
  }

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
