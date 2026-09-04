# MCP Server de Dados Financeiros

Um servidor [MCP](https://modelcontextprotocol.io) que expõe ferramentas para consultar cotações e calcular métricas de risco/retorno de carteiras (retorno acumulado, volatilidade anualizada, Sharpe, máximo drawdown). Plugável direto no Claude Desktop, Claude Code ou qualquer outro cliente MCP.

## Arquitetura

Um servidor MCP é só um processo Python que fala o protocolo MCP (via stdio ou HTTP) e expõe um punhado de *tools* — funções com schema de input bem definido — que qualquer cliente MCP pode chamar. O servidor não tem interface própria; o cliente (Claude, por exemplo) decide quando invocar cada tool com base na docstring e no schema.

```
src/mcp_financial/
├── server.py           # entrypoint MCP: registra as tools (FastMCP)
├── models.py            # validação de input com Pydantic
├── data.py               # wrapper do yfinance: cache + tratamento de erro
├── metrics.py           # cálculos financeiros puros (testáveis sem rede)
├── cache.py               # cache TTL em memória (evita rate limit do yfinance)
├── logging_config.py    # logging estruturado (JSON) em stderr
└── errors.py             # exceções de domínio
```

Separação deliberada: `metrics.py` não importa `yfinance` nem faz I/O — é só matemática sobre `pandas.Series`/`DataFrame`, o que permite testar Sharpe e drawdown com valores calculados à mão, sem depender da rede ou de mocks frágeis. `data.py` isola tudo que pode falhar (ticker inválido, provedor fora do ar, rate limit) atrás de exceções próprias (`TickerNotFoundError`, `DataProviderError`), para que `server.py` só precise de um `try/except` genérico por tool.

## Ferramentas

| Tool | Descrição |
|---|---|
| `get_quote(ticker)` | Preço atual, fechamento anterior e variação do dia. |
| `get_portfolio_metrics(tickers, weights, period, risk_free_rate)` | Retorno acumulado, retorno anualizado, volatilidade anualizada, Sharpe e máximo drawdown de uma carteira ponderada. |
| `compare_assets(tickers, period)` | Matriz de correlação dos retornos diários entre dois ou mais ativos. |
| `get_historical_summary(ticker, period)` | Médias móveis (20/50), máxima/mínima do período e retorno acumulado. |

Todas retornam um dict `{"error": "invalid_input" | "data_unavailable" | "internal_error", "details": ...}` em vez de lançar exceção, para que o modelo cliente consiga reagir ao erro em vez de a chamada travar.

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Testar as ferramentas via [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector mcp-financial-data-server
```

Ou rodar o servidor puro (fala stdio, então não produz output "normal" no terminal):

```bash
mcp-financial-data-server
```

## Configurando no Claude Desktop

Adicione ao `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "financial-data": {
      "command": "mcp-financial-data-server"
    }
  }
}
```

Ou apontando para o Python do virtualenv, se preferir não instalar globalmente:

```json
{
  "mcpServers": {
    "financial-data": {
      "command": "/caminho/para/.venv/bin/mcp-financial-data-server"
    }
  }
}
```

## Docker

```bash
docker build -t mcp-financial-data-server .
```

Como o protocolo MCP fala stdio, o cliente precisa invocar o container com `-i`:

```json
{
  "mcpServers": {
    "financial-data": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "mcp-financial-data-server"]
    }
  }
}
```

## Testes

```bash
pytest --cov=mcp_financial --cov-report=term-missing
```

Os testes de `metrics.py` usam valores calculados à mão (não a mesma fórmula do código sob teste) para os cálculos financeiros — ver comentários em [tests/test_metrics.py](tests/test_metrics.py).

## Boas práticas aplicadas

- **Validação de input**: todo tool valida com um modelo Pydantic antes de tocar em dado externo (ticker normalizado, período restrito a um enum, pesos de carteira validados para somar 1.0).
- **Tratamento de erro**: ticker inválido e provedor fora do ar viram exceções de domínio (`errors.py`), nunca uma exceção crua do yfinance vazando pro cliente MCP.
- **Cache**: TTL curto (15s para cotação, 5min para histórico) evita bater o rate limit do yfinance em chamadas repetidas na mesma sessão.
- **Logging estruturado**: JSON em stderr (stdout é reservado pro protocolo MCP).
- **CI**: GitHub Actions roda lint (`ruff`) e `pytest` a cada push/PR em duas versões de Python.

## Limitações conhecidas

- yfinance depende de endpoints não-oficiais do Yahoo Finance; instabilidade upstream é esperada e tratada como `DataProviderError`, não como bug do servidor.
- Métricas de carteira assumem rebalanceamento diário implícito (pesos fixos aplicados ao retorno diário de cada ativo), não um buy-and-hold com deriva de pesos.
