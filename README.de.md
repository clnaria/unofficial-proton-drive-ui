# Proton Drive UI (inoffiziell)

[English](README.md) | **Deutsch**

Eine inoffizielle grafische Oberfläche für die offizielle Proton Drive CLI unter Linux, geschrieben in Python mit Qt (PySide6).

Die App ruft für jede Aktion die CLI auf (`proton-drive … -j`) und wertet deren JSON-Ausgabe aus. Anmeldung, Verschlüsselung und Übertragung bleiben vollständig Sache der CLI; die App speichert keine Zugangsdaten.

> **Inoffiziell.** Dieses Projekt steht in keiner Verbindung zur Proton AG und wird von ihr weder unterstützt noch geprüft.

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

Alle Abhängigkeiten landen in einer Umgebung im Projektordner; am System wird nichts installiert.

```bash
git clone https://github.com/clnaria/unofficial-proton-drive-ui.git
cd unofficial-proton-drive-ui
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Starten

```bash
./run.sh
```

Beim ersten Start ohne bestehende CLI-Sitzung bietet die App „Anmelden …“ an.

### Eintrag im Startmenü

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
| `proton_drive_ui.py` | Die gesamte App (Texte im Quelltext sind englisch) |
| `translations.py` | Deutsche Übersetzung der Oberfläche |
| `run.sh` | Startet die App aus der lokalen Umgebung |
| `install-launcher.sh` | Legt den Startmenü-Eintrag an oder entfernt ihn |
| `icon.svg` | App-Icon (eigenes Motiv, kein Proton-Logo) |
| `requirements.txt` | Python-Abhängigkeiten |
| `LICENSE` | Lizenztext (MIT) |

Geöffnete Dateien liegen vorübergehend unter `~/.cache/proton-drive-ui/open` und werden beim Start und beim Beenden gelöscht. Einstellungen stehen in `~/.config/proton-drive-ui/`.

## Lizenz

MIT – jeder darf die Software frei benutzen, kopieren, verändern und weitergeben, auch kommerziell. Einzige Bedingung: Der Lizenztext aus `LICENSE` bleibt bei Kopien dabei. Es gibt keine Gewährleistung.
