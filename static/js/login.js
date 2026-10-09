document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('form');
  const btn = document.querySelector('button');

  form.addEventListener('submit', () => {
    btn.textContent = 'Carregando...';
    btn.style.opacity = '0.7';
  });
});