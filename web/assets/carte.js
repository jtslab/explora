// Carte des villes étudiantes : score recalculé dans le navigateur selon les poids choisis.
(function () {
  "use strict";

  var AXES = [
    { id: "etudes", libelle: "Études" },
    { id: "budget", libelle: "Budget" },
    { id: "vie", libelle: "Vie étudiante" },
    { id: "mobilite_cadre", libelle: "Mobilité, cadre" }
  ];
  var NIVEAUX = ["ignoré", "secondaire", "normal", "important", "essentiel"];
  var VUES = {
    metropole: { bounds: [[-5.3, 41.3], [9.7, 51.2]] },
    "971": { center: [-61.55, 16.2], zoom: 8.6 },
    "972": { center: [-61.02, 14.64], zoom: 9.2 },
    "973": { center: [-53.1, 4.4], zoom: 6.6 },
    "974": { center: [55.53, -21.13], zoom: 8.8 },
    "976": { center: [45.14, -12.82], zoom: 9.8 }
  };
  var CLE_POIDS = "explora.poids";

  var E = window.Explora;
  var villes = [];
  var donnees = null;
  var carte = null;
  var bulle = null;

  function echapper(texte) {
    return String(texte).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function lirePoids() {
    var poids = {};
    AXES.forEach(function (a) {
      poids[a.id] = Number(document.getElementById("poids-" + a.id).value);
    });
    return poids;
  }

  function score(p, poids) {
    var total = 0, somme = 0;
    AXES.forEach(function (a) {
      var note = p["axe_" + a.id];
      if (note === null || note === undefined) return;
      total += poids[a.id];
      somme += poids[a.id] * note;
    });
    return total > 0 ? somme / total : null;
  }

  function recalculer() {
    var poids = lirePoids();
    AXES.forEach(function (a) {
      document.getElementById("sortie-" + a.id).textContent = NIVEAUX[poids[a.id]];
    });
    try { localStorage.setItem(CLE_POIDS, JSON.stringify(poids)); } catch (e) { /* stockage indisponible */ }

    villes.forEach(function (f) {
      var s = score(f.properties, poids);
      f.properties.score = s === null ? -1 : Math.round(s * 10) / 10;
    });
    // Couleur au rang : les scores se tassent autour de 50, le rang étale la palette.
    var notees = villes.filter(function (f) { return f.properties.score >= 0; })
      .sort(function (a, b) { return a.properties.score - b.properties.score; });
    villes.forEach(function (f) { f.properties.pos = -1; });
    notees.forEach(function (f, i) {
      f.properties.pos = notees.length > 1 ? (100 * i) / (notees.length - 1) : 50;
    });
    if (carte && carte.getSource("villes")) carte.getSource("villes").setData(donnees);
    afficherClassement();
  }

  function pastille(s, pos) {
    var t = E.teinte(pos < 0 ? null : pos);
    return '<span class="note" style="background:' + t.fond + ";color:" + t.texte + '">' +
      (s < 0 ? "n.d." : Math.round(s)) + "</span>";
  }

  function afficherClassement() {
    var tries = villes.slice().sort(function (a, b) { return b.properties.score - a.properties.score; });
    var aucun = AXES.every(function (a) { return lirePoids()[a.id] === 0; });
    var liste = document.getElementById("classement");
    if (aucun) {
      liste.innerHTML = "<li>Donnez de l'importance à au moins un axe pour classer les villes.</li>";
      return;
    }
    liste.innerHTML = tries.slice(0, 10).map(function (f, i) {
      var p = f.properties;
      return '<li><a href="villes/' + p.slug + '/" data-id="' + f.id + '">' +
        '<span class="rang">' + (i + 1) + "</span>" +
        '<span class="nom">' + echapper(p.nom) + "<small>(" + echapper(p.dep) + ")</small></span>" +
        pastille(p.score, p.pos) + "</a></li>";
    }).join("");
  }

  function contenuBulle(p) {
    var barres = AXES.map(function (a) {
      var note = p["axe_" + a.id];
      return '<div class="barre"><span>' + a.libelle + '</span><span class="piste"><i style="width:' +
        (note || 0) + '%"></i></span><b>' + (note === null ? "n.d." : Math.round(note)) + "</b></div>";
    }).join("");
    return '<div class="bulle">' +
      '<div class="tete"><div><h3>' + echapper(p.nom) + '</h3><span class="dep">' +
      echapper(p.departement) + " (" + echapper(p.dep) + ")</span></div>" + pastille(p.score, p.pos) + "</div>" +
      '<div class="barres">' + barres + "</div>" +
      "<dl><dt>Étudiants inscrits</dt><dd>" + E.nombre(p.etudiants) + "</dd>" +
      "<dt>Loyer estimé</dt><dd>" + E.nombre(p.loyer_m2, 1, "€/m²") + "</dd>" +
      "<dt>Rendement brut indicatif</dt><dd>" +
      (p.rendement === null ? "n.d." : E.nombre(p.rendement * 100, 1, "%")) + "</dd></dl>" +
      '<a href="villes/' + p.slug + '/">Voir la fiche de ' + echapper(p.nom) + " →</a></div>";
  }

  function etroit() {
    return window.matchMedia("(max-width: 760px)").matches;
  }

  function ouvrir(f, voler) {
    var p = villes[f.id].properties;
    var coord = villes[f.id].geometry.coordinates;
    // Sur téléphone la carte est basse : on remonte le point pour laisser place à la bulle.
    var decalage = etroit() ? [0, -carte.getContainer().clientHeight * 0.3] : [0, 0];
    if (voler) {
      carte.flyTo({ center: coord, zoom: Math.max(carte.getZoom(), 9), offset: decalage, essential: true });
    } else if (etroit()) {
      carte.easeTo({ center: coord, offset: decalage });
    }
    if (bulle) bulle.remove();
    bulle = new maplibregl.Popup({ offset: 10, maxWidth: "300px", anchor: etroit() ? "top" : undefined })
      .setLngLat(coord).setHTML(contenuBulle(p)).addTo(carte);
  }

  function preparerRecherche() {
    var champ = document.getElementById("recherche");
    var liste = document.getElementById("suggestions");
    var choix = [];
    var actif = -1;
    function normaliser(t) {
      return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-'’]/g, " ");
    }
    function fermer() {
      liste.hidden = true;
      champ.setAttribute("aria-expanded", "false");
      actif = -1;
    }
    function choisir(f) {
      champ.value = f.properties.nom;
      fermer();
      ouvrir(f, true);
    }
    function marquer() {
      Array.prototype.forEach.call(liste.querySelectorAll("button"), function (b, i) {
        b.setAttribute("aria-selected", i === actif ? "true" : "false");
      });
    }
    champ.addEventListener("input", function () {
      var q = normaliser(champ.value.trim());
      if (q.length < 2) { fermer(); return; }
      choix = villes.filter(function (f) { return normaliser(f.properties.nom).indexOf(q) !== -1; })
        .sort(function (a, b) {
          return normaliser(a.properties.nom).indexOf(q) - normaliser(b.properties.nom).indexOf(q) ||
            b.properties.etudiants - a.properties.etudiants;
        }).slice(0, 6);
      if (!choix.length) {
        liste.innerHTML = "<li><small>Aucune des " + villes.length + " villes ne correspond.</small></li>";
      } else {
        liste.innerHTML = choix.map(function (f, i) {
          return '<li><button type="button" role="option" data-i="' + i + '">' + echapper(f.properties.nom) +
            "<small>" + echapper(f.properties.departement) + "</small></button></li>";
        }).join("");
      }
      liste.hidden = false;
      champ.setAttribute("aria-expanded", "true");
    });
    champ.addEventListener("keydown", function (e) {
      if (liste.hidden || !choix.length) return;
      if (e.key === "ArrowDown") { actif = (actif + 1) % choix.length; marquer(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { actif = (actif - 1 + choix.length) % choix.length; marquer(); e.preventDefault(); }
      else if (e.key === "Enter") { choisir(choix[Math.max(actif, 0)]); e.preventDefault(); }
      else if (e.key === "Escape") { fermer(); }
    });
    liste.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (b) choisir(choix[Number(b.getAttribute("data-i"))]);
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".recherche")) fermer();
    });
  }

  function preparerPoids() {
    try {
      var memo = JSON.parse(localStorage.getItem(CLE_POIDS) || "null");
      if (memo) AXES.forEach(function (a) {
        if (typeof memo[a.id] === "number") document.getElementById("poids-" + a.id).value = memo[a.id];
      });
    } catch (e) { /* stockage indisponible */ }
    AXES.forEach(function (a) {
      document.getElementById("poids-" + a.id).addEventListener("input", recalculer);
    });
    document.getElementById("reinitialiser").addEventListener("click", function () {
      AXES.forEach(function (a) { document.getElementById("poids-" + a.id).value = 2; });
      recalculer();
    });
  }

  function couleurs() {
    var r = E.RAMPE;
    return ["case", ["<", ["get", "pos"], 0], "#cfd4cc",
      ["interpolate", ["linear"], ["get", "pos"], 0, r[0], 25, r[1], 50, r[2], 75, r[3], 100, r[4]]];
  }

  function rayon(facteur) {
    return ["+", 2.5 * facteur, ["*", 0.019 * facteur, ["sqrt", ["get", "etudiants"]]]];
  }

  function demarrer(geo) {
    donnees = geo;
    villes = geo.features;
    preparerPoids();
    recalculer();
    preparerRecherche();

    carte = new maplibregl.Map({
      container: "carte",
      style: E.style(),
      bounds: VUES.metropole.bounds,
      fitBoundsOptions: { padding: 24 },
      maxZoom: 15,
      attributionControl: { compact: true }
    });
    carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    carte.on("load", function () {
      carte.addSource("villes", { type: "geojson", data: donnees });
      carte.addLayer({
        id: "villes",
        type: "circle",
        source: "villes",
        layout: { "circle-sort-key": ["-", 0, ["get", "etudiants"]] },
        paint: {
          "circle-color": couleurs(),
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, rayon(1), 8, rayon(2.2), 12, rayon(3.5)],
          "circle-stroke-color": getComputedStyle(document.documentElement).getPropertyValue("--point-trait").trim() || "#18211f",
          "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 4, 0.6, 10, 1.2],
          "circle-opacity": 0.95
        }
      });
      E.fondDeSecours(carte, "./");
    });
    carte.on("click", "villes", function (e) { ouvrir(e.features[0], false); });
    carte.on("mouseenter", "villes", function () { carte.getCanvas().style.cursor = "pointer"; });
    carte.on("mouseleave", "villes", function () { carte.getCanvas().style.cursor = ""; });

    document.querySelector(".outremer").addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      var vue = VUES[b.getAttribute("data-vue")];
      if (vue.bounds) carte.fitBounds(vue.bounds, { padding: 24 });
      else carte.flyTo({ center: vue.center, zoom: vue.zoom, essential: true });
    });
  }

  fetch("data/villes.geojson")
    .then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(demarrer)
    .catch(function () {
      document.getElementById("classement").innerHTML =
        "<li>Les données des villes n'ont pas pu être chargées. Rechargez la page.</li>";
    });
})();
