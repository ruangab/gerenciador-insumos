/**
 * Sistema Web para Gerenciamento de Estoques — Parnamirim/RN
 * JavaScript Vanilla (ES6+ Assíncrono com Fetch API e Autenticação JWT)
 */

// Estado global da aplicação
const AppState = {
  token: localStorage.getItem("estoque_token") || null,
  usuario: JSON.parse(localStorage.getItem("estoque_usuario") || "null"),
  recursos: [],
  categorias: new Set(),
  filtroBuscaTimeout: null,
  recursoEmEdicaoId: null,
};

// =============================================================================
// INICIALIZAÇÃO E CONTROLE DE SESSÃO
// =============================================================================

document.addEventListener("DOMContentLoaded", () => {
  configurarNavegacaoAbas();
  // verificarSaudeSistema();
  atualizarInterfaceSessao();

  // Define data padrão de hoje para o input de movimentação
  const movDataInput = document.getElementById("mov-data");
  if (movDataInput) {
    const agora = new Date();
    agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset());
    movDataInput.value = agora.toISOString().slice(0, 16);
  }
});

function atualizarInterfaceSessao() {
  const authSection = document.getElementById("auth-section");
  const appSection = document.getElementById("app-main-section");
  const navTabs = document.getElementById("app-nav-tabs");
  const userWidget = document.getElementById("user-widget");
  const userNameEl = document.getElementById("user-display-name");

  if (AppState.token && AppState.usuario) {
    // Usuário autenticado: exibe o sistema
    authSection.style.display = "none";
    appSection.style.display = "block";
    navTabs.style.display = "flex";
    userWidget.style.display = "flex";
    userNameEl.textContent = AppState.usuario.nome || "Usuário";

    // Carrega os dados das abas para o usuário logado
    carregarDashboard();
    carregarRecursos();
    carregarMovimentacoes();
    carregarItensCriticos();
    gerarRelatorioBalanco();
  } else {
    // Usuário não autenticado: exibe login/cadastro
    authSection.style.display = "flex";
    appSection.style.display = "none";
    navTabs.style.display = "none";
    userWidget.style.display = "none";
  }
}

// Helper universal de fetch autenticado
async function apiFetch(url, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};

  if (AppState.token) {
    headers["Authorization"] = `Bearer ${AppState.token}`;
  }

  const response = await fetch(url, { ...options, headers });

  // Se receber 401 Unauthorized, expira a sessão e redireciona para login
  if (response.status === 401) {
    if (AppState.token) {
      mostrarToast("Sessão expirada. Faça login novamente.", "warning");
      fazerLogout();
    }
  }

  return response;
}

// =============================================================================
// AUTENTICAÇÃO (LOGIN, CADASTRO, LOGOUT)
// =============================================================================

function alternarFormAuth(modo) {
  const formLogin = document.getElementById("form-login");
  const formCadastro = document.getElementById("form-cadastro");
  const tabLogin = document.getElementById("tab-btn-login");
  const tabCadastro = document.getElementById("tab-btn-cadastro");

  if (modo === "cadastro") {
    formLogin.style.display = "none";
    formCadastro.style.display = "flex";
    tabLogin.classList.remove("active");
    tabCadastro.classList.add("active");
  } else {
    formLogin.style.display = "flex";
    formCadastro.style.display = "none";
    tabLogin.classList.add("active");
    tabCadastro.classList.remove("active");
  }
}

async function fazerLogin(event) {
  event.preventDefault();
  const btn = document.getElementById("btn-submit-login");
  btn.disabled = true;
  btn.textContent = "Entrando...";

  const email = document.getElementById("login-email").value.trim();
  const senha = document.getElementById("login-senha").value;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Falha ao realizar login.");
    }

    // Salva token e dados no storage
    salvarSessao(data);
    mostrarToast(`Bem-vindo(a), ${data.nome}!`, "success");
    atualizarInterfaceSessao();
  } catch (err) {
    mostrarToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Entrar no Sistema";
  }
}

async function fazerCadastro(event) {
  event.preventDefault();
  const btn = document.getElementById("btn-submit-cadastro");
  btn.disabled = true;
  btn.textContent = "Cadastrando...";

  const nome = document.getElementById("cadastro-nome").value.trim();
  const email = document.getElementById("cadastro-email").value.trim();
  const senha = document.getElementById("cadastro-senha").value;

  try {
    const res = await fetch("/api/auth/registrar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome, email, senha }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Falha ao criar conta.");
    }

    salvarSessao(data);
    mostrarToast(`Conta criada com sucesso! Bem-vindo(a), ${data.nome}!`, "success");
    atualizarInterfaceSessao();
  } catch (err) {
    mostrarToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Criar Conta e Acessar";
  }
}

function salvarSessao(authData) {
  AppState.token = authData.access_token;
  AppState.usuario = {
    id: authData.usuario_id,
    nome: authData.nome,
    email: authData.email,
  };
  localStorage.setItem("estoque_token", authData.access_token);
  localStorage.setItem("estoque_usuario", JSON.stringify(AppState.usuario));
}

function fazerLogout() {
  AppState.token = null;
  AppState.usuario = null;
  AppState.recursos = [];
  AppState.categorias.clear();
  localStorage.removeItem("estoque_token");
  localStorage.removeItem("estoque_usuario");
  atualizarInterfaceSessao();
  mostrarToast("Você saiu da sua conta.", "info");
}

// =============================================================================
// NAVEGAÇÃO ENTRE ABAS
// =============================================================================

function configurarNavegacaoAbas() {
  const tabButtons = document.querySelectorAll(".nav-tab");
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      mudarParaAba(targetId);
    });
  });
}

function mudarParaAba(tabId) {
  document.querySelectorAll(".nav-tab").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

  const targetBtn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
  const targetPane = document.getElementById(tabId);

  if (targetBtn && targetPane) {
    targetBtn.classList.add("active");
    targetPane.classList.add("active");

    // Recarrega dados específicos ao entrar na aba
    if (tabId === "tab-dashboard") carregarDashboard();
    if (tabId === "tab-recursos") carregarRecursos();
    if (tabId === "tab-movimentacoes") carregarMovimentacoes();
    if (tabId === "tab-relatorios") {
      carregarItensCriticos();
      gerarRelatorioBalanco();
    }
  }
}

async function verificarSaudeSistema() {
  const badge = document.getElementById("db-status-badge");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.database_connected) {
      badge.textContent = "● Conectado ao MongoDB";
      badge.className = "badge badge-success";
    } else {
      badge.textContent = "⚠️ MongoDB Offline";
      badge.className = "badge badge-warning";
      mostrarToast("Atenção: MongoDB não está acessível no momento.", "warning");
    }
  } catch {
    badge.textContent = "✕ Servidor Indisponível";
    badge.className = "badge badge-danger";
  }
}

// =============================================================================
// ABA 1: DASHBOARD
// =============================================================================

async function carregarDashboard() {
  if (!AppState.token) return;
  try {
    const res = await apiFetch("/api/relatorios/dashboard");
    if (!res.ok) throw new Error("Erro ao carregar dados do painel.");
    const data = await res.json();

    // Atualiza KPIs
    document.getElementById("kpi-total-recursos").textContent = data.total_recursos;
    document.getElementById("kpi-unidades-estoque").textContent = `${formatarNumero(data.total_unidades_estoque)} un. totais`;
    document.getElementById("kpi-estoque-baixo").textContent = data.itens_estoque_baixo;
    document.getElementById("kpi-validade-risco").textContent = data.itens_vencidos + data.itens_proximo_vencimento;
    document.getElementById("kpi-validade-detalhe").textContent = `${data.itens_vencidos} vencidos • ${data.itens_proximo_vencimento} em ≤ 30 dias`;
    document.getElementById("kpi-total-movimentacoes").textContent = `${data.total_movimentacoes} ops`;
    document.getElementById("kpi-fluxo-detalhe").textContent = `+${formatarNumero(data.total_entradas_30d)} ent. • -${formatarNumero(data.total_saidas_30d)} saídas (30d)`;

    // Renderiza lista de alertas urgentes no Dashboard
    renderizarAlertasDashboard();

    // Renderiza últimas movimentações no Dashboard
    renderizarUltimasMovimentacoesDashboard(data.ultimas_movimentacoes || []);
  } catch (err) {
    console.error(err);
  }
}

async function renderizarAlertasDashboard() {
  const container = document.getElementById("dashboard-alertas-lista");
  try {
    const res = await apiFetch("/api/relatorios/itens-criticos");
    if (!res.ok) return;
    const itensCriticos = await res.json();

    if (!itensCriticos || itensCriticos.length === 0) {
      container.innerHTML = `<p class="text-muted text-center py-4">🎉 Nenhum alerta crítico ativo. Seu estoque está regular!</p>`;
      return;
    }

    container.innerHTML = itensCriticos.slice(0, 5).map(item => {
      const isVencido = item.status_validade === "VENCIDO";
      const isBaixo = item.status_estoque !== "NORMAL";
      const isCritico = isVencido || item.status_estoque === "ZERADO";

      let textoAlerta = "";
      if (isVencido) {
        textoAlerta = `⚠️ VENCIDO há ${Math.abs(item.dias_para_vencer)} dias`;
      } else if (item.status_validade === "PROXIMO_VENCIMENTO") {
        textoAlerta = `⏳ Vence em ${item.dias_para_vencer} dias`;
      }

      if (isBaixo) {
        const sep = textoAlerta ? " • " : "";
        textoAlerta += `${sep}Estoque: ${item.quantidade_atual} ${item.unidade_medida} (Mín: ${item.estoque_minimo})`;
      }

      return `
        <div class="alerta-item ${isCritico ? 'critico' : ''}">
          <div>
            <strong>${escapeHTML(item.nome)}</strong>
            <div class="text-muted text-sm">${textoAlerta} • Lote: ${escapeHTML(item.lote)}</div>
          </div>
          <button class="btn btn-sm btn-outline" onclick="abrirModalMovimentacaoParaItem('${item.id}')">Movimentar</button>
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<p class="text-danger text-center py-4">Erro ao carregar alertas.</p>`;
  }
}

function renderizarUltimasMovimentacoesDashboard(movimentacoes) {
  const corpo = document.getElementById("dashboard-ultimas-movimentacoes");
  if (!movimentacoes || movimentacoes.length === 0) {
    corpo.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Nenhuma movimentação registrada no seu perfil.</td></tr>`;
    return;
  }

  corpo.innerHTML = movimentacoes.map(m => `
    <tr>
      <td>${formatarDataHora(m.data_movimentacao)}</td>
      <td>
        <span class="badge ${m.tipo === 'ENTRADA' ? 'badge-success' : 'badge-warning'}">
          ${m.tipo === 'ENTRADA' ? '📥 Entrada' : '📤 Saída'}
        </span>
      </td>
      <td><strong>${escapeHTML(m.recurso_nome || m.recurso_id)}</strong></td>
      <td>${formatarNumero(m.quantidade)}</td>
      <td>${escapeHTML(m.responsavel)}</td>
    </tr>
  `).join("");
}

// =============================================================================
// ABA 2: RECURSOS & ESTOQUE (CRUD)
// =============================================================================

async function carregarRecursos() {
  if (!AppState.token) return;
  const corpo = document.getElementById("tabela-recursos-corpo");
  const busca = document.getElementById("filtro-busca").value;
  const categoria = document.getElementById("filtro-categoria").value;
  const alertaEstoque = document.getElementById("filtro-alerta-estoque").value;
  const alertaValidade = document.getElementById("filtro-alerta-validade").value;

  const params = new URLSearchParams();
  if (busca) params.append("busca", busca);
  if (categoria) params.append("categoria", categoria);
  if (alertaEstoque) params.append("alerta_estoque", alertaEstoque);
  if (alertaValidade) params.append("alerta_validade", alertaValidade);

  try {
    const res = await apiFetch(`/api/recursos?${params.toString()}`);
    if (!res.ok) throw new Error("Erro ao buscar recursos.");
    const recursos = await res.json();
    AppState.recursos = recursos;

    // Atualiza opções do select de categorias
    atualizarCategoriasSelect(recursos);

    if (recursos.length === 0) {
      corpo.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">Nenhum recurso cadastrado no seu perfil ainda. Clique em "+ Cadastrar Recurso" para começar!</td></tr>`;
      return;
    }

    corpo.innerHTML = recursos.map(r => {
      const badgeEstoque = obterBadgeEstoque(r.status_estoque);
      const badgeValidade = obterBadgeValidade(r.status_validade, r.dias_para_vencer);

      return `
        <tr>
          <td>
            <strong>${escapeHTML(r.nome)}</strong>
            ${r.descricao ? `<div class="text-muted text-sm">${escapeHTML(r.descricao)}</div>` : ''}
          </td>
          <td><span class="badge badge-neutral">${escapeHTML(r.categoria)}</span></td>
          <td><strong>${formatarNumero(r.quantidade_atual)}</strong> ${r.unidade_medida}</td>
          <td>${formatarNumero(r.estoque_minimo)} ${r.unidade_medida}</td>
          <td>${badgeEstoque}</td>
          <td><code>${escapeHTML(r.lote)}</code></td>
          <td>${formatarData(r.data_validade)}</td>
          <td>${badgeValidade}</td>
          <td class="text-right actions-cell">
            <button class="btn btn-sm btn-outline" title="Registrar Fluxo" onclick="abrirModalMovimentacaoParaItem('${r.id}')">🔄</button>
            <button class="btn btn-sm btn-outline" title="Editar Recurso" onclick="editarRecurso('${r.id}')">✏️</button>
            <button class="btn btn-sm btn-danger" title="Excluir" onclick="excluirRecurso('${r.id}', '${escapeHTML(r.nome)}')">🗑️</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    corpo.innerHTML = `<tr><td colspan="9" class="text-danger text-center py-4">Erro ao carregar recursos da API.</td></tr>`;
  }
}

function filtrarRecursosDebounce() {
  clearTimeout(AppState.filtroBuscaTimeout);
  AppState.filtroBuscaTimeout = setTimeout(carregarRecursos, 300);
}

function limparFiltrosRecursos() {
  document.getElementById("filtro-busca").value = "";
  document.getElementById("filtro-categoria").value = "";
  document.getElementById("filtro-alerta-estoque").value = "";
  document.getElementById("filtro-alerta-validade").value = "";
  carregarRecursos();
}

function atualizarCategoriasSelect(recursos) {
  const select = document.getElementById("filtro-categoria");
  recursos.forEach(r => {
    if (r.categoria) AppState.categorias.add(r.categoria);
  });

  const categoriaAtual = select.value;
  select.innerHTML = '<option value="">Todas as Categorias</option>';
  Array.from(AppState.categorias).sort().forEach(cat => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    if (cat === categoriaAtual) opt.selected = true;
    select.appendChild(opt);
  });
}

function obterBadgeEstoque(status) {
  if (status === "ZERADO") return `<span class="badge badge-danger">Zerado</span>`;
  if (status === "BAIXO") return `<span class="badge badge-warning">Estoque Baixo</span>`;
  return `<span class="badge badge-success">Regular</span>`;
}

function obterBadgeValidade(status, dias) {
  if (status === "VENCIDO") {
    return `<span class="badge badge-danger">Vencido (${Math.abs(dias)}d atrás)</span>`;
  }
  if (status === "PROXIMO_VENCIMENTO") {
    return `<span class="badge badge-warning">Vence em ${dias}d</span>`;
  }
  return `<span class="badge badge-success">No Prazo (${dias}d)</span>`;
}

// -----------------------------------------------------------------------------
// Modal: Criar / Editar Recurso
// -----------------------------------------------------------------------------

function abrirModalRecurso() {
  AppState.recursoEmEdicaoId = null;
  document.getElementById("modal-recurso-titulo").textContent = "Cadastrar Novo Recurso";
  document.getElementById("form-recurso").reset();
  document.getElementById("recurso-id").value = "";
  document.getElementById("recurso-lote").value = "PADRAO";
  document.getElementById("recurso-quantidade").disabled = false;

  // Define validade padrão de 6 meses à frente
  const dataFutura = new Date();
  dataFutura.setMonth(dataFutura.getMonth() + 6);
  document.getElementById("recurso-validade").value = dataFutura.toISOString().split("T")[0];

  const modal = document.getElementById("modal-recurso");
  modal.showModal();
}

async function editarRecurso(id) {
  try {
    const res = await apiFetch(`/api/recursos/${id}`);
    if (!res.ok) throw new Error("Recurso não encontrado.");
    const r = await res.json();

    AppState.recursoEmEdicaoId = r.id;
    document.getElementById("modal-recurso-titulo").textContent = "Editar Recurso";
    document.getElementById("recurso-id").value = r.id;
    document.getElementById("recurso-nome").value = r.nome;
    document.getElementById("recurso-categoria").value = r.categoria;
    document.getElementById("recurso-unidade").value = r.unidade_medida;
    document.getElementById("recurso-quantidade").value = r.quantidade_atual;
    document.getElementById("recurso-quantidade").disabled = true; // Saldo via movimentação
    document.getElementById("recurso-minimo").value = r.estoque_minimo;
    document.getElementById("recurso-lote").value = r.lote;
    document.getElementById("recurso-validade").value = r.data_validade.slice(0, 10);
    document.getElementById("recurso-descricao").value = r.descricao || "";

    const modal = document.getElementById("modal-recurso");
    modal.showModal();
  } catch (err) {
    mostrarToast(err.message, "error");
  }
}

function fecharModalRecurso() {
  document.getElementById("modal-recurso").close();
}

async function salvarRecurso(event) {
  event.preventDefault();
  const btnSalvar = document.getElementById("btn-salvar-recurso");
  btnSalvar.disabled = true;
  btnSalvar.textContent = "Salvando...";

  const id = document.getElementById("recurso-id").value;
  const payload = {
    nome: document.getElementById("recurso-nome").value.trim(),
    categoria: document.getElementById("recurso-categoria").value.trim(),
    unidade_medida: document.getElementById("recurso-unidade").value,
    estoque_minimo: parseFloat(document.getElementById("recurso-minimo").value),
    lote: document.getElementById("recurso-lote").value.trim(),
    data_validade: new Date(document.getElementById("recurso-validade").value + "T00:00:00Z").toISOString(),
    descricao: document.getElementById("recurso-descricao").value.trim()
  };

  if (!id) {
    payload.quantidade_atual = parseFloat(document.getElementById("recurso-quantidade").value);
  }

  try {
    const url = id ? `/api/recursos/${id}` : "/api/recursos";
    const method = id ? "PUT" : "POST";

    const res = await apiFetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Falha ao salvar recurso.");
    }

    fecharModalRecurso();
    mostrarToast(id ? "Recurso atualizado com sucesso!" : "Novo recurso cadastrado com sucesso!", "success");
    carregarRecursos();
    carregarDashboard();
  } catch (err) {
    mostrarToast(err.message, "error");
  } finally {
    btnSalvar.disabled = false;
    btnSalvar.textContent = "Salvar Recurso";
  }
}

async function excluirRecurso(id, nome) {
  if (!confirm(`Deseja realmente excluir o recurso "${nome}"?\nEsta ação não poderá ser desfeita.`)) {
    return;
  }

  try {
    const res = await apiFetch(`/api/recursos/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Erro ao excluir recurso.");
    mostrarToast(`Recurso "${nome}" removido com sucesso!`, "success");
    carregarRecursos();
    carregarDashboard();
  } catch (err) {
    mostrarToast(err.message, "error");
  }
}

// =============================================================================
// ABA 3: MOVIMENTAÇÕES & FLUXO
// =============================================================================

async function carregarMovimentacoes() {
  if (!AppState.token) return;
  const corpo = document.getElementById("tabela-movimentacoes-corpo");
  const tipo = document.getElementById("filtro-mov-tipo").value;
  const dataInicio = document.getElementById("filtro-mov-data-inicio").value;
  const dataFim = document.getElementById("filtro-mov-data-fim").value;

  const params = new URLSearchParams();
  if (tipo) params.append("tipo", tipo);
  if (dataInicio) params.append("data_inicio", new Date(dataInicio + "T00:00:00Z").toISOString());
  if (dataFim) params.append("data_fim", new Date(dataFim + "T23:59:59Z").toISOString());

  try {
    const res = await apiFetch(`/api/movimentacoes?${params.toString()}`);
    if (!res.ok) throw new Error("Erro ao buscar movimentações.");
    const movimentacoes = await res.json();

    if (movimentacoes.length === 0) {
      corpo.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">Nenhuma movimentação registrada para os filtros selecionados.</td></tr>`;
      return;
    }

    corpo.innerHTML = movimentacoes.map(m => {
      const isEntrada = m.tipo === "ENTRADA";
      const tipoBadge = isEntrada
        ? `<span class="badge badge-success">📥 Entrada</span>`
        : `<span class="badge badge-warning">📤 Saída</span>`;

      const saldoAnterior = m.saldo_anterior !== null ? formatarNumero(m.saldo_anterior) : "-";
      const saldoPosterior = m.saldo_posterior !== null ? formatarNumero(m.saldo_posterior) : "-";

      return `
        <tr>
          <td>${formatarDataHora(m.data_movimentacao)}</td>
          <td>${tipoBadge}</td>
          <td><strong>${escapeHTML(m.recurso_nome || m.recurso_id)}</strong></td>
          <td><strong class="${isEntrada ? 'text-success' : 'text-danger'}">${isEntrada ? '+' : '-'}${formatarNumero(m.quantidade)}</strong></td>
          <td><code>${saldoAnterior} ➔ ${saldoPosterior}</code></td>
          <td>${escapeHTML(m.origem_destino)}</td>
          <td>${escapeHTML(m.motivo)}</td>
          <td>${escapeHTML(m.responsavel)}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    corpo.innerHTML = `<tr><td colspan="8" class="text-danger text-center py-4">Erro ao carregar movimentações.</td></tr>`;
  }
}

function limparFiltrosMovimentacoes() {
  document.getElementById("filtro-mov-tipo").value = "";
  document.getElementById("filtro-mov-data-inicio").value = "";
  document.getElementById("filtro-mov-data-fim").value = "";
  carregarMovimentacoes();
}

// -----------------------------------------------------------------------------
// Modal: Registrar Movimentação
// -----------------------------------------------------------------------------

async function abrirModalMovimentacao() {
  document.getElementById("form-movimentacao").reset();
  ajustarCamposTipoMovimentacao();

  // Sugere o nome do usuário logado no campo de responsável
  if (AppState.usuario) {
    document.getElementById("mov-responsavel").value = AppState.usuario.nome;
  }

  // Preenche select de recursos disponíveis
  await preencherSelectRecursosMovimentacao();

  const modal = document.getElementById("modal-movimentacao");
  modal.showModal();
}

async function abrirModalMovimentacaoParaItem(recursoId) {
  await abrirModalMovimentacao();
  const select = document.getElementById("mov-recurso-id");
  select.value = recursoId;
  aoSelecionarRecursoMovimentacao();
}

async function preencherSelectRecursosMovimentacao() {
  const select = document.getElementById("mov-recurso-id");
  select.innerHTML = '<option value="">Carregando recursos...</option>';

  try {
    const res = await apiFetch("/api/recursos?limit=500");
    if (!res.ok) throw new Error();
    const recursos = await res.json();
    AppState.recursos = recursos;

    select.innerHTML = '<option value="">Selecione um recurso...</option>';
    recursos.forEach(r => {
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = `${r.nome} (Disponível: ${formatarNumero(r.quantidade_atual)} ${r.unidade_medida})`;
      opt.dataset.saldo = r.quantidade_atual;
      opt.dataset.unidade = r.unidade_medida;
      opt.dataset.nome = r.nome;
      select.appendChild(opt);
    });
  } catch (err) {
    select.innerHTML = '<option value="">Erro ao carregar itens</option>';
  }
}

function aoSelecionarRecursoMovimentacao() {
  const select = document.getElementById("mov-recurso-id");
  const info = document.getElementById("mov-saldo-info");
  const opt = select.options[select.selectedIndex];

  if (opt && opt.value) {
    const saldo = opt.dataset.saldo;
    const unidade = opt.dataset.unidade;
    info.innerHTML = `Saldo atual disponível: <strong>${formatarNumero(saldo)} ${unidade}</strong>.`;
  } else {
    info.textContent = "Selecione o recurso para consultar o saldo disponível.";
  }
}

function ajustarCamposTipoMovimentacao() {
  const tipo = document.getElementById("mov-tipo").value;
  const label = document.getElementById("label-origem-destino");
  const input = document.getElementById("mov-origem-destino");

  if (tipo === "ENTRADA") {
    label.textContent = "Origem (Doador / Fornecedor) *";
    input.placeholder = "Ex: Campanha Comunitária Natal Sem Fome / Supermercado X";
  } else {
    label.textContent = "Destino (Comunidade / Destinatário / Motivo Descarte) *";
    input.placeholder = "Ex: Bairro Passagem de Areia / Entrega Cesta Familiar";
  }
}

function fecharModalMovimentacao() {
  document.getElementById("modal-movimentacao").close();
}

async function salvarMovimentacao(event) {
  event.preventDefault();
  const btn = document.getElementById("btn-salvar-movimentacao");
  btn.disabled = true;
  btn.textContent = "Gravando...";

  const recursoId = document.getElementById("mov-recurso-id").value;
  const tipo = document.getElementById("mov-tipo").value;
  const quantidade = parseFloat(document.getElementById("mov-quantidade").value);
  const origemDestino = document.getElementById("mov-origem-destino").value.trim();
  const motivo = document.getElementById("mov-motivo").value.trim();
  const responsavel = document.getElementById("mov-responsavel").value.trim();
  const dataInput = document.getElementById("mov-data").value;

  const payload = {
    recurso_id: recursoId,
    tipo: tipo,
    quantidade: quantidade,
    origem_destino: origemDestino,
    motivo: motivo,
    responsavel: responsavel,
    data_movimentacao: dataInput ? new Date(dataInput).toISOString() : null
  };

  try {
    const res = await apiFetch("/api/movimentacoes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Falha ao registrar movimentação.");
    }

    fecharModalMovimentacao();
    mostrarToast("Movimentação de estoque registrada com sucesso!", "success");
    carregarMovimentacoes();
    carregarRecursos();
    carregarDashboard();
    carregarItensCriticos();
    gerarRelatorioBalanco();
  } catch (err) {
    mostrarToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Confirmar Movimentação";
  }
}

// =============================================================================
// ABA 4: RELATÓRIOS & PRESTAÇÃO DE CONTAS
// =============================================================================

async function carregarItensCriticos() {
  if (!AppState.token) return;
  const corpo = document.getElementById("tabela-itens-criticos-corpo");
  try {
    const res = await apiFetch("/api/relatorios/itens-criticos");
    if (!res.ok) throw new Error("Erro ao carregar itens críticos.");
    const itens = await res.json();

    if (itens.length === 0) {
      corpo.innerHTML = `<tr><td colspan="8" class="text-center text-success py-4">🎉 Nenhum item crítico! Todo o estoque está acima do mínimo e dentro da validade.</td></tr>`;
      return;
    }

    corpo.innerHTML = itens.map(r => `
      <tr>
        <td><strong>${escapeHTML(r.nome)}</strong></td>
        <td><span class="badge badge-neutral">${escapeHTML(r.categoria)}</span></td>
        <td><strong>${formatarNumero(r.quantidade_atual)}</strong> ${r.unidade_medida}</td>
        <td>${formatarNumero(r.estoque_minimo)} ${r.unidade_medida}</td>
        <td>${obterBadgeEstoque(r.status_estoque)}</td>
        <td>${formatarData(r.data_validade)}</td>
        <td>${r.dias_para_vencer < 0 ? `Vencido há ${Math.abs(r.dias_para_vencer)}d` : `${r.dias_para_vencer} dias`}</td>
        <td>${obterBadgeValidade(r.status_validade, r.dias_para_vencer)}</td>
      </tr>
    `).join("");
  } catch (err) {
    corpo.innerHTML = `<tr><td colspan="8" class="text-danger text-center py-4">Erro ao carregar inventário crítico.</td></tr>`;
  }
}

async function gerarRelatorioBalanco() {
  if (!AppState.token) return;
  const dataInicio = document.getElementById("relatorio-data-inicio").value;
  const dataFim = document.getElementById("relatorio-data-fim").value;

  const params = new URLSearchParams();
  if (dataInicio) params.append("data_inicio", new Date(dataInicio + "T00:00:00Z").toISOString());
  if (dataFim) params.append("data_fim", new Date(dataFim + "T23:59:59Z").toISOString());

  try {
    const res = await apiFetch(`/api/relatorios/balanco?${params.toString()}`);
    if (!res.ok) throw new Error("Erro ao buscar balanço.");
    const data = await res.json();

    document.getElementById("rel-total-entradas").textContent = `+${formatarNumero(data.entradas.quantidade)}`;
    document.getElementById("rel-ops-entradas").textContent = `${data.entradas.registros} operações de entrada`;

    document.getElementById("rel-total-saidas").textContent = `-${formatarNumero(data.saidas.quantidade)}`;
    document.getElementById("rel-ops-saidas").textContent = `${data.saidas.registros} operações de saída`;

    const saldoEl = document.getElementById("rel-saldo-liquido");
    saldoEl.textContent = formatarNumero(data.saldo_liquido);
    saldoEl.className = data.saldo_liquido >= 0 ? "kpi-value text-success" : "kpi-value text-danger";
    document.getElementById("rel-total-ops").textContent = `${data.total_operacoes} operações registradas no período`;
  } catch (err) {
    mostrarToast("Erro ao calcular balanço operacional.", "error");
  }
}

function definirPeriodoRapido(dias) {
  const hoje = new Date();
  const inicio = new Date();
  inicio.setDate(hoje.getDate() - dias);

  document.getElementById("relatorio-data-inicio").value = inicio.toISOString().split("T")[0];
  document.getElementById("relatorio-data-fim").value = hoje.toISOString().split("T")[0];
  gerarRelatorioBalanco();
}

function limparPeriodoRelatorio() {
  document.getElementById("relatorio-data-inicio").value = "";
  document.getElementById("relatorio-data-fim").value = "";
  gerarRelatorioBalanco();
}

// =============================================================================
// EXPORTAÇÃO CSV (AUTENTICADA VIA BLOB)
// =============================================================================

async function exportarRecursosCSV() {
  try {
    mostrarToast("Gerando arquivo CSV do estoque...", "info");
    const res = await apiFetch("/api/relatorios/exportar/recursos-csv");
    if (!res.ok) throw new Error("Erro ao exportar CSV de recursos.");
    
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `relatorio_estoque_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    mostrarToast("Download concluído com sucesso!", "success");
  } catch (err) {
    mostrarToast(err.message, "error");
  }
}

async function exportarMovimentacoesCSV() {
  const dataInicio = document.getElementById("filtro-mov-data-inicio").value;
  const dataFim = document.getElementById("filtro-mov-data-fim").value;

  const params = new URLSearchParams();
  if (dataInicio) params.append("data_inicio", new Date(dataInicio + "T00:00:00Z").toISOString());
  if (dataFim) params.append("data_fim", new Date(dataFim + "T23:59:59Z").toISOString());

  try {
    mostrarToast("Gerando extrato CSV de movimentações...", "info");
    const res = await apiFetch(`/api/relatorios/exportar/movimentacoes-csv?${params.toString()}`);
    if (!res.ok) throw new Error("Erro ao exportar CSV de movimentações.");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `historico_movimentacoes_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    mostrarToast("Download concluído com sucesso!", "success");
  } catch (err) {
    mostrarToast(err.message, "error");
  }
}

// =============================================================================
// UTILITÁRIOS E TOASTS
// =============================================================================

function mostrarToast(mensagem, tipo = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;

  let icone = "ℹ️";
  if (tipo === "success") icone = "✅";
  if (tipo === "error") icone = "❌";
  if (tipo === "warning") icone = "⚠️";

  toast.innerHTML = `
    <div><strong>${icone}</strong> ${escapeHTML(mensagem)}</div>
    <button type="button" class="btn-close" style="font-size: 1rem;" onclick="this.parentElement.remove()">✕</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

function formatarNumero(valor) {
  if (valor === undefined || valor === null || isNaN(valor)) return "0";
  return Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function formatarData(dataStr) {
  if (!dataStr) return "-";
  const d = new Date(dataStr);
  return d.toLocaleDateString("pt-BR");
}

function formatarDataHora(dataStr) {
  if (!dataStr) return "-";
  const d = new Date(dataStr);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function escapeHTML(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
