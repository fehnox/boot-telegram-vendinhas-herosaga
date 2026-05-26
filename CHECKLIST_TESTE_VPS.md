# Checklist de Teste - Notificacoes com PC desligado

Data: 25/05/2026
Objetivo: confirmar que o worker continua enviando alertas mesmo com o PC offline.

## 1) Validacao local (PC)

1. Confirmar alteracoes no git:

```bash
git status --short
```

Esperado:
- scripts/run_vps_worker.sh alterado
- data/history.json pode aparecer alterado por execucao local

2. Validar se o .env local tem configuracao de sync para VPS:

Campos obrigatorios para sync remoto no app:
- VPS_SSH_TARGET
- VPS_SSH_KEY_PATH
- VPS_PROJECT_DIR

Observacao:
- Se VPS_SSH_KEY_PATH estiver vazio, a sincronizacao UI -> VPS pode falhar.
- Depois de trocar as lojas, espere a VPS completar pelo menos 1 ciclo inteiro antes de fazer a compra de teste; o primeiro ciclo só cria a base das novas URLs.

3. Commit e push:

```bash
git add scripts/run_vps_worker.sh CHECKLIST_TESTE_VPS.md
git commit -m "fix: keep vps worker loop alive on transient failures"
git push
```

## 2) Atualizacao na VPS

1. Entrar na VPS:

```bash
ssh -i /caminho/sua-chave.key ubuntu@SEU_IP
```

2. Ir para o projeto e atualizar:

```bash
cd /home/ubuntu/boot-telegram-vendinhas-herosaga
git pull --ff-only
```

3. Reiniciar worker no tmux:

```bash
tmux kill-session -t bot || true
tmux new -s bot
bash scripts/run_vps_worker.sh
```

4. Em outra conexao SSH, acompanhar log:

```bash
tmux attach -t bot
```

Esperado no log:
- Monitor iniciado
- Verificando itens
- Verificacao concluida
- Em caso de erro temporario: mensagens de retry sem encerrar o loop
- Se as lojas foram atualizadas recentemente, o primeiro ciclo pode registrar apenas o baseline; a compra de teste deve acontecer depois dessa rodada inicial.

## 3) Teste real de notificacao

1. Com worker rodando na VPS, desligar o PC.
2. Aguardar um ciclo de monitoramento.
3. Confirmar recebimento no Telegram.

Se nao chegar:
- verificar se TOKEN e CHAT_ID estao corretos no .env da VPS
- validar acesso de rede da VPS ao dominio da loja e ao Telegram
- checar se o tmux continua vivo apos erro transitório

## 4) Confirmacao final

Teste aprovado quando:
- notificacao chega com PC desligado
- worker nao morre apos falha de git pull/rede/python
- proximo ciclo continua executando automaticamente
