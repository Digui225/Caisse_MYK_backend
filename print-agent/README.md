# Agent d'impression (hors Docker — ADR-13)

Petit service HTTP local qui pilote l'imprimante ESC/POS USB et le tiroir (branché sur le
port DK/RJ11 de l'imprimante). Il ne connaît aucune règle métier.

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/status` | `{ "online", "paper", "model", "width" }` |
| POST | `/print` | `{ "content", "qr", "open_drawer", "cut" }` |
| POST | `/open-drawer` | impulsion seule |
| POST | `/test-print` | ticket de test |

## Sans imprimante (développement)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && sed -i 's/^PRINTER_BACKEND=.*/PRINTER_BACKEND=dummy/' .env
.venv/bin/python -m agent          # le ticket s'affiche dans le terminal
```

## Sur la machine de la caisse

```bash
lsusb                               # repérer « ID vvvv:pppp »
cp .env.example .env && nano .env   # PRINTER_VENDOR_ID / PRINTER_PRODUCT_ID
sudo cp 99-escpos.rules /etc/udev/rules.d/   # après y avoir mis les mêmes identifiants
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo usermod -aG lp $USER           # puis se déconnecter / reconnecter
./install.sh                        # venv + service systemd caisse-print-agent
curl -X POST localhost:8090/test-print
curl -X POST localhost:8090/open-drawer
```

Journal : `journalctl -u caisse-print-agent -n 100 -f`
