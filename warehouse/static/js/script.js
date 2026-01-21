document.addEventListener("DOMContentLoaded", function () {
  const navbar = document.querySelector(".navbar");
  let scrollPosition = 0;

  // Funkce pro skrytí navigace, když uživatel sjede dolů
  function hideNavbarAfterDelay() {
    setTimeout(() => {
      if (window.scrollY > 550) {
        // Podmínka pro srolování - např. po 100 pixelech
        navbar.classList.add("hidden");
      }
    }, 500);
  }

  // Sleduje scroll a po srolování dolů spustí funkci pro skrytí panelu
  window.addEventListener("scroll", () => {
    if (window.scrollY > 550) {
      // Panel se skryje jen po srolování o více než 100px
      hideNavbarAfterDelay();
    } else {
      navbar.classList.remove("hidden"); // Když se uživatel vrátí nahoru, panel je viditelný
    }
  });

  // Zobrazení navigace při pohybu myší do horní části obrazovky
  document.addEventListener("mousemove", (event) => {
    if (event.clientY < 200) {
      // Pokud myš je v horních 50px
      navbar.classList.remove("hidden");
    } else if (window.scrollY > 550) {
      navbar.classList.add("hidden");
    }
  });
});
