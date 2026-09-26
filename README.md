# 📦 Sistema Web para Gerenciamento de Estoques em Pequenos Negócios e Organizações Sociais

> **Localização:** Parnamirim/RN (Atuação de nível local a regional)  
> **Impacto Social:** Alinhado aos Objetivos de Desenvolvimento Sustentável da ONU — **ODS 9** (Indústria, Inovação e Infraestrutura) e **ODS 12** (Consumo e Produção Responsáveis).

---

## 📌 Apresentação e Propósito

Este sistema foi concebido para resolver um gargalo crítico em pequenos mercados de bairro, farmácias comunitárias e ONGs de distribuição de alimentos em Parnamirim/RN: a ausência de ferramentas simples, acessíveis e sem custo de licenciamento para controle centralizado de estoques.

O controle rigoroso de lotes e datas de validade previne perdas de alimentos e medicamentos perecíveis, enquanto o registro auditável de fluxo garante total transparência para a prestação de contas de doações comunitárias.

---

## 🛠️ Stack Tecnológica

- **Back-end:** Python 3.10+ com **FastAPI** (rotas assíncronas e documentação Swagger automática).
- **Banco de Dados:** **MongoDB** (NoSQL) com driver assíncrono **Motor** e índices de consulta.
- **Validação e Tipagem:** **Pydantic v2** e `pydantic-settings`.
- **Front-end:** **HTML5 semântico, CSS3 responsivo e JavaScript Vanilla** (ES6+ com `fetch API`).  
  *100% livre de frameworks pesados (sem React/Vue) e sem dependências de build (`npm`/`webpack`), funcionando instantaneamente em computadores e celulares antigos.*
- **Servidor ASGI:** **Uvicorn**.

---

## 🎯 Requisitos Funcionais Atendidos

1. **RF01 - Gerenciamento de Recursos (CRUD):**
   - Cadastro, listagem, busca textual (nome, lote, descrição), filtros por categoria e status de alerta.
   - Atributos: Nome, Descrição, Categoria, Unidade de Medida (`UN`, `KG`, `LITRO`, `CAIXA`, `PACOTE`), Quantidade Atual, Estoque Mínimo, Lote e Data de Validade.
   - Tratamento nativo de `ObjectId` mapeado para `id`.

2. **RF02 - Registro de Fluxo e Movimentações Auditáveis:**
   - Registro de **Entradas** (compras, doações recebidas) com soma atômica ao estoque.
   - Registro de **Saídas** (distribuição, vendas, perdas) com subtração atômica.
   - **Validação Preventiva de Saldo Negativo:** impede saídas com quantidade maior que o saldo disponível (`HTTP 400`).
   - Auditoria completa: responsável, motivo, origem/destino, data/hora e histórico de saldo anterior e posterior.

3. **RF03 - Sistema de Alertas Automáticos:**
   - Alerta visual no painel para `quantidade_atual <= estoque_minimo` (Estoque Baixo ou Zerado).
   - Alerta de validade:
     - 🔴 **Vencido:** `data_validade < hoje`.
     - 🟡 **Próximo do Vencimento:** vence em até 30 dias.
     - 🟢 **No Prazo:** mais de 30 dias de validade.

4. **RF04 - Relatórios Digitais & Prestação de Contas:**
   - Balanço consolidado de entradas e saídas em intervalos de datas configuráveis.
   - Painel e relatório de **Itens Críticos** para planejamento de compras e distribuição prioritária.
   - Exportação direta para **CSV** formatado (compatível com Excel) e folha de estilo para impressão direta do navegador (`window.print()` / PDF via `@media print`).

5. **RF05 - Interface Responsiva e Acessível:**
   - Design Mobile-First com CSS Grid e Flexbox.
   - Modais nativos acessíveis com a tag HTML5 `<dialog>`.
   - Sistema de notificações temporárias (*toasts*) para confirmação visual de ações.

---

## 🏗️ Estrutura do Projeto

```text
projeto-estoque/
├── app/
│   ├── __init__.py
│   ├── main.py              # Aplicação FastAPI, CORS, rotas e arquivos estáticos
│   ├── config.py            # Configurações com Pydantic Settings e .env
│   ├── database.py          # Conexão assíncrona Motor com MongoDB e índices
│   ├── models/              # Schemas Pydantic v2
│   │   ├── __init__.py
│   │   ├── recurso.py       # Modelo de Recurso com campos computados de alerta
│   │   └── movimentacao.py  # Modelo de Movimentação e auditoria
│   ├── routers/             # Controllers REST
│   │   ├── __init__.py
│   │   ├── recursos.py      # Endpoints CRUD de recursos
│   │   ├── movimentacoes.py # Endpoints de fluxo de entradas/saídas
│   │   └── relatorios.py    # Endpoints de KPIs, itens críticos e CSV
│   └── services/            # Camada de regras de negócio
│       ├── __init__.py
│       └── estoque_service.py
├── static/                  # Interface Web Vanilla (Zero Build)
│   ├── css/
│   │   └── style.css        # Estilos responsivos e acessíveis
│   ├── js/
│   │   └── main.js          # Lógica do front-end e consumo da API REST
│   └── index.html           # Interface do usuário em página única
├── tests/
│   ├── __init__.py
│   └── test_api.py          # Suíte completa de testes automatizados
├── .env.example
├── .env
├── .gitignore
├── requirements.txt
├── README.md

```

---

## ⚡ Como Executar o Projeto

### 1. Pré-requisitos
- Python 3.10+ instalado.
- MongoDB rodando localmente na porta padrão `27017` (ou via Docker).

### 2. Instalação das Dependências

No terminal:
```bash
# Navegar até a pasta do projeto
cd projeto-estoque

# Criar e ativar o ambiente virtual (opcional, recomendado)
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
.\venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate

# Instalar pacotes Python
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente
O arquivo `.env` já vem pré-configurado para ambiente local:
```env
MONGODB_URL=mongodb://127.0.0.1:27017
DATABASE_NAME=gestao_estoque
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
ALERTA_DIAS_VALIDADE=30
```

### 4. Iniciar o Servidor de Desenvolvimento
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interface Web:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Documentação Swagger:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Documentação ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🧪 Execução dos Testes Automatizados

A suíte de testes valida todos os requisitos essenciais da aplicação:
```bash
pytest -v
```

Cenários cobertos:
- Verificação de saúde da API e ping do MongoDB (`test_health_check`).
- Ciclo de vida de Recursos: criação, busca, atualização e remoção (`test_rf01_crud_recurso`).
- Movimentações de Entrada e Saída auditáveis (`test_rf02_fluxo_movimentacoes_e_validacao_saldo_negativo`).
- Rejeição preventiva de saída quando a quantidade solicitada for maior que o saldo em estoque (`HTTP 400`).
- Alertas de Estoque Baixo, Zerado, Vencendo em breve e Vencido (`test_rf03_alertas_automaticos`).
- Relatório de Itens Críticos, Balanço Operacional e Exportação de CSV (`test_rf04_relatorios_e_exportacao_csv`).

---

## 📄 Licença e Uso
Desenvolvido para apoio comunitário e pequenos negócios em Parnamirim/RN. Software livre para adaptação, implantação e distribuição pública.
