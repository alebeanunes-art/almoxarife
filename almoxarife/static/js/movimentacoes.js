document.querySelector('form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const dados = {
    tipo: document.getElementById('tipo').value,
    produto_id: document.getElementById('produto').value, // Pega do input id="produto"
    quantidade: document.getElementById('quantidade').value,
    usuario_id: 1 // ID do utilizador logado
  };

  const resposta = await fetch('/api/movimentacoes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(dados)
  });

  const resultado = await resposta.json();

  if (resposta.ok) {
    alert(resultado.mensagem);
    window.location.reload();
  } else {
    alert(resultado.erro || 'Erro ao registrar movimentação.');
  }
});