// Arbre des parcours : bac → spécialités → famille de formation → diplôme visé → formation.
// Chaque clic ouvre la colonne suivante ; le détail du dernier nœud choisi s'affiche dessous.
(function () {
  "use strict";

  var zone = document.getElementById("arbre");
  var detail = document.getElementById("arbre-detail");
  if (!zone || !detail) return;
  var racine = zone.getAttribute("data-racine") || "../";

  var BACS = [
    {
      libelle: "Bac général",
      texte: "Le bac général ouvre toutes les familles de formation. Les spécialités de première et de terminale pèsent dans les formations sélectives : choisissez votre doublette dans la colonne suivante pour voir où sont allés les élèves qui l'avaient."
    },
    {
      libelle: "Bac technologique",
      texte: "Les bacs technologiques mènent surtout aux BTS et aux BUT, où des places leur sont réservées, ainsi qu'aux diplômes paramédicaux et sociaux. Une prépa technologique (TSI, TB, TPC, ECT) ouvre aussi les grandes écoles."
    },
    {
      libelle: "Bac professionnel",
      texte: "Le bac professionnel mène d'abord aux BTS, où des places lui sont réservées, et aux certificats de spécialisation. Les admissions parallèles permettent ensuite d'aller plus loin."
    }
  ];
  var MAX_FORMATIONS = 12;

  var d = null;
  var etat = { bac: null, doublette: null, famille: null, niveau: null, mention: null, tout: false };
  var dernier = null;

  function echapper(texte) {
    return String(texte).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function nombre(n) {
    return n.toLocaleString("fr-FR");
  }

  function admisMention(m) {
    return m[4] ? m[4][etat.bac] : 0;
  }

  function niveauDe(m) {
    return m[2] === null ? "v" : String(Math.min(m[2], 5));
  }

  function libelleNiveau(cle) {
    return cle === "v" ? "Niveau variable" : d.niveaux[cle];
  }

  // Les niveaux et formations n'ont pas le détail par spécialités : on compte tous les admis du bac.
  function mesureBac() {
    return "admis avec un " + BACS[etat.bac].libelle.toLowerCase() +
      (etat.bac === 0 && etat.doublette ? ", toutes spécialités" : "");
  }

  function trier(noeuds) {
    return noeuds.sort(function (a, b) { return b.valeur - a.valeur || a.libelle.localeCompare(b.libelle, "fr"); });
  }

  // Colonnes à afficher pour l'état courant.
  function colonnes() {
    var cols = [];
    cols.push({
      cle: "bac", titre: "Votre bac", mesure: "admis en " + d.session,
      noeuds: BACS.map(function (b, i) {
        var total = 0;
        Object.keys(d.familles).forEach(function (f) { if (d.familles[f].admis) total += d.familles[f].admis[i]; });
        return { id: i, libelle: b.libelle, valeur: total };
      })
    });
    if (etat.bac === null) return cols;

    if (etat.bac === 0) {
      var parDoublette = {};
      Object.keys(d.familles).forEach(function (f) {
        var dbl = d.familles[f].doublettes;
        Object.keys(dbl).forEach(function (k) { parDoublette[k] = (parDoublette[k] || 0) + dbl[k]; });
      });
      var total = 0;
      var noeuds = Object.keys(parDoublette).map(function (k) {
        total += parDoublette[k];
        return { id: k, libelle: k, valeur: parDoublette[k] };
      });
      noeuds = trier(noeuds).slice(0, 12);
      noeuds.unshift({ id: "", libelle: "Toutes les spécialités", valeur: total, toutes: true });
      cols.push({ cle: "doublette", titre: "Vos spécialités", mesure: "bacheliers généraux admis", noeuds: noeuds });
      if (etat.doublette === null) return cols;
    }

    var parDbl = etat.bac === 0 && etat.doublette;
    cols.push({
      cle: "famille", titre: "Après le bac", mesure: parDbl ? "admis avec ces spécialités" : "admis",
      noeuds: trier(Object.keys(d.familles).map(function (f) {
        var fam = d.familles[f];
        var v = parDbl ? fam.doublettes[etat.doublette] || 0 : fam.admis ? fam.admis[etat.bac] : 0;
        return { id: f, libelle: fam.titre, valeur: v };
      }).filter(function (n) { return n.valeur > 0; }))
    });
    if (etat.famille === null) return cols;

    var groupes = {};
    d.mentions.forEach(function (m) {
      if (m[1] !== etat.famille) return;
      var cle = niveauDe(m);
      groupes[cle] = groupes[cle] || { id: cle, libelle: libelleNiveau(cle), valeur: 0, nb: 0 };
      groupes[cle].valeur += admisMention(m);
      groupes[cle].nb += 1;
    });
    cols.push({
      cle: "niveau", titre: "Diplôme visé", mesure: mesureBac(),
      noeuds: Object.keys(groupes).sort().map(function (k) {
        var g = groupes[k];
        g.detail = g.nb + (g.nb > 1 ? " formations" : " formation");
        return g;
      })
    });
    if (etat.niveau === null) return cols;

    var mentions = trier(d.mentions.map(function (m, i) {
      return { id: i, libelle: m[0], valeur: admisMention(m), m: m };
    }).filter(function (n) { return n.m[1] === etat.famille && niveauDe(n.m) === etat.niveau; }));
    var reste = mentions.length - MAX_FORMATIONS;
    if (!etat.tout && reste > 0) {
      mentions = mentions.slice(0, MAX_FORMATIONS);
      mentions.push({ id: "tout", libelle: "Voir les " + reste + " autres", valeur: 0, plus: true });
    }
    cols.push({ cle: "mention", titre: "Formation", mesure: mesureBac(), noeuds: mentions });
    return cols;
  }

  // Sur téléphone, les colonnes deviennent des étapes empilées : les choix faits se replient.
  function vertical() {
    return window.matchMedia("(max-width: 760px)").matches;
  }

  function noeudHtml(c, n, max) {
    var choisi = String(etat[c.cle]) === String(n.id) && !n.plus;
    var largeur = max > 0 ? Math.max(2, Math.round((100 * n.valeur) / max)) : 0;
    return '<li><button type="button" class="noeud' + (choisi ? " choisi" : "") + (n.plus ? " plus" : "") +
      '" data-cle="' + c.cle + '" data-id="' + echapper(n.id) + '" aria-pressed="' + choisi + '">' +
      '<span class="noeud-nom">' + echapper(n.libelle) + "</span>" +
      (n.plus ? "" : '<span class="noeud-barre"><i style="width:' + largeur + '%"></i></span>' +
        '<span class="noeud-val">' + (n.valeur > 0 ? nombre(n.valeur) : "n.d.") +
        (n.detail ? " · " + n.detail : "") + "</span>") +
      "</button></li>";
  }

  function maxDe(c) {
    var max = 0;
    c.noeuds.forEach(function (n) { max = Math.max(max, n.valeur); });
    return max;
  }

  function dessinerVertical(cols) {
    var html = '<ol class="etapes-arbre">';
    cols.forEach(function (c, i) {
      var choix = etat[c.cle] === null ? null : c.noeuds.filter(function (n) {
        return String(n.id) === String(etat[c.cle]) && !n.plus;
      })[0];
      var derniere = i === cols.length - 1;
      if (choix && (!derniere || c.cle === "mention")) {
        html += '<li class="etape faite"><span class="etape-titre">' + c.titre + "</span>" +
          '<button type="button" class="etape-choix" data-rouvrir="' + c.cle + '">' +
          '<span class="noeud-nom">' + echapper(choix.libelle) + "</span>" +
          '<span class="noeud-val">' + (choix.valeur > 0 ? nombre(choix.valeur) + " " + c.mesure : "") + "</span>" +
          '<span class="etape-modifier">Changer</span></button></li>';
      } else {
        var max = maxDe(c);
        html += '<li class="etape ouverte"><span class="etape-titre">' + c.titre + " <small>" + c.mesure +
          '</small></span><ul role="list">' + c.noeuds.map(function (n) { return noeudHtml(c, n, max); }).join("") +
          "</ul></li>";
      }
    });
    zone.classList.add("arbre-vertical");
    zone.innerHTML = html + "</ol>";
  }

  function dessiner() {
    var cols = colonnes();
    if (vertical()) {
      dessinerVertical(cols);
      return;
    }
    zone.classList.remove("arbre-vertical");
    var html = '<svg class="arbre-liens" aria-hidden="true"></svg><div class="arbre-colonnes">';
    cols.forEach(function (c) {
      var max = 0;
      c.noeuds.forEach(function (n) { max = Math.max(max, n.valeur); });
      html += '<div class="arbre-col" data-cle="' + c.cle + '"><div class="arbre-tete"><b>' + c.titre +
        "</b><small>" + c.mesure + '</small></div><ul role="list">';
      c.noeuds.forEach(function (n) { html += noeudHtml(c, n, max); });
      html += "</ul></div>";
    });
    zone.innerHTML = html + "</div>";
    relier();
  }

  // Courbes entre le nœud choisi d'une colonne et tous les nœuds de la suivante.
  function relier() {
    var svg = zone.querySelector(".arbre-liens");
    var boite = zone.querySelector(".arbre-colonnes");
    var ref = boite.getBoundingClientRect();
    svg.setAttribute("width", boite.scrollWidth);
    svg.setAttribute("height", boite.scrollHeight);
    var chemins = "";
    var cols = zone.querySelectorAll(".arbre-col");
    for (var i = 1; i < cols.length; i++) {
      var depart = cols[i - 1].querySelector(".noeud.choisi");
      if (!depart) continue;
      var a = depart.getBoundingClientRect();
      var x1 = a.right - ref.left, y1 = a.top + a.height / 2 - ref.top;
      Array.prototype.forEach.call(cols[i].querySelectorAll(".noeud"), function (n) {
        var b = n.getBoundingClientRect();
        var x2 = b.left - ref.left, y2 = b.top + b.height / 2 - ref.top;
        var mx = (x1 + x2) / 2;
        chemins += '<path d="M' + x1 + " " + y1 + " C" + mx + " " + y1 + " " + mx + " " + y2 + " " + x2 + " " + y2 +
          '"' + (n.classList.contains("choisi") ? ' class="actif"' : "") + "/>";
      });
    }
    svg.innerHTML = chemins;
  }

  var ORDRE = ["bac", "doublette", "famille", "niveau", "mention"];

  function choisir(cle, id) {
    if (cle === "mention" && id === "tout") {
      etat.tout = true;
      dessiner();
      return;
    }
    var valeur = cle === "bac" || cle === "mention" ? Number(id) : id;
    etat[cle] = valeur;
    // Changer une branche referme les colonnes qui en dépendaient.
    ORDRE.slice(ORDRE.indexOf(cle) + 1).forEach(function (k) { etat[k] = null; });
    if (cle !== "mention") etat.tout = false;
    if (cle === "bac" && valeur !== 0) etat.doublette = "";
    dernier = cle;
    dessiner();
    afficherDetail();
    amenerALecran(cle);
  }

  // Bureau : la nouvelle colonne entre dans le cadre. Téléphone : l'étape suivante, ou le détail à la fin.
  function amenerALecran(cle) {
    if (!vertical()) {
      zone.scrollTo({ left: zone.scrollWidth, behavior: "smooth" });
      return;
    }
    var cible = cle === "mention" ? detail : zone.querySelector(".etape.ouverte") || detail;
    cible.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function partsFamilles(valeurDe) {
    var total = 0;
    var liste = Object.keys(d.familles).map(function (f) {
      var v = valeurDe(d.familles[f]);
      total += v;
      return { f: f, v: v };
    }).sort(function (a, b) { return b.v - a.v; }).slice(0, 4);
    return liste.filter(function (x) { return x.v > 0; }).map(function (x) {
      return '<button type="button" class="lien-bouton" data-famille="' + x.f + '">' + echapper(d.familles[x.f].titre) +
        "</button> (" + Math.round((100 * x.v) / total) + "&nbsp;%)";
    }).join(", ");
  }

  function afficherDetail() {
    var html = "";
    if (dernier === "bac") {
      var b = etat.bac;
      html = "<h3>" + BACS[b].libelle + "</h3><p>" + BACS[b].texte + "</p><p>Les admis de " + d.session +
        " sont surtout allés en " + partsFamilles(function (f) { return f.admis ? f.admis[b] : 0; }) + ".</p>";
    } else if (dernier === "doublette") {
      var dbl = etat.doublette;
      html = dbl
        ? "<h3>" + echapper(dbl) + "</h3><p>Les bacheliers généraux admis en " + d.session +
          " avec ces spécialités sont surtout allés en " +
          partsFamilles(function (f) { return f.doublettes[dbl] || 0; }) + ".</p>"
        : "<h3>Toutes les spécialités</h3><p>Choisissez une famille de formation pour voir son parcours type.</p>";
    } else if (dernier === "famille" || dernier === "niveau") {
      html = ficheFamille(etat.famille);
      if (dernier === "niveau") {
        html = "<p class=\"arbre-niveau\">" + echapper(libelleNiveau(etat.niveau)) +
          " : choisissez une formation dans la dernière colonne.</p>" + html;
      }
    } else if (dernier === "mention") {
      html = ficheMention(d.mentions[etat.mention]);
    }
    detail.innerHTML = html;
    detail.hidden = !html;
  }

  function ficheFamille(id) {
    var fam = d.familles[id];
    var section = document.getElementById(id);
    var etapes = section ? section.querySelector(".etapes") : null;
    var suites = fam.suites.map(function (s) {
      return '<button type="button" class="niv" data-famille="' + s + '">' + echapper(d.familles[s].titre) + "</button>";
    }).join("");
    return "<h3>" + echapper(fam.titre) + '</h3><p class="niveaux"><span class="niv">Après le bac</span>' +
      '<span class="fleche" aria-hidden="true">→</span><span class="niv niv-sortie">' + echapper(fam.sortie) + "</span></p>" +
      (etapes ? '<dl class="etapes">' + etapes.innerHTML + "</dl>" : "") +
      (suites ? '<p class="arbre-suites"><b>Ensuite, on peut rejoindre :</b> ' + suites + "</p>" : "") +
      '<p><a href="' + racine + "?famille=" + encodeURIComponent(id) + '">Voir les villes qui proposent ces formations →</a></p>';
  }

  function ficheMention(m) {
    var lignes = ["<h3>" + echapper(m[0]) + "</h3>",
      '<p class="niveaux"><span class="niv">Après le bac</span><span class="fleche" aria-hidden="true">→</span>' +
      '<span class="niv niv-sortie">' + (m[2] === null ? "Niveau variable" : m[2] <= 1 ? "1 an" : "Bac+" + m[2]) +
      '</span><span class="acces">' + echapper(d.acces[m[3]]) + "</span></p>"];
    if (m[4]) {
      var total = m[4][0] + m[4][1] + m[4][2];
      var noms = ["bac général", "techno", "pro"];
      lignes.push("<p>Admis en " + d.session + " : " + m[4].map(function (n, i) {
        return n > 0 ? Math.round((100 * n) / total) + "&nbsp;% " + noms[i] : "";
      }).filter(Boolean).join(", ") + ".</p>");
    }
    if (m[5]) {
      lignes.push("<p>Spécialités les plus fréquentes chez les bacheliers généraux admis : " + m[5].map(function (x) {
        return echapper(x[0]) + " (" + x[1] + "&nbsp;%)";
      }).join(", ") + ".</p>");
    }
    lignes.push("<p>Proposée dans " + m[6] + (m[6] > 1 ? " villes" : " ville") + " du site. " +
      '<a href="' + racine + "?formation=" + encodeURIComponent(m[0]) + '">Voir sur la carte →</a> · ' +
      '<button type="button" class="lien-bouton" data-famille="' + m[1] + '">Parcours type de la famille</button></p>');
    return lignes.join("");
  }

  zone.addEventListener("click", function (e) {
    var r = e.target.closest("[data-rouvrir]");
    if (r) {
      var cle = r.getAttribute("data-rouvrir");
      ORDRE.slice(ORDRE.indexOf(cle)).forEach(function (k) { etat[k] = null; });
      if (cle !== "bac" && cle !== "doublette" && etat.bac !== 0) etat.doublette = "";
      etat.tout = false;
      dessiner();
      amenerALecran(cle === "mention" ? "niveau" : cle);
      return;
    }
    var b = e.target.closest(".noeud");
    if (b) choisir(b.getAttribute("data-cle"), b.getAttribute("data-id"));
  });
  // Les passerelles et familles citées dans le détail ouvrent la branche correspondante.
  detail.addEventListener("click", function (e) {
    var b = e.target.closest("[data-famille]");
    if (!b) return;
    if (etat.bac === null) etat.bac = 0;
    if (etat.bac === 0 && etat.doublette === null) etat.doublette = "";
    var f = b.getAttribute("data-famille");
    var v = etat.bac === 0 && etat.doublette ? d.familles[f].doublettes[etat.doublette] || 0 : (d.familles[f].admis || [0, 0, 0])[etat.bac];
    if (!v) etat.doublette = etat.bac === 0 ? "" : etat.doublette;
    choisir("famille", f);
    zone.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  var modeVertical = vertical();
  window.addEventListener("resize", function () {
    if (!d) return;
    if (vertical() !== modeVertical) {
      modeVertical = vertical();
      dessiner();
    } else if (!modeVertical) {
      relier();
    }
  });

  fetch(racine + "data/parcours-arbre.json")
    .then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(function (donnees) {
      d = donnees;
      dessiner();
    })
    .catch(function () {
      zone.innerHTML = "<p>L'arbre des parcours n'a pas pu être chargé. Les fiches ci-dessous restent disponibles.</p>";
    });
})();
