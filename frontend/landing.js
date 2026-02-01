/* Landing page interactivity */

// ── Expandable sections ──
document.querySelectorAll(".expandable-trigger").forEach((btn) => {
  btn.addEventListener("click", () => {
    const content = btn.nextElementSibling;
    const isOpen = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", !isOpen);
    if (isOpen) {
      content.classList.remove("open");
    } else {
      content.classList.add("open");
    }
  });
});

// ── Sticky nav: show after scrolling past hero ──
const nav = document.getElementById("landingNav");
const hero = document.getElementById("hero");

if (nav && hero) {
  const observer = new IntersectionObserver(
    ([entry]) => {
      nav.classList.toggle("nav-visible", !entry.isIntersecting);
    },
    { threshold: 0.1 }
  );
  observer.observe(hero);
}

// ── Smooth scroll for anchor links ──
document.querySelectorAll('.nav-links a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    const target = document.querySelector(link.getAttribute("href"));
    if (target) {
      target.scrollIntoView({ behavior: "smooth" });
    }
  });
});
