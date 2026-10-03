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
