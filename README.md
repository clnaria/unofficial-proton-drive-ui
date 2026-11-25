# Proton Drive UI (unofficial)

**English** | [Deutsch](README.de.md)

An unofficial graphical front end for the official Proton Drive CLI on Linux, written in Python with Qt (PySide6).

The app runs the CLI for every action (`proton-drive … -j`) and reads its JSON output. Signing in, encryption and transfers stay entirely with the CLI; the app stores no credentials.

> **Unofficial.** This project is not affiliated with Proton AG, and is neither supported nor reviewed by them.

> **Written with AI.** The code, tests, documentation, translation and icon of this project were written by an AI model (Claude by Anthropic). See [AI disclosure](#ai-disclosure).

## Features

- **Browse:** My files, Computer, Shared by me, Shared with me and Trash, with a breadcrumb bar, history, sorting and a filter
- **Transfer:** Upload files and folders (dialog or drag and drop from the file manager), download them, and open files with a double click; transfers run one after another and can be cancelled
- **Manage:** New folder, rename, move, copy, trash, restore, delete permanently, properties including folder size
- **Share:** Create a public link (role, password, expiry date), copy it and remove it
- **Account:** Sign in and out through the CLI; the sign-in itself happens in your browser
- **Conflicts:** The “Conflicts” menu sets what happens when a file or folder already exists
- **Language:** English and German, chosen from the system language or under “View → Language”

## Requirements

- Linux with a graphical desktop (developed on KDE Plasma / Wayland)
- Python 3.10 or newer
- The Proton Drive CLI as `proton-drive` in your `PATH` or at `~/.local/bin/proton-drive`

Tested with Proton Drive CLI 0.9.0, Python 3.14 and PySide6 6.12 on Arch Linux.

## Installation

### Arch Linux package

An AUR entry is planned. Until then you can build the package yourself. The Proton Drive CLI has to be installed as a package first, for example `proton-drive-cli-bin` from the AUR.

```bash
git clone https://github.com/clnaria/unofficial-proton-drive-ui.git
cd unofficial-proton-drive-ui/packaging/arch
makepkg -si
```

This installs the `proton-drive-ui` command and a launcher entry, and uses the system's PySide6.

### From source

All dependencies go into an environment inside the project folder; nothing is installed system-wide.

```bash
git clone https://github.com/clnaria/unofficial-proton-drive-ui.git
cd unofficial-proton-drive-ui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Running

With the Arch package, start “Proton Drive UI (unofficial)” from the application launcher or run `proton-drive-ui`. From a source checkout:

```bash
./run.sh
```

If the CLI has no session yet, the app offers “Sign in …”.

The language follows your system. To force one, use “View → Language” or set `PROTON_DRIVE_UI_LANG=en` (or `de`) when starting.

### Application launcher entry for a source checkout

```bash
./install-launcher.sh
```

This creates `~/.local/share/applications/proton-drive-ui.desktop`, pointing at the current location of the project folder. Run the script again after moving the folder. To remove the entry:

```bash
./install-launcher.sh --remove
```

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `F5` | Refresh |
| `Alt+←` / `Alt+→` / `Alt+↑` | Back / Forward / Parent folder |
| `Ctrl+U` | Upload files |
| `Ctrl+D` | Download |
| `Ctrl+Shift+N` | New folder |
| `F2` | Rename |
| `Del` | Move to trash |
| `Alt+Enter` | Properties |
| `Ctrl+F` | Filter in folder |

## Known limitations

- **No progress percentage.** The CLI only reports a summary at the end of a transfer, so the app shows “Running …” with the elapsed time.
- **Items with the same name in the trash.** The CLI (as of 0.9.0) addresses trashed items by name only and cannot tell apart items that share a name. The app warns before restoring or deleting in that case.
- **Drag and drop works one way.** Files can be dragged into the app but not out of it; use “Download …” instead.
- **Photos and albums** of the CLI are not integrated yet.
- **Share link password:** It is passed to the CLI as a command-line argument and is visible in your own machine's process list while the call runs.

## Project layout

| File | Purpose |
|---|---|
| `proton_drive_ui/app.py` | The whole app (source texts are English) |
| `proton_drive_ui/translations.py` | German translation of the interface |
| `proton_drive_ui/icon.svg` | App icon (an original design, not the Proton logo) |
| `data/proton-drive-ui.desktop` | Launcher entry used by packages |
| `tests/` | Test suite; runs against a fake CLI, no account needed |
| `pyproject.toml` | Package metadata and build configuration |
| `packaging/arch/PKGBUILD` | Build recipe for the Arch Linux package |
| `run.sh` | Starts the app from the local environment |
| `install-launcher.sh` | Creates or removes the launcher entry |
| `requirements.txt`, `requirements-dev.txt` | Python dependencies for running and for development |
| `LICENSE` | Licence text (MIT) |

Opened files are kept temporarily in `~/.cache/proton-drive-ui/open` and deleted on start and on exit. Settings are stored in `~/.config/proton-drive-ui/`.

## Development

The tests need no Proton account and no network; they drive the app against a fake CLI.

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## AI disclosure

This project was written with AI, and that should be clear before you rely on it.

- **What the AI did:** Claude, an AI model by Anthropic, wrote the code, the tests, the documentation, the German translation, the packaging files and the icon, working through Claude Code. The commits name it as co-author.
- **What the maintainer did:** Decided what the app should do, directed the work and tested the app by hand against the real Proton Drive CLI with a real account.
- **What has not happened:** No independent code review and no security audit.

The app only starts the official CLI and reads its output; signing in, encryption and transfers are done by the CLI. Even so, it can move, share and permanently delete files in your Proton Drive, so read the code or try it with unimportant data first if that matters to you.

## Licence

MIT – anyone may use, copy, modify and distribute the software freely, including commercially. The only condition: the licence text from `LICENSE` stays with copies. There is no warranty.
