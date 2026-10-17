# Deploy automático

O servidor deve ter um clone Git em `/opt/finances-app`, com a branch `master`,
e os secrets devem ficar em `/opt/finances-app/.env` com permissão `600`.
Esse arquivo é ignorado pelo Git e não é substituído pelo deploy.

Instalação no servidor:

```bash
install -m 0644 deploy/finances-app-deploy.service /etc/systemd/system/finances-app-deploy.service
install -m 0644 deploy/finances-app-deploy.timer /etc/systemd/system/finances-app-deploy.timer
systemctl daemon-reload
systemctl enable --now finances-app-deploy.timer
```

Comandos úteis:

```bash
systemctl status finances-app-deploy.timer
journalctl -u finances-app-deploy.service -f
systemctl start finances-app-deploy.service
```

O deploy usa `git pull --ff-only`, não executa com alterações locais e usa `flock`
para impedir dois deploys simultâneos.
