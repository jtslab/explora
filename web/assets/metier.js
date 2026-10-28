// « Je veux devenir… » : on choisit un métier, le site remonte le chemin jusqu'au lycée.
// Les métiers réglementés ont des voies rédigées ; pour les autres, les voies sont déduites
// des formations que le RNCP rattache au métier, regroupées par famille de formation.
(function () {
  "use strict";

  var chemin = document.getElementById("chemin");
  var champ = document.getElementById("metier-recherche");
  var liste = document.getElementById("metier-suggestions");
  var exemples = document.getElementById("metier-exemples");
  if (!chemin || !champ || !liste) return;
  var racine = chemin.getAttribute("data-racine") || "../";

  var MAX_FORMATIONS = 6;
  var MAX_VOIES_AUTO = 4;
  var EXEMPLES = [["avocat", "Avocat"], ["medecin", "Médecin"], ["ingenieur", "Ingénieur"],
    ["infirmier", "Infirmier"], ["plombier", "Plombier"], ["boulanger", "Boulanger"],
    ["chauffeur-routier", "Chauffeur routier"], ["professeur-des-ecoles", "Professeur des écoles"]];
  var VIDES = ["je", "veux", "etre", "devenir", "faire", "travailler", "dans", "de", "des", "du", "d",
    "la", "le", "les", "l", "un", "une", "en", "et", "ou", "a", "au", "aux", "metier", "metiers"];

  var cibles = [];
  var romes = [];
  var arbre = null;
  var choix = [];
  var actif = -1;
  var courant = null;
  var couverts = {};

  function echapper(texte) {
    return String(texte).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function normaliser(t) {
    return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  function mots(q) {
    return normaliser(q).split(" ").filter(function (m) { return m && VIDES.indexOf(m) === -1; });
  }

  // « avocates », « infirmière » : on accepte le mot sans son s ou son e final.
  function contient(cle, mot) {
    if (cle.indexOf(mot) !== -1) return true;
    var court = mot.replace(/s$/, "").replace(/e$/, "");
    return court.length >= 4 && cle.indexOf(court) !== -1;
  }

  function nbVilles(n) {
    return n + (n > 1 ? " villes" : " ville");
  }

  // Textes d'une famille, repris de sa section sur la page.
  function texteFamille(famille, intitule) {
    var section = document.getElementById(famille);
    if (!section) return "";
    var dts = section.querySelectorAll(".etapes dt");
    for (var i = 0; i < dts.length; i++) {
      if (dts[i].textContent.trim() === intitule) {
        var dd = dts[i].nextElementSibling.cloneNode(true);
        var admis = dd.querySelector(".admis");
        if (admis) admis.remove();
        return dd.textContent.replace(/\s+/g, " ").trim();
      }
    }
    return "";
  }

  function preparer(donnees) {
    var noms = {};
    donnees.metiers.forEach(function (m) { noms[m[0]] = m[1]; });
    cibles = donnees.cibles.map(function (c) {
      var x = {
        genre: "cible", id: c.id, titre: c.titre, data: c,
        cle: normaliser([c.titre].concat(c.mots, c.romes.map(function (code) { return noms[code] || ""; })).join(" "))
      };
      c.romes.forEach(function (code) { couverts[code] = x; });
      return x;
    });
    romes = donnees.metiers.filter(function (m) { return !couverts[m[0]]; }).map(function (m) {
      var villes = m[2].reduce(function (s, i) { return s + arbre.mentions[i][6]; }, 0);
      return { genre: "rome", id: m[0], titre: m[1], mentions: m[2], villes: villes, cle: normaliser(m[1]) };
    });
  }

  function chercher(q) {
    var m = mots(q);
    if (!m.length) return [];
    function score(x) { return m.filter(function (w) { return contient(x.cle, w); }).length; }
    var tous = cibles.concat(romes).map(function (x) { return { x: x, s: score(x) }; })
      .filter(function (r) { return r.s > 0; });
    var meilleur = tous.reduce(function (b, r) { return Math.max(b, r.s); }, 0);
    return tous.filter(function (r) { return r.s === meilleur; })
      .sort(function (a, b) {
        return (a.x.genre === "cible" ? 0 : 1) - (b.x.genre === "cible" ? 0 : 1) ||
          (b.x.villes || 0) - (a.x.villes || 0);
      })
      .slice(0, 8).map(function (r) { return r.x; });
  }

  function afficherSuggestions() {
    choix = chercher(champ.value);
    actif = choix.length ? 0 : -1;
    if (!choix.length) {
      if (mots(champ.value).length) {
        liste.innerHTML = '<li class="aucun">Pas encore de chemin pour ce métier. Essayez un mot plus court ou un métier proche.</li>';
        liste.hidden = false;
      } else {
        liste.hidden = true;
      }
      champ.setAttribute("aria-expanded", "false");
      return;
    }
    liste.innerHTML = choix.map(function (x, i) {
      var detail = x.genre === "cible"
        ? x.data.voies.length + (x.data.voies.length > 1 ? " voies" : " voie")
        : x.mentions.length + (x.mentions.length > 1 ? " formations" : " formation");
      return '<li><button type="button" role="option" id="metier-choix-' + i + '" aria-selected="' +
        (i === actif) + '" data-i="' + i + '"><span>' + echapper(x.titre) + "</span><small>" + detail +
        "</small></button></li>";
    }).join("");
    liste.hidden = false;
    champ.setAttribute("aria-expanded", "true");
  }

  function fermer() {
    liste.hidden = true;
    champ.setAttribute("aria-expanded", "false");
  }

  // Voies d'un métier sans chemin rédigé : une par famille de formation, les plus répandues d'abord.
  function voiesAuto(r) {
    var parFamille = {};
    r.mentions.forEach(function (i) {
      var f = arbre.mentions[i][1];
      if (!parFamille[f]) parFamille[f] = { famille: f, mentions: [], villes: 0 };
      parFamille[f].mentions.push(i);
      parFamille[f].villes += arbre.mentions[i][6];
    });
    return Object.keys(parFamille).map(function (k) { return parFamille[k]; })
      .sort(function (a, b) { return b.villes - a.villes; })
      .slice(0, MAX_VOIES_AUTO)
      .map(function (g) {
        var fam = arbre.familles[g.famille];
        g.mentions.sort(function (a, b) { return arbre.mentions[b][6] - arbre.mentions[a][6]; });
        return {
          titre: fam.titre,
          resume: g.mentions.length + (g.mentions.length > 1 ? " formations, " : " formation, ") + nbVilles(g.villes) + " au total",
          lycee: texteFamille(g.famille, "Au lycée"),
          famille: g.famille,
          etapes: [
            ["Après le bac → " + fam.sortie, fam.titre, texteFamille(g.famille, "Comment y entrer"), g.mentions],
            ["Ensuite", "Poursuites et passerelles", texteFamille(g.famille, "Et après"), []]
          ]
        };
      });
  }

  function cheminDe(x) {
    if (x.genre === "cible") {
      var c = x.data;
      return {
        id: c.id, titre: c.titre, metier: c.metier, depart: c.depart, auto: false,
        voies: c.voies.map(function (v) {
          return { titre: v.titre, resume: v.resume, lycee: c.lycee, depart: c.depart, etapes: v.etapes };
        })
      };
    }
    return {
      id: x.id, titre: x.titre, auto: true,
      metier: "Les formations ci-dessus sont celles que le répertoire national des certifications rattache à ce métier (code " + x.id + "). Certains postes demandent un diplôme de plus : la fiche officielle de chaque formation précise les débouchés.",
      voies: voiesAuto(x)
    };
  }

  // Spécialités des bacheliers généraux admis dans les formations d'une étape.
  function specialites(indices) {
    var cumul = {};
    var total = 0;
    indices.forEach(function (i) {
      var m = arbre.mentions[i];
      var poids = m[4] ? m[4][0] : 0;
      if (!m[5] || !poids) return;
      total += poids;
      m[5].forEach(function (d) { cumul[d[0]] = (cumul[d[0]] || 0) + d[1] * poids; });
    });
    if (!total && indices.length) {
      var fam = arbre.familles[arbre.mentions[indices[0]][1]];
      Object.keys(fam.doublettes || {}).forEach(function (d) {
        cumul[d] = fam.doublettes[d] * 100;
        total += fam.doublettes[d];
      });
    }
    if (!total) return [];
    return Object.keys(cumul).map(function (d) { return [d, Math.round(cumul[d] / total)]; })
      .sort(function (a, b) { return b[1] - a[1]; })
      .filter(function (d) { return d[1] > 0; })
      .slice(0, 3);
  }

  // Formations d'une étape : [libellé, nombre de villes], post-bac (indices de l'arbre) puis voie pro.
  function formationsEtape(e) {
    return e[3].map(function (i) { return [arbre.mentions[i][0], arbre.mentions[i][6]]; }).concat(e[4] || []);
  }

  function puces(liste, tout) {
    var vus = tout ? liste : liste.slice(0, MAX_FORMATIONS);
    var html = '<ul class="frise-formations">' + vus.map(function (m) {
      return '<li><a href="' + racine + "?formation=" + encodeURIComponent(m[0]) + '">' + echapper(m[0]) +
        "<small>" + nbVilles(m[1]) + "</small></a></li>";
    }).join("") + "</ul>";
    if (!tout && liste.length > MAX_FORMATIONS) {
      html += '<button type="button" class="frise-plus" data-tout>Voir les ' + (liste.length - MAX_FORMATIONS) +
        " autres formations</button>";
    }
    return html;
  }

  function frise(c, v, tout) {
    var premiere = v.etapes.find(function (e) { return e[3].length; });
    // Les spécialités des bacheliers généraux n'éclairent pas un départ après la 3e.
    var spe = premiere && (!v.depart || v.depart === "Lycée") ? specialites(premiere[3]) : [];
    var html = '<ol class="frise">';
    html += '<li class="frise-etape"><span class="niv">' + echapper(v.depart || "Lycée") + "</span><h4>" +
      (!v.depart || v.depart === "Lycée" ? "Bac et spécialités" : "Point de départ") + "</h4><p>" + echapper(v.lycee) + "</p>" +
      (spe.length ? '<p class="frise-donnee">Bacheliers généraux admis en ' + echapper(arbre.session) + " dans ces formations : " +
        spe.map(function (d) { return echapper(d[0]) + " (" + d[1] + " %)"; }).join(", ") + ".</p>" : "") + "</li>";
    v.etapes.forEach(function (e) {
      html += '<li class="frise-etape"><span class="niv">' + echapper(e[0]) + "</span><h4>" + echapper(e[1]) + "</h4>" +
        (e[2] ? "<p>" + echapper(e[2]) + "</p>" : "") +
        (formationsEtape(e).length ? '<p class="frise-donnee">Dans les villes du site :</p>' + puces(formationsEtape(e), tout) : "") + "</li>";
    });
    html += '<li class="frise-etape frise-arrivee"><span class="niv niv-sortie">Métier</span><h4>' + echapper(c.titre) + "</h4>" +
      (c.metier ? "<p>" + echapper(c.metier) + "</p>" : "") +
      (v.famille ? '<p><a href="#' + v.famille + '">Le parcours type de cette famille de formation ↓</a></p>' : "") + "</li>";
    return html + "</ol>";
  }

  function afficher(c, n, tout) {
    courant = { c: c, n: n };
    if (!c.voies.length) {
      chemin.innerHTML = "<h3>" + echapper(c.titre) + "</h3><p>Aucune formation du site n'est rattachée à ce métier.</p>";
      chemin.hidden = false;
      return;
    }
    var v = c.voies[n];
    var html = "<h3>" + (c.auto ? "Métier : " + echapper(c.titre)
      : "Devenir " + echapper(c.titre.charAt(0).toLowerCase() + c.titre.slice(1))) + "</h3>" +
      '<p class="chemin-aide">' + (c.voies.length > 1
        ? c.voies.length + " voies possibles. Choisissez-en une pour voir le chemin jusqu'au métier."
        : "Le chemin jusqu'au métier.") +
      (c.depart && c.depart !== "Lycée" ? " Les CAP et bacs pro se préparent en lycée professionnel ou en apprentissage : touchez une formation pour voir les villes qui la proposent. Les titres professionnels, préparés en centre de formation pour adultes, ne sont pas sur la carte." : "") +
      (c.auto ? " Chemin établi d'après les formations qui mènent à ce métier." : "") + "</p>";
    if (c.voies.length > 1) {
      html += '<div class="voies" role="tablist" aria-label="Voies possibles">' + c.voies.map(function (x, i) {
        var fin = x.etapes[x.etapes.length - 1][0];
        return '<button type="button" role="tab" class="voie' + (i === n ? " choisie" : "") + '" aria-selected="' + (i === n) +
          '" data-voie="' + i + '"><small>Voie ' + (i + 1) + (c.auto || (c.depart && c.depart !== "Lycée") ? "" : " · " + echapper(fin)) + "</small><b>" +
          echapper(x.titre) + "</b>" + (x.resume ? "<span>" + echapper(x.resume) + "</span>" : "") + "</button>";
      }).join("") + "</div>";
    }
    html += '<div role="tabpanel">' + frise(c, v, tout) + "</div>";
    chemin.innerHTML = html;
    chemin.hidden = false;
  }

  function choisir(x, defiler) {
    fermer();
    champ.value = x.titre;
    afficher(cheminDe(x), 0, false);
    try {
      history.replaceState(null, "", "?metier=" + encodeURIComponent(x.id) + location.hash);
    } catch (e) { /* adresse inchangée */ }
    if (defiler) chemin.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function trouver(id) {
    var c = cibles.find(function (x) { return x.id === id; });
    if (c) return c;
    if (couverts[id]) return couverts[id];
    return romes.find(function (x) { return x.id === id; }) || null;
  }

  champ.addEventListener("input", afficherSuggestions);
  champ.addEventListener("focus", function () { if (champ.value) afficherSuggestions(); });
  champ.addEventListener("keydown", function (e) {
    if (liste.hidden) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      actif = (actif + (e.key === "ArrowDown" ? 1 : choix.length - 1)) % choix.length;
      liste.querySelectorAll("button").forEach(function (b, i) { b.setAttribute("aria-selected", i === actif ? "true" : "false"); });
      champ.setAttribute("aria-activedescendant", "metier-choix-" + actif);
    } else if (e.key === "Enter" && actif >= 0) {
      e.preventDefault();
      choisir(choix[actif], false);
    } else if (e.key === "Escape") {
      fermer();
    }
  });
  liste.addEventListener("mousedown", function (e) { e.preventDefault(); });
  liste.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-i]");
    if (b) choisir(choix[Number(b.getAttribute("data-i"))], false);
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".recherche-metier")) fermer();
  });
  chemin.addEventListener("click", function (e) {
    var voie = e.target.closest("[data-voie]");
    if (voie && courant) {
      afficher(courant.c, Number(voie.getAttribute("data-voie")), false);
      var panneau = chemin.querySelector("[role=tabpanel]");
      if (panneau && panneau.getBoundingClientRect().top > window.innerHeight * 0.6) {
        panneau.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      return;
    }
    if (e.target.closest("[data-tout]") && courant) afficher(courant.c, courant.n, true);
  });
  if (exemples) {
    exemples.addEventListener("click", function (e) {
      var b = e.target.closest("[data-metier]");
      if (b) {
        var x = trouver(b.getAttribute("data-metier"));
        if (x) choisir(x, true);
      }
    });
  }

  Promise.all([
    fetch(racine + "data/metiers-cibles.json").then(function (r) { return r.json(); }),
    fetch(racine + "data/parcours-arbre.json").then(function (r) { return r.json(); })
  ]).then(function (res) {
    arbre = res[1];
    preparer(res[0]);
    champ.disabled = false;
    if (exemples) {
      exemples.innerHTML = "<span>Par exemple :</span>" + EXEMPLES
        .filter(function (e) { return trouver(e[0]); }).map(function (e) {
          return '<button type="button" class="niv" data-metier="' + e[0] + '">' + e[1] + "</button>";
        }).join("");
    }
    var demande = new URLSearchParams(location.search).get("metier");
    var x = demande ? trouver(demande) : null;
    if (x) choisir(x, false);
  }).catch(function () {
    chemin.innerHTML = "<p>Les chemins vers les métiers n'ont pas pu être chargés.</p>";
    chemin.hidden = false;
  });
})();
