/* VisaCommunity — minimal vanilla JS (progressive enhancement only) */

// Mobile nav
document.querySelectorAll(".nav-toggle").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var links = document.querySelector(".nav-links");
    var open = links.classList.toggle("open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });
});

// Compose: switch between "Ask a question" and "Share an experience".
// The segmented buttons write into the hidden <input name="kind"> so the
// choice is actually sent to Django with the form.
(function () {
  var seg = document.querySelector("[data-compose-seg]");
  if (!seg) return;
  var extra = document.querySelector("[data-experience-fields]");
  var textarea = document.querySelector("[data-compose-text]");
  var kindInput = document.querySelector("[data-kind-input]");
  var placeholders = {
    question: "What would you like to ask other travelers? e.g. “Which documents did the consulate actually check?”",
    experience: "Tell your story — appointment city, documents, waiting time, the result, and anything you wish you had known."
  };
  function setMode(mode) {
    seg.querySelectorAll("button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.mode === mode ? "true" : "false");
    });
    if (extra) extra.hidden = mode !== "experience";
    if (textarea && !textarea.value) textarea.placeholder = placeholders[mode] || "";
    if (kindInput) kindInput.value = mode;
  }
  seg.querySelectorAll("button").forEach(function (btn) {
    btn.addEventListener("click", function () { setMode(btn.dataset.mode); });
  });
  // Start in whatever mode the server rendered (e.g. after a validation error)
  setMode(kindInput && kindInput.value ? kindInput.value : "question");
})();

// Character counter for the comment textarea
(function () {
  var ta = document.querySelector("[data-compose-text]");
  var counter = document.querySelector("[data-counter]");
  if (!ta || !counter) return;
  var max = parseInt(ta.getAttribute("maxlength") || "2000", 10);
  var update = function () { counter.textContent = ta.value.length + " / " + max; };
  ta.addEventListener("input", update);
  update();
})();

// Guide examples: both languages stay in the HTML. The buttons only hide one.
(function () {
  document.querySelectorAll("[data-lang-seg]").forEach(function (seg) {
    var pair = seg.closest("[data-letter-pair]");
    if (!pair) return;
    pair.classList.add("is-enhanced");
    seg.querySelectorAll("button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var lang = btn.getAttribute("data-lang");
        seg.querySelectorAll("button").forEach(function (other) {
          other.setAttribute("aria-pressed", other === btn ? "true" : "false");
        });
        pair.classList.toggle("show-tr", lang === "tr");
      });
    });
  });
})();

// Letter drafts are built in the browser and are never submitted.
(function () {
  var blanks = {
    en: {
      applicant_name: "[Full name]",
      address: "[Address]",
      letter_date: "[Date]",
      consulate: "[Consulate]",
      purpose: "[purpose of the trip]",
      depart: "[departure date]",
      return_on: "[return date]",
      itinerary: "[dates and cities]",
      accommodation: "[where you will stay]",
      financing: "[who pays, and from what]",
      ties: "[job or school, family, and the day you return]",
      documents: "[list the papers you will attach]",
      sponsor_name: "[Sponsor’s full name]",
      sponsor_id: "[ID number]",
      sponsor_address: "[Address]",
      sponsor_contact: "[Phone or email]",
      relationship: "[relationship]",
      applicant_details: "[student, spouse, or employee]",
      destination: "[destination]"
    },
    tr: {
      applicant_name: "[Ad Soyad]",
      address: "[Adres]",
      letter_date: "[Tarih]",
      consulate: "[Konsolosluk]",
      purpose: "[seyahatin amacı]",
      depart: "[gidiş tarihi]",
      return_on: "[dönüş tarihi]",
      itinerary: "[tarihler ve şehirler]",
      accommodation: "[nerede kalacağınız]",
      financing: "[masrafı kimin, hangi gelirle karşıladığı]",
      ties: "[iş veya okul, aile ve dönüş günü]",
      documents: "[ekteki belgelerin listesi]",
      sponsor_name: "[Sponsorun adı soyadı]",
      sponsor_id: "[Kimlik numarası]",
      sponsor_address: "[Adres]",
      sponsor_contact: "[Telefon veya e-posta]",
      relationship: "[yakınlık]",
      applicant_details: "[öğrenci, eş veya çalışan]",
      destination: "[gidilecek yer]"
    }
  };

  function field(root, name, lang) {
    var input = root.querySelector("[data-field='" + name + "']");
    var value = input && input.value.trim();
    if (value) return value;
    return (blanks[lang] && blanks[lang][name]) || "[" + name + "]";
  }

  function motivation(root, lang) {
    var name = field(root, "applicant_name", lang);
    if (lang === "tr") {
      return [
        name,
        field(root, "address", lang),
        "",
        field(root, "letter_date", lang),
        "",
        field(root, "consulate", lang),
        "",
        "Konu: Kısa süreli Schengen vizesi başvurusu",
        "",
        "Sayın Konsolos,",
        "",
        "Kısa süreli Schengen vizesine başvuruyorum. Seyahatin amacı: " + field(root, "purpose", lang) + ".",
        "",
        "Gidiş tarihim " + field(root, "depart", lang) + ", dönüş tarihim " + field(root, "return_on", lang) + ". Program: " + field(root, "itinerary", lang) + ". Ana varış ülkesi, en uzun kaldığım ülkedir. Kalışlar eşitse, Schengen bölgesine ilk girdiğim ülkedir.",
        "",
        "Konaklama: " + field(root, "accommodation", lang) + ".",
        "",
        "Masraflar: " + field(root, "financing", lang) + ".",
        "",
        "Türkiye’ye bağlarım ve dönüş planım: " + field(root, "ties", lang) + ".",
        "",
        "Ekli belgeler:",
        field(root, "documents", lang),
        "",
        "Saygılarımla,",
        name
      ].join("\n");
    }
    return [
      name,
      field(root, "address", lang),
      "",
      field(root, "letter_date", lang),
      "",
      field(root, "consulate", lang),
      "",
      "Subject: Application for a short-stay Schengen visa",
      "",
      "Dear Consul,",
      "",
      "I am applying for a short-stay Schengen visa. The purpose of my trip is " + field(root, "purpose", lang) + ".",
      "",
      "I plan to travel from " + field(root, "depart", lang) + " to " + field(root, "return_on", lang) + ". Itinerary: " + field(root, "itinerary", lang) + ". The main destination is the country where I stay longest, or the country of first entry if the stays are equal.",
      "",
      "Accommodation: " + field(root, "accommodation", lang) + ".",
      "",
      "Financing: " + field(root, "financing", lang) + ".",
      "",
      "Ties to Türkiye and my return plan: " + field(root, "ties", lang) + ".",
      "",
      "Enclosed documents:",
      field(root, "documents", lang),
      "",
      "Yours faithfully,",
      name
    ].join("\n");
  }

  function sponsorship(root, lang) {
    var sponsor = field(root, "sponsor_name", lang);
    if (lang === "tr") {
      return [
        sponsor,
        "T.C. kimlik numarası: " + field(root, "sponsor_id", lang),
        field(root, "sponsor_address", lang),
        field(root, "sponsor_contact", lang),
        "",
        field(root, "letter_date", lang),
        "",
        "Sayın Konsolos,",
        "",
        "Ben " + sponsor + ", " + field(root, "applicant_name", lang) + " adlı başvuranın " + field(root, "relationship", lang) + " yakınıyım. Başvuran: " + field(root, "applicant_details", lang) + ".",
        "",
        field(root, "applicant_name", lang) + ", " + field(root, "depart", lang) + " ile " + field(root, "return_on", lang) + " tarihleri arasında " + field(root, "destination", lang) + " adresine seyahat edecektir.",
        "",
        "Bu seyahatin uçak, konaklama, günlük masraf ve sigorta dahil tüm masraflarını ben karşılayacağım.",
        "",
        "Saygılarımla,",
        sponsor
      ].join("\n");
    }
    return [
      sponsor,
      "ID number: " + field(root, "sponsor_id", lang),
      field(root, "sponsor_address", lang),
      field(root, "sponsor_contact", lang),
      "",
      field(root, "letter_date", lang),
      "",
      "Dear Consul,",
      "",
      "I am " + sponsor + ", " + field(root, "relationship", lang) + " of " + field(root, "applicant_name", lang) + " (" + field(root, "applicant_details", lang) + ").",
      "",
      field(root, "applicant_name", lang) + " will travel to " + field(root, "destination", lang) + " from " + field(root, "depart", lang) + " to " + field(root, "return_on", lang) + ".",
      "",
      "I will cover all costs of this trip, including travel, accommodation, living expenses, and insurance.",
      "",
      "Yours faithfully,",
      sponsor
    ].join("\n");
  }

  document.querySelectorAll("[data-letter-builder]").forEach(function (root) {
    var output = root.parentElement.parentElement.querySelector("[data-output]");
    var result = root.querySelector("[data-result]");
    var copyBtn = root.querySelector("[data-copy]");
    var lang = "en";
    var langSeg = root.querySelector("[data-output-lang]");
    if (langSeg) {
      langSeg.querySelectorAll("button").forEach(function (btn) {
        btn.addEventListener("click", function () {
          lang = btn.getAttribute("data-lang");
          langSeg.querySelectorAll("button").forEach(function (other) {
            other.setAttribute("aria-pressed", other === btn ? "true" : "false");
          });
        });
      });
    }
    root.querySelector("[data-write]").addEventListener("click", function () {
      var text = root.getAttribute("data-kind") === "sponsorship"
        ? sponsorship(root, lang)
        : motivation(root, lang);
      output.textContent = text;
      output.hidden = false;
      result.hidden = false;
      output.setAttribute("lang", lang === "tr" ? "tr" : "en");
    });
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        var text = output.textContent || "";
        var done = function () { copyBtn.textContent = "Copied"; };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () {
            copyBtn.textContent = "Select the letter and copy it";
          });
        } else {
          copyBtn.textContent = "Select the letter and copy it";
        }
      });
    }
    var printBtn = root.querySelector("[data-print]");
    if (printBtn) {
      printBtn.addEventListener("click", function () {
        document.body.classList.add("printing-letter");
        window.print();
      });
    }
  });

  window.addEventListener("afterprint", function () {
    document.body.classList.remove("printing-letter");
  });
})();

// Helpful marks: update the count in place. A normal POST still works if fetch cannot.
(function () {
  document.querySelectorAll("form.js-like").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.fetch) return;
      event.preventDefault();
      var button = form.querySelector("button");
      var token = form.querySelector("[name=csrfmiddlewaretoken]");
      var body = new URLSearchParams(new FormData(form));
      fetch(form.action, {
        method: "POST",
        headers: {
          "X-CSRFToken": token ? token.value : "",
          "X-Requested-With": "XMLHttpRequest",
          "Accept": "application/json"
        },
        body: body,
        credentials: "same-origin"
      }).then(function (response) {
        var type = response.headers.get("content-type") || "";
        if (!response.ok || type.indexOf("application/json") === -1) {
          throw new Error("fallback");
        }
        return response.json();
      }).then(function (data) {
        button.textContent = "Helpful · " + data.count;
        button.classList.toggle("liked", !!data.liked);
        button.setAttribute("aria-pressed", data.liked ? "true" : "false");
      }).catch(function () {
        form.submit();
      });
    });
  });
})();

// Profile tabs — visual filter only
(function () {
  var tabs = document.querySelector("[data-tabs]");
  if (!tabs) return;
  var entries = document.querySelectorAll("[data-kind]");
  tabs.querySelectorAll("button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      tabs.querySelectorAll("button").forEach(function (b) {
        b.setAttribute("aria-selected", b === btn ? "true" : "false");
      });
      var f = btn.dataset.filter;
      entries.forEach(function (el) {
        el.style.display = (f === "all" || el.dataset.kind === f) ? "" : "none";
      });
    });
  });
})();
