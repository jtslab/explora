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
  var GROUPES = { ville: "Villes", metier: "Métiers", secteur: "Secteurs d'activité", formation: "Formations" };

  var E = window.Explora;
  var villes = [];
  var donnees = null;
  var carte = null;
  var bulle = null;
  var formations = null;
  var filtre = null;

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
    villes.forEach(function (f) { f.properties.actif = !filtre || filtre.ids.has(f.id) ? 1 : 0; });
    if (carte && carte.getSource("villes")) carte.getSource("villes").setData(donnees);
    afficherClassement();
  }

  function pastille(s, pos) {
    var t = E.teinte(pos < 0 ? null : pos);
    return '<span class="note" style="background:' + t.fond + ";color:" + t.texte + '">' +
      (s < 0 ? "n.d." : Math.round(s)) + "</span>";
  }

  function afficherClassement() {
    var tries = villes.filter(function (f) { return f.properties.actif; })
      .sort(function (a, b) { return b.properties.score - a.properties.score; });
    var aucun = AXES.every(function (a) { return lirePoids()[a.id] === 0; });
    var liste = document.getElementById("classement");
    document.getElementById("titre-classement").textContent = filtre
      ? "Les 10 premières avec une formation correspondante"
      : "Les 10 premières avec vos réglages";
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
      '<div class="barres">' + barres + "</div>" + formationsBulle(p) +
      "<dl><dt>Étudiants inscrits</dt><dd>" + E.nombre(p.etudiants) + "</dd>" +
      "<dt>Loyer estimé</dt><dd>" + E.nombre(p.loyer_m2, 1, "€/m²") + "</dd>" +
      "<dt>Rendement brut indicatif</dt><dd>" +
      (p.rendement === null ? "n.d." : E.nombre(p.rendement * 100, 1, "%")) + "</dd></dl>" +
      '<a href="villes/' + p.slug + "/" + (filtre ? "#formations" : "") + '">Voir la fiche de ' + echapper(p.nom) + " →</a></div>";
  }

  function formationsBulle(p) {
    if (!filtre || !formations) return "";
    var trouvees = formations.parVille[p.id_carte].filter(function (i) { return filtre.mentions.has(i); });
    if (!trouvees.length) return '<p class="bulle-formations">Aucune formation de cette recherche ici.</p>';
    var noms = trouvees.slice(0, 3).map(function (i) { return echapper(formations.mentions[i].libelle); });
    var reste = trouvees.length > 3 ? "<li>et " + (trouvees.length - 3) + " autres</li>" : "";
    return '<ul class="bulle-formations"><li>' + noms.join("</li><li>") + "</li>" + reste + "</ul>";
  }

  function etroit() {
    return window.matchMedia("(max-width: 760px)").matches;
  }

  function ouvrir(f, voler) {
    var p = villes[f.id].properties;
    p.id_carte = f.id;
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

  function normaliser(t) {
    return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  // Tous les mots de la requête doivent apparaître (« commerce international »).
  function correspond(texte, mots) {
    return mots.every(function (m) { return texte.indexOf(m) !== -1; });
  }

  function preparerFormations(index) {
    var parVille = villes.map(function () { return []; });
    var code = {};
    villes.forEach(function (f) { code[f.properties.code] = f.id; });
    formations = {
      session: index.session,
      types: index.types.map(function (t) { return { libelle: t, cle: normaliser(t) }; }),
      mentions: index.mentions.map(function (m, i) {
        var ids = m[2].map(function (c) { return code[c]; }).filter(function (id) { return id !== undefined; });
        ids.forEach(function (id) { parVille[id].push(i); });
        return { libelle: m[0], cle: normaliser(m[0]), type: m[1], ids: ids };
      }),
      parVille: parVille,
      metiers: (index.metiers || []).map(function (m) {
        return { code: m[0], libelle: m[1], cle: normaliser(m[1]), mentions: m[2] };
      }),
      secteurs: (index.secteurs || []).map(function (d) {
        return { lettre: d[0], libelle: d[1], cle: normaliser(d[1]) };
      })
    };
    var metiers = formations.metiers.length > 0;
    document.getElementById("recherche").placeholder = metiers
      ? "Ville, métier, secteur, formation : Rennes, infirmier, santé…"
      : "Une ville, une formation : Rennes, infirmier, BTS tourisme…";
    document.getElementById("libelle-recherche").textContent = metiers
      ? "Chercher une ville, un métier ou une formation"
      : "Chercher une ville ou une formation";
  }

  function appliquerFiltre(nouveau) {
    filtre = nouveau;
    var zone = document.getElementById("filtre");
    if (filtre) {
      document.getElementById("filtre-libelle").textContent = filtre.libelle;
      document.getElementById("filtre-nombre").textContent =
        filtre.ids.size + (filtre.ids.size > 1 ? " villes avec une formation qui y mène" : " ville avec une formation qui y mène");
      zone.hidden = false;
    } else {
      zone.hidden = true;
    }
    if (bulle) bulle.remove();
    recalculer();
    if (filtre && carte && filtre.ids.size) {
      var bornes = new maplibregl.LngLatBounds();
      filtre.ids.forEach(function (id) {
        var c = villes[id].geometry.coordinates;
        // L'outre-mer étirerait le cadrage sur la moitié du globe.
        if (c[0] > -6 && c[0] < 10 && c[1] > 41) bornes.extend(c);
      });
      if (!bornes.isEmpty()) carte.fitBounds(bornes, { padding: 40, maxZoom: 9 });
    }
  }

  function filtreMentions(libelle, indices) {
    var ids = new Set();
    indices.forEach(function (i) { formations.mentions[i].ids.forEach(function (id) { ids.add(id); }); });
    return { libelle: libelle, mentions: new Set(indices), ids: ids };
  }

  function nbVilles(f) {
    return f.ids.size + (f.ids.size > 1 ? " villes" : " ville");
  }

  function suggestionsMetiers(mots) {
    var res = [];
    formations.metiers
      .filter(function (m) { return correspond(m.cle, mots); })
      .map(function (m) { return { m: m, f: filtreMentions("Métier : " + m.libelle, m.mentions) }; })
      .sort(function (a, b) { return b.f.ids.size - a.f.ids.size; })
      .slice(0, 4)
      .forEach(function (x) {
        res.push({ genre: "metier", filtre: x.f, texte: x.m.libelle, detail: nbVilles(x.f) });
      });
    formations.secteurs
      .filter(function (d) { return correspond(d.cle, mots); })
      .slice(0, 2)
      .forEach(function (d) {
        var indices = [];
        formations.metiers.forEach(function (m) {
          if (m.code.charAt(0) === d.lettre) indices = indices.concat(m.mentions);
        });
        var f = filtreMentions("Secteur : " + d.libelle, indices);
        res.push({ genre: "secteur", filtre: f, texte: d.libelle, detail: nbVilles(f) });
      });
    return res;
  }

  function suggestions(q) {
    var mots = q.split(" ");
    var res = villes.filter(function (f) { return correspond(normaliser(f.properties.nom), mots); })
      .sort(function (a, b) {
        return normaliser(a.properties.nom).indexOf(mots[0]) - normaliser(b.properties.nom).indexOf(mots[0]) ||
          b.properties.etudiants - a.properties.etudiants;
      }).slice(0, formations ? 3 : 6)
      .map(function (f) { return { genre: "ville", f: f, texte: f.properties.nom, detail: f.properties.departement }; });
    if (!formations) return res;
    res = res.concat(suggestionsMetiers(mots));

    var types = [];
    formations.types.forEach(function (t, i) { if (correspond(t.cle, mots)) types.push(i); });
    var trouvees = [];
    formations.mentions.forEach(function (m, i) {
      if (correspond(m.cle, mots) || types.indexOf(m.type) !== -1) trouvees.push(i);
    });
    trouvees.sort(function (a, b) { return formations.mentions[b].ids.length - formations.mentions[a].ids.length; });
    if (trouvees.length > 1) {
      res.push({
        genre: "formation",
        filtre: filtreMentions("Formations « " + q + " »", trouvees),
        texte: "Toutes les formations « " + q + " »",
        detail: trouvees.length + " formations"
      });
    }
    trouvees.slice(0, 5).forEach(function (i) {
      var m = formations.mentions[i];
      res.push({
        genre: "formation",
        filtre: filtreMentions(m.libelle, [i]),
        texte: m.libelle,
        detail: m.ids.length + (m.ids.length > 1 ? " villes" : " ville")
      });
    });
    return res;
  }

  function preparerRecherche() {
    var champ = document.getElementById("recherche");
    var liste = document.getElementById("suggestions");
    var choix = [];
    var actif = -1;
    function fermer() {
      liste.hidden = true;
      champ.setAttribute("aria-expanded", "false");
      actif = -1;
    }
    function choisir(s) {
      fermer();
      if (s.genre === "ville") {
        champ.value = s.texte;
        ouvrir(s.f, true);
      } else {
        champ.value = "";
        appliquerFiltre(s.filtre);
      }
      // Sur téléphone la carte est au-dessus du panneau : on la ramène à l'écran.
      if (etroit()) window.scrollTo({ top: 0, behavior: "smooth" });
    }
    function marquer() {
      Array.prototype.forEach.call(liste.querySelectorAll("button"), function (b, i) {
        b.setAttribute("aria-selected", i === actif ? "true" : "false");
      });
    }
    champ.addEventListener("input", function () {
      var q = normaliser(champ.value);
      if (q.length < 2) { fermer(); return; }
      choix = suggestions(q);
      if (!choix.length) {
        liste.innerHTML = "<li><small>Aucune ville ni formation ne correspond.</small></li>";
      } else {
        var groupe = null;
        liste.innerHTML = choix.map(function (s, i) {
          var titre = "";
          if (formations && s.genre !== groupe) {
            groupe = s.genre;
            titre = '<li class="groupe" role="presentation">' + GROUPES[s.genre] + "</li>";
          }
          return titre + '<li><button type="button" role="option" data-i="' + i + '"><span>' + echapper(s.texte) +
            "</span><small>" + echapper(s.detail) + "</small></button></li>";
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
    document.getElementById("filtre-retirer").addEventListener("click", function () {
      appliquerFiltre(null);
      champ.focus();
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
        // Villes retenues par la recherche au-dessus, puis les petites sur les grandes.
        layout: { "circle-sort-key": ["-", ["*", 1e7, ["get", "actif"]], ["get", "etudiants"]] },
        paint: {
          "circle-color": couleurs(),
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, rayon(1), 8, rayon(2.2), 12, rayon(3.5)],
          "circle-stroke-opacity": ["case", ["==", ["get", "actif"], 1], 1, 0.25],
          "circle-stroke-color": getComputedStyle(document.documentElement).getPropertyValue("--point-trait").trim() || "#18211f",
          "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 4, 0.6, 10, 1.2],
          "circle-opacity": ["case", ["==", ["get", "actif"], 1], 0.95, 0.12]
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

  function charger(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + " : " + r.status);
      return r.json();
    });
  }

  charger("data/villes.geojson")
    .then(function (geo) {
      demarrer(geo);
      // La recherche par formation s'ajoute quand l'index est là ; la carte n'en dépend pas.
      return charger("data/formations-index.json").then(preparerFormations, function () {});
    })
    .catch(function () {
      document.getElementById("classement").innerHTML =
        "<li>Les données des villes n'ont pas pu être chargées. Rechargez la page.</li>";
    });
})();
