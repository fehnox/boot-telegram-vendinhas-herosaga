# boot-telegram-vendinhas-herosaga

Bot Telegram simples para gerenciar "vendinhas" do jogo Herosaga.

Requisitos
- Python 3.10+
- `git` e opcionalmente o CLI `gh` (para criar o repositório remoto)

Instalação rápida

```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
.venv\Scripts\activate     # Windows (PowerShell)
pip install -r requirements.txt
cp .env.example .env
# edite .env para adicionar seu BOT_TOKEN
python -m src.bot.main
```

Publicar no GitHub (opcional, com `gh` instalado e autenticado)

```bash
cd boot-telegram-vendinhas-herosaga
git init
git add -A
git commit -m "Initial commit"
gh repo create boot-telegram-vendinhas-herosaga --public --source=. --remote=origin --push
```

Se preferir criar o repositório pelo site do GitHub, crie-o manualmente e depois rode:

```bash
git remote add origin <URL_DO_REPO>
git push -u origin main
```

Estrutura inicial
- `src/bot/main.py` — ponto de entrada do bot
- `.env.example` — variáveis de ambiente
- `requirements.txt` — dependências

Próximos passos sugeridos
- Implementar comandos de criação/consulta de vendinhas
- Persistir dados (SQLite/postgres)
- Adicionar testes e CI
