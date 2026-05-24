# boot-telegram-vendinhas-herosaga

Worker Python para monitorar lojas do Herosaga, enviar alertas no Telegram e rodar sem PC ligado usando GitHub Actions ou uma VPS com `git pull`.

## Como funciona

O ponto de entrada do monitor é [bot.py](bot.py) e o comando do worker é `python bot.py`.

O script executa um ciclo único por processo, salva o histórico em [data/history.json](data/history.json) e encerra corretamente. Isso permite que o GitHub Actions rode a cada 3 minutos sem loop infinito e também facilita o uso em VPS com `tmux`.

## Requisitos

- Python 3.11.
- Um bot do Telegram com `TOKEN` e `CHAT_ID`.

## Configurar GitHub Secrets

1. Abra o repositório no GitHub.
2. Vá em Settings > Secrets and variables > Actions.
3. Crie os secrets:
   - `TOKEN`
   - `CHAT_ID`

O workflow usa esses secrets no runtime e não expõe os valores no código.

## Configurar lojas

As lojas monitoradas ficam em [config/shop_urls.txt](config/shop_urls.txt), uma URL por linha.

Se você quiser sobrescrever isso localmente, ainda pode usar a variável `SHOP_URLS` no `.env`.

Exemplo:

```txt
https://herosaga.com.br/?module=vending&action=viewshop&id=30313
https://herosaga.com.br/?module=vending&action=viewshop&id=30314
```

## GitHub Actions

O workflow em [.github/workflows/market.yml](.github/workflows/market.yml) roda automaticamente a cada 3 minutos com `ubuntu-latest`, instala Python 3.11, instala as dependências e executa [bot.py](bot.py).

Como o runner do GitHub Actions é temporário, o workflow também persiste [data/history.json](data/history.json) de volta no repositório quando o estado muda. Assim a próxima execução compara o mercado com o ciclo anterior.

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
TOKEN=seu_token_aqui
CHAT_ID=seu_chat_id_aqui
```

Variáveis opcionais:

```env
SHOP_URL=https://herosaga.com.br/?module=vending&action=viewshop&id=30313
SHOP_URLS=
CHAT_IDS=
DISCORD_WEBHOOK=
NOTIFY_COOLDOWN=300
REQUEST_TIMEOUT=20
```

Se quiser alerta no Discord pelo GitHub Actions, crie também o secret `DISCORD_WEBHOOK`.

Se você alterar [config/shop_urls.txt](config/shop_urls.txt) e fizer `git push`, a VPS atualiza com `git pull` e passa a ler as novas lojas no próximo ciclo do `tmux`.

Se `CHAT_IDS` estiver preenchido com uma lista separada por vírgulas, o bot envia alertas para vários usuários sem mudar o código.

## Rodar na VPS

Na VPS Ubuntu, o worker pode ser mantido em `tmux` com o script [scripts/run_vps_worker.sh](scripts/run_vps_worker.sh). Ele faz `git pull --ff-only` antes de cada ciclo, então qualquer atualização enviada para o GitHub, incluindo [config/shop_urls.txt](config/shop_urls.txt), chega na VPS automaticamente no próximo ciclo.

Exemplo:

```bash
cd /home/ubuntu/boot-telegram-vendinhas-herosaga
tmux new -s bot
bash scripts/run_vps_worker.sh
```

## Testar localmente

1. Preencha [.env](.env) com `TOKEN` e `CHAT_ID`.
2. Rode `python bot.py`.
3. Verifique os logs no terminal: `Monitor iniciado`, `Verificando mercado`, `Item encontrado`, `Alerta enviado` e `Execução finalizada`.

## Estrutura principal

- [bot.py](bot.py) - monitor único por execução e notificações.
- [.github/workflows/market.yml](.github/workflows/market.yml) - cron do GitHub Actions.
- [.env.example](.env.example) - exemplo de variáveis.
- [requirements.txt](requirements.txt) - dependências do worker.
- [src/bot/main.py](src/bot/main.py) - utilitário separado do worker principal.

## Observações

- O backend usa apenas caminhos relativos, então é compatível com Linux e com o runner do GitHub Actions.
- [Procfile](Procfile) continua disponível para o start tradicional, mas o monitor principal agora foi ajustado para execução temporária.
