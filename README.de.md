# Proton Drive UI (inoffiziell)

[English](README.md) | **Deutsch**

Eine inoffizielle grafische Oberfläche für die offizielle Proton Drive CLI unter Linux, geschrieben in Python mit Qt (PySide6).

Die App ruft für jede Aktion die CLI auf (`proton-drive … -j`) und wertet deren JSON-Ausgabe aus. Anmeldung, Verschlüsselung und Übertragung bleiben vollständig Sache der CLI; die App speichert keine Zugangsdaten.

> **Inoffiziell.** Dieses Projekt steht in keiner Verbindung zur Proton AG und wird von ihr weder unterstützt noch geprüft.

> **Mit KI geschrieben.** Code, Tests, Dokumentation, Übersetzung und Icon dieses Projekts wurden von einem KI-Modell geschrieben (Claude von Anthropic). Siehe [KI-Hinweis](#ki-hinweis).

## Funktionen

- **Browsen:** Meine Dateien, Computer, Von mir geteilt, Mit mir geteilt und Papierkorb, mit Pfadleiste, Verlauf, Sortierung und Filter
- **Übertragen:** Dateien und Ordner hochladen (Dialog oder Drag & Drop aus dem Dateimanager), herunterladen und per Doppelklick öffnen; Übertragungen laufen nacheinander und lassen sich abbrechen
- **Verwalten:** Neuer Ordner, Umbenennen, Verschieben, Kopieren, Papierkorb, Wiederherstellen, endgültig löschen, Eigenschaften mit Ordnergröße
- **Freigabe:** Öffentlichen Link erstellen (Rolle, Passwort, Ablaufdatum), kopieren und entfernen
- **Konto:** An- und Abmelden über die CLI; die Anmeldung selbst passiert im Browser
- **Konflikte:** Im Menü „Konflikte“ einstellbar, was bei bereits vorhandenen Dateien und Ordnern passiert
- **Sprache:** Deutsch und Englisch, automatisch nach Systemsprache oder über „Ansicht → Sprache“ wählbar

## Voraussetzungen

- Linux mit grafischer Oberfläche (entwickelt unter KDE Plasma / Wayland)
- Python 3.10 oder neuer
- Die Proton Drive CLI als `proton-drive` im `PATH` oder unter `~/.local/bin/proton-drive`

Getestet mit Proton Drive CLI 0.9.0, Python 3.14 und PySide6 6.12 unter Arch Linux.

## Installation

### Arch-Linux-Paket

Ein AUR-Eintrag ist geplant. Bis dahin lässt sich das Paket selbst bauen. Die Proton Drive CLI muss vorher als Paket installiert sein, zum Beispiel `proton-drive-cli-bin` aus dem AUR.

```bash
git clone https://github.com/clnaria/unofficial-proton-drive-ui.git
cd unofficial-proton-drive-ui/packaging/arch
makepkg -si
```

Das installiert den Befehl `proton-drive-ui` und einen Starteintrag und nutzt das PySide6 des Systems.

### Aus dem Quelltext

Alle Abhängigkeiten landen in einer Umgebung im Projektordner; am System wird nichts installiert.

```bash
git clone https://github.com/clnaria/unofficial-proton-drive-ui.git
cd unofficial-proton-drive-ui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Starten

Mit dem Arch-Paket startest du „Proton Drive UI (inoffiziell)“ über das Startmenü oder mit `proton-drive-ui`. Aus dem Quelltext:

```bash
./run.sh
```

Beim ersten Start ohne bestehende CLI-Sitzung bietet die App „Anmelden …“ an.

### Eintrag im Startmenü für den Quelltext

```bash
./install-launcher.sh
```

Das legt `~/.local/share/applications/proton-drive-ui.desktop` an, mit dem aktuellen Ort des Projektordners. Nach dem Verschieben des Ordners das Skript erneut ausführen. Entfernen:

```bash
./install-launcher.sh --remove
```

## Tastenkürzel

| Kürzel | Aktion |
|---|---|
| `F5` | Aktualisieren |
| `Alt+←` / `Alt+→` / `Alt+↑` | Zurück / Vor / Übergeordneter Ordner |
| `Strg+U` | Dateien hochladen |
| `Strg+D` | Herunterladen |
| `Strg+Umschalt+N` | Neuer Ordner |
| `F2` | Umbenennen |
| `Entf` | In den Papierkorb |
| `Alt+Eingabe` | Eigenschaften |
| `Strg+F` | Im Ordner filtern |

## Bekannte Grenzen

- **Kein Fortschritt in Prozent.** Die CLI meldet bei Übertragungen nur eine Zusammenfassung am Ende; die App zeigt deshalb „Läuft …“ mit Laufzeit.
- **Gleichnamige Elemente im Papierkorb.** Die CLI (Stand 0.9.0) spricht Elemente im Papierkorb nur über ihren Namen an und kann gleichnamige nicht unterscheiden. Die App warnt in diesem Fall vor dem Wiederherstellen oder Löschen.
- **Drag & Drop nur in eine Richtung.** Dateien lassen sich in die App ziehen, aber nicht aus ihr heraus; dafür gibt es „Herunterladen …“.
- **Fotos und Alben** der CLI sind noch nicht eingebunden.
- **Passwort für Freigabelinks:** Es wird der CLI als Kommandozeilenargument übergeben und ist für die Dauer des Aufrufs in der Prozessliste des eigenen Rechners sichtbar.

## Aufbau

| Datei | Zweck |
|---|---|
| `proton_drive_ui/app.py` | Die gesamte App (Texte im Quelltext sind englisch) |
| `proton_drive_ui/translations.py` | Deutsche Übersetzung der Oberfläche |
| `proton_drive_ui/icon.svg` | App-Icon (eigenes Motiv, kein Proton-Logo) |
| `data/proton-drive-ui.desktop` | Starteintrag für Pakete |
| `tests/` | Tests; laufen gegen eine simulierte CLI, ohne Konto |
| `pyproject.toml` | Paketdaten und Build-Konfiguration |
| `packaging/arch/PKGBUILD` | Bauanleitung für das Arch-Linux-Paket |
| `run.sh` | Startet die App aus der lokalen Umgebung |
| `install-launcher.sh` | Legt den Startmenü-Eintrag an oder entfernt ihn |
| `requirements.txt`, `requirements-dev.txt` | Python-Abhängigkeiten für Betrieb und Entwicklung |
| `LICENSE` | Lizenztext (MIT) |

Geöffnete Dateien liegen vorübergehend unter `~/.cache/proton-drive-ui/open` und werden beim Start und beim Beenden gelöscht. Einstellungen stehen in `~/.config/proton-drive-ui/`.

## Entwicklung

Die Tests brauchen weder Proton-Konto noch Netz; sie steuern die App gegen eine simulierte CLI.

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## KI-Hinweis

Dieses Projekt wurde mit KI geschrieben, und das soll klar sein, bevor du dich darauf verlässt.

- **Was die KI gemacht hat:** Claude, ein KI-Modell von Anthropic, hat über Claude Code den Code, die Tests, die Dokumentation, die deutsche Übersetzung, die Paketdateien und das Icon geschrieben. Die Commits nennen es als Mitautor.
- **Was der Maintainer gemacht hat:** Festgelegt, was die App können soll, die Arbeit gesteuert und die App von Hand gegen die echte Proton Drive CLI mit einem echten Konto getestet.
- **Was nicht passiert ist:** Keine unabhängige Code-Durchsicht und kein Sicherheitsaudit.

Die App startet nur die offizielle CLI und liest deren Ausgabe; Anmeldung, Verschlüsselung und Übertragung erledigt die CLI. Trotzdem kann sie Dateien in deinem Proton Drive verschieben, freigeben und endgültig löschen. Lies also den Code oder probiere sie zuerst mit unwichtigen Daten aus, wenn dir das wichtig ist.

## Lizenz

MIT – jeder darf die Software frei benutzen, kopieren, verändern und weitergeben, auch kommerziell. Einzige Bedingung: Der Lizenztext aus `LICENSE` bleibt bei Kopien dabei. Es gibt keine Gewährleistung.
