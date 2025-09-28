
function verificarGenero() {
  const genero = document.getElementById("genero").value;
  const campoPersonalizado = document.getElementById("personalizadoInput");

  if (genero === "Outro") {
    campoPersonalizado.style.display = "block";
  } else {
    campoPersonalizado.style.display = "none";
  }
}
document.addEventListener('DOMContentLoaded', function () {
  verificarGenero();
  const v = document.getElementById('genero');
  selectGenero.addEventListener('change', verificarGenero);
});



//const navButtons = document.querySelectorAll('.nav-button');
//const pages = document.querySelectorAll('.page');

/*navButtons.forEach(button => {
  button.addEventListener('click', () => {
    // Atualizar botão ativo
    navButtons.forEach(btn => btn.classList.remove('active'));
    button.classList.add('active');

    // Mostrar div da página atual
    const pageId = button.getAttribute('data-page');
    pages.forEach(page => {
      page.classList.remove('active');
      if (page.id === pageId) {
        page.classList.add('active');
      }
    });
  });
});*/
