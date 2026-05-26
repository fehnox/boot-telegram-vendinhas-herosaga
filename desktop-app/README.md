# HeroSaga Monitor Desktop

Aplicativo Electron para gerenciar o monitor sem editar arquivo manualmente.

## Funções

- Cadastrar lojinhas (nome + URL)
- Cadastrar `TOKEN`, `CHAT_ID`, `CHAT_IDS`, `DISCORD_WEBHOOK` e `DISCORD_MESSAGE`
- Configurar VPS (`VPS_SSH_TARGET`, `VPS_SSH_KEY_PATH`, `VPS_PROJECT_DIR`)
- Salvar tudo em `../config/shop_urls.txt` e `../.env`
- Sincronizar Git + VPS e reiniciar worker em `tmux`
- Restaurar manualmente o worker na VPS quando ele parar

## Como usar

```bash
cd desktop-app
npm install
npm start
```

## Observações

- O botão **Salvar + sincronizar VPS** roda `git add/commit/push` e depois `ssh` na VPS.
- O botão **Salvar** na aba de lojinhas também sincroniza a VPS quando `VPS_SSH_TARGET` e `VPS_PROJECT_DIR` estão preenchidos.
- O arquivo `.env` local é enviado para a VPS via `scp` durante a sincronização.
- `VPS_SSH_KEY_PATH` é opcional; se estiver vazio, o app tenta usar a autenticação SSH padrão do Windows.
- Se sua chave SSH tiver senha, o `ssh/scp` pode pedir confirmação no terminal do sistema.
