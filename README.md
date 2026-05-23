# boot-telegram-vendinhas-herosaga

Worker Python para monitorar lojas do Herosaga 24h por dia, enviar alertas no Telegram e ficar pronto para execução no Render como Background Worker.

## O que roda no Render

O ponto de entrada do deploy é [bot.py](bot.py) e o comando do worker é `python bot.py`.

## Requisitos

- Python 3.10+.
- Conta no Render.
- Um bot do Telegram com `BOT_TOKEN` e `TELEGRAM_CHAT_ID`.

## Rodar localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

No Linux ou macOS, troque a ativação da virtualenv para:

```bash
source .venv/bin/activate
```

## Configurar `.env`

Crie um arquivo `.env` na raiz do projeto com base em [.env.example](.env.example) e preencha pelo menos:

```env
BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
```

Variáveis opcionais:

```env
SHOP_URL=https://herosaga.com.br/?module=vending&action=viewshop&id=30313
DISCORD_WEBHOOK=
CHECK_INTERVAL=60
NOTIFY_COOLDOWN=300
REQUEST_TIMEOUT=20
ERROR_RETRY_DELAY=60
```

## Deploy no Render

1. Envie este repositório para o GitHub.
2. No Render, crie um novo service do tipo Background Worker.
3. Aponte para este repositório.
4. Configure:
	- Build Command: `pip install -r requirements.txt`
	- Start Command: `python bot.py`
5. Adicione as variáveis de ambiente no painel do Render.

O arquivo [Procfile](Procfile) já está configurado com `worker: python bot.py`.

## Estrutura principal

- [bot.py](bot.py) - monitor contínuo e notificações.
- [.env.example](.env.example) - exemplo de variáveis.
- [requirements.txt](requirements.txt) - dependências do worker.
- [src/bot/main.py](src/bot/main.py) - utilitário separado do worker principal.

## Observações

- Não há interface Electron/desktop neste projeto Python; o worker roda de forma independente.
- O backend usa apenas caminhos relativos, então é compatível com ambiente Linux/cloud.
