# Install, update, and remove Agen Mini

[Release files and checksums](https://github.com/Zwart04/agenmini/releases/latest)

**Public preview:** downloads are open, but provider quotas and local-model availability still vary. Verify every package with its published SHA256 before installing.

Choose **x64 / amd64 / x86_64** for Intel and AMD computers, or **arm64 /
aarch64** for supported ARM Linux systems. Model weights and provider accounts
are not bundled. The app's interface currently uses Indonesian labels; the
instructions below include the relevant labels where useful.

## Windows 10 / 11 x64

1. Download `agenmini-setup-VERSION-windows-x64.exe` and its `.sha256` file.
2. Compare the SHA256 using PowerShell `Get-FileHash .\agenmini-setup-VERSION-windows-x64.exe -Algorithm SHA256`.
3. Run the installer, then open **Agen Mini** from Start. First setup provides a password.
4. For the CLI, open **Agen Mini CLI** from Start.

Alternatively, extract `agenmini-VERSION-windows-x64.zip` and open its launcher.
From that folder, run `.\agenmini.cmd` in PowerShell for CLI commands.

Data lives in `%LOCALAPPDATA%\AgenMini\data`, separate from the program.
To update, back up through Settings and run the newer installer in the same
location. To remove, use **Windows Settings → Apps → Agen Mini → Uninstall**.
Uninstall preserves your data; remove the data directory manually only if you
intend to erase accounts, settings, and conversations after backing up.

## Linux desktop and CLI

Download a package and its matching `.sha256` file into the same folder, then:

```sh
sha256sum -c PACKAGE-NAME.sha256
```

Choose **one** install command, replacing `VERSION` with the downloaded version:

```sh
# Debian / Ubuntu / Mint, Intel or AMD
sudo apt install ./agenmini_VERSION_amd64.deb

# Fedora, Intel or AMD
sudo dnf install ./agenmini-VERSION-1.x86_64.rpm

# Arch / EndeavourOS / Manjaro, Intel or AMD
sudo pacman -U ./agenmini-VERSION-1-x86_64.pkg.tar.zst
```

ARM64 packages are named `_arm64.deb` and `.aarch64.rpm`; Arch is x86_64 only.
These are direct package downloads, not a signed distribution repository or AUR.

Open the application menu entry or run `agenmini open` **as your normal user**.
First setup opens a private local page containing the initial password. The
interface runs in your browser; it does not require Electron or Docker.

```sh
agenmini start --no-browser
agenmini status
agenmini password
agenmini provider online
agenmini model YOUR-MODEL-ID
agenmini stop
```

Configure the endpoint/API key in Settings before using that model. The web app
and CLI share the same user settings. By default, the app listens on loopback
`127.0.0.1:8765`; its private gateway listens on `127.0.0.1:20128`.

Data is stored in `~/.local/share/agenmini`, or `AGENMINI_DATA_DIR` if set.
Before an update, finish active tasks, create a backup in Settings, and run
`agenmini stop`. Install the newer package with the same package-manager command.

To remove, stop the app and choose the command for your distribution:

```sh
sudo apt remove agenmini
sudo dnf remove agenmini
sudo pacman -R agenmini
```

Removal preserves the user data directory. Desktop tools run with your user's
privileges; full access is not container isolation.

### Other GNU/Linux: portable archive

Requires glibc 2.35+, Node.js, Git, and xdg-utils. Extract the archive without sudo:

```sh
tar -xzf agenmini-VERSION-linux-amd64.tar.gz
./opt/agenmini/runtime/bin/python3 ./opt/agenmini/launcher.py open
```

Use the `arm64` archive for ARM. The archive's `usr/bin/agenmini` wrapper expects
an installation under `/opt`; use the Python command above for a portable folder.
Alpine/musl, Android and NixOS are not claimed as supported desktop targets.
[Detailed Linux reference](../CARA-PASANG-LINUX.md)

## Connect a model

Open **Settings → AI connections & model** (**Pengaturan → Koneksi AI & model**).
Choose the built-in OAuth/API gateway, a direct API, or a running local endpoint.
Enter credentials if needed, select the exact model ID, save, and test a response.
Provider quotas and availability still apply.

Desktop can connect to an already-running llama.cpp/Ollama OpenAI-compatible
endpoint through direct API settings. Automated local-model downloads and
service management require the VPS supervisor installation. A saved key or
model name alone does not prove the provider works.

## VPS: Debian / Ubuntu

On **your own target server**, log in as root and run:

```sh
curl -fL https://github.com/Zwart04/agenmini/releases/latest/download/pasang-vps.sh -o pasang-vps.sh
curl -fL https://github.com/Zwart04/agenmini/releases/latest/download/pasang-vps.sha256 -o pasang-vps.sha256
sha256sum -c pasang-vps.sha256 && bash pasang-vps.sh
```

The installer prepares Docker/Compose, offers password and optional swap setup,
and prints the app address. Open TCP 443 in your provider firewall. The initial
certificate is self-signed. RAM 2 GB is recommended for API use; local models
need more RAM and CPU, depending on the model. Swap does not replace fast RAM.

**Update without deleting the existing installation, models, `.env`, or data:**

```sh
agen update check
agen update
agen update status
agen status
```

If an older updater fails, download the current installer/checksum again and
install over the existing directory. Data and settings are retained.

To review removal: `agen hapus --dry-run`. `agen hapus` removes Agen Mini
services while retaining data/models. `agen hapus --all` also erases its private
data after confirmation; back up first. It does not uninstall Docker or remove
unrelated projects. [Removal reference](../UNINSTALL.md)

## macOS / source setup

No native macOS installer is currently published. Source setup requires Python
3.12, Node.js, Git, and the dependencies in `requirements.lock`.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
DATA_DIR="$HOME/.local/share/agenmini" WEB_HOST=127.0.0.1 \
  WEB_PORT_INTERNAL=8765 WEB_TLS=0 LLM_BACKEND=online python -m app.main
```

The first launch prints a generated password; open `http://127.0.0.1:8765`.
This is manual source setup, not a verified native macOS package. You can also
use the web interface of your own VPS from a macOS or mobile browser.

[Back to README](../README.md) · [Report a problem](https://github.com/Zwart04/agenmini/issues)
