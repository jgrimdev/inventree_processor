import sys
import os
import shutil
import csv
import threading
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import requests
import webbrowser
import customtkinter as ctk
from tkinter import filedialog, messagebox

# --- NASTAVENÍ PRO AUTO-AKTUALIZACE ---
CURRENT_VERSION = "v1.0"  # Tuto hodnotu zvedni vždy, když vydáváš novou verzi (např. na "v1.1")
GITHUB_REPO = "TvojeJmeno/TvujRepozitar"  # PŘEPIŠ NA SVŮJ SKUTEČNÝ GITHUB (např. "novak/inventree")

# Nastavení vzhledu
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def resource_path(relative_path):
    """Získá absolutní cestu k assetům – funguje při vývoji i po zabalení v PyInstalleru."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class InvenTreeDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"InvenTree Desktop Processor ({CURRENT_VERSION})")
        self.geometry("680x560")
        self.minsize(600, 500)

        # Načtení ikony okna
        icon_path = resource_path(os.path.join("img", "icon.ico"))
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception as e:
                print(f"Ikonu okna se nepodařilo načíst: {e}")

        self.selected_folder = ""
        self.selected_csv = ""

        # UI Rozložení
        self._build_ui()

        # Spuštění kontroly aktualizací na pozadí, aby to nebrzdilo start aplikace
        if "TvojeJmeno" not in GITHUB_REPO:
            threading.Thread(target=self._check_for_updates, daemon=True).start()

    def _build_ui(self):
        self.header_label = ctk.CTkLabel(
            self, text="🌲 InvenTree - Zpracování dat", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.header_label.pack(pady=(20, 10))

        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.pack(fill="x", padx=20, pady=10)

        self.folder_btn = ctk.CTkButton(
            self.input_frame, text="1. Vybrat složku s fotkami", command=self._choose_folder, width=190
        )
        self.folder_btn.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.folder_label = ctk.CTkLabel(self.input_frame, text="Zatím nevybráno...", text_color="gray")
        self.folder_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.csv_btn = ctk.CTkButton(
            self.input_frame, text="2. Vybrat CSV tabulku", command=self._choose_csv, width=190
        )
        self.csv_btn.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.csv_label = ctk.CTkLabel(self.input_frame, text="Zatím nevybráno...", text_color="gray")
        self.csv_label.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.actions_frame = ctk.CTkFrame(self)
        self.actions_frame.pack(fill="x", padx=20, pady=10)

        self.sort_btn = ctk.CTkButton(
            self.actions_frame,
            text="📁 Roztřídit fotky do podsložek",
            command=lambda: self._run_thread(self._sort_photos),
            fg_color="#2B8A3E", hover_color="#237032", height=38
        )
        self.sort_btn.pack(side="left", expand=True, padx=10, pady=10)

        self.gpx_btn = ctk.CTkButton(
            self.actions_frame,
            text="🗺️ Vytvořit GPX pro Mapy.cz",
            command=lambda: self._run_thread(self._generate_gpx),
            fg_color="#1971C2", hover_color="#145899", height=38
        )
        self.gpx_btn.pack(side="right", expand=True, padx=10, pady=10)

        self.log_box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Courier", size=12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        self._log("Připraveno. Vyberte složku s fotkami a CSV soubor.")

    def _check_for_updates(self):
        try:
            # Dotaz na API GitHubu na nejnovější release
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "")

                # Porovnání s naší verzí (např. v1.1 vs v1.0)
                if latest_version and latest_version != CURRENT_VERSION:
                    update_url = data.get("html_url")
                    # Přepnutí zpět do hlavního GUI vlákna pro zobrazení okna
                    self.after(1500, lambda: self._show_update_prompt(latest_version, update_url))
        except Exception:
            pass  # Pokud není internet, potichu to ignorujeme

    def _show_update_prompt(self, latest_version, update_url):
        msg = f"Nalezena nová verze programu ({latest_version})!\nVy používáte {CURRENT_VERSION}.\n\nChcete otevřít stránku pro stažení nového .exe souboru?"
        if messagebox.askyesno("Aktualizace k dispozici", msg):
            webbrowser.open(update_url)

    def _log(self, message):
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    def _choose_folder(self):
        path = filedialog.askdirectory(title="Vyberte složku obsahující fotky")
        if path:
            self.selected_folder = path
            self.folder_label.configure(text=f".../{os.path.basename(path)}", text_color=("black", "white"))
            self._log(f"Zvolena složka: {path}")

            if not self.selected_csv:
                csv_candidates = list(Path(path).glob("*.csv"))
                if csv_candidates:
                    self._set_csv(str(csv_candidates[0]))
                    self._log(f"Automaticky detekováno CSV: {csv_candidates[0].name}")

    def _choose_csv(self):
        file = filedialog.askopenfilename(
            title="Vyberte CSV tabulku",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file:
            self._set_csv(file)

    def _set_csv(self, path):
        self.selected_csv = path
        self.csv_label.configure(text=os.path.basename(path), text_color=("black", "white"))
        self._log(f"Zvoleno CSV: {path}")

    def _run_thread(self, target_function):
        if not self.selected_folder or not self.selected_csv:
            messagebox.showwarning("Chybí podklady", "Nejprve vyberte složku s fotkami i CSV soubor.")
            return
        thread = threading.Thread(target=target_function, daemon=True)
        thread.start()

    def _parse_csv(self):
        records = []
        with open(self.selected_csv, mode="r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
            reader = csv.DictReader(f, delimiter=delimiter)
            reader.fieldnames = [c.strip().lower() for c in reader.fieldnames]
            for row in reader:
                records.append(row)
        return records

    def _sort_photos(self):
        self._log("\n--- Spouštím třídění fotografií ---")
        try:
            records = self._parse_csv()
            moved_count = 0
            missing_count = 0

            for row in records:
                file_name = row.get("file name") or row.get("filename") or row.get("file_name")
                folder_name = row.get("folder name (5 digits)") or row.get("folder name") or row.get("foldername")

                if not file_name or not folder_name:
                    continue

                folder_name = str(folder_name).strip().zfill(5)
                file_name = str(file_name).strip()

                src_path = Path(self.selected_folder) / file_name
                dest_dir = Path(self.selected_folder) / folder_name

                if src_path.is_file():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / file_name
                    shutil.move(str(src_path), str(dest_path))
                    moved_count += 1
                else:
                    if not (dest_dir / file_name).exists():
                        missing_count += 1

            self._log(f"✅ Hotovo: Přesunuto {moved_count} fotografií do podsložek.")
            if missing_count > 0:
                self._log(f"⚠️ {missing_count} fotografií z CSV nebylo nalezeno.")
            messagebox.showinfo("Úspěch", f"Fotografie byly roztříděny ({moved_count} přesunuto).")
        except Exception as e:
            self._log(f"❌ Chyba při třídění: {str(e)}")
            messagebox.showerror("Chyba", f"Nastala chyba: {e}")

    def _generate_gpx(self):
        self._log("\n--- Vytvářím GPX soubor pro Mapy.cz ---")
        try:
            records = self._parse_csv()
            points_by_folder = {}
            project_name = "Projekt"

            for row in records:
                if project_name == "Projekt" and row.get("project name"):
                    project_name = str(row.get("project name")).strip()

                folder_name = row.get("folder name (5 digits)") or row.get("folder name") or row.get("foldername")
                lat_str = row.get("latitude") or row.get("lat")
                lon_str = row.get("longitude") or row.get("lon")

                is_main = str(row.get("is main gps") or row.get("is_main_gps") or "no").strip().lower()

                if not folder_name or not lat_str or not lon_str:
                    continue

                try:
                    lat = float(str(lat_str).replace(",", "."))
                    lon = float(str(lon_str).replace(",", "."))
                except ValueError:
                    continue

                folder_name = str(folder_name).strip().zfill(5)

                # OPRAVA: Zapíše se do mapy POUZE pokud je natvrdo označeno YES/TRUE/1
                if is_main in ["yes", "true", "1"]:
                    points_by_folder[folder_name] = (lat, lon)

            if not points_by_folder:
                self._log("⚠️ V CSV nebyly nalezeny žádné HLAVNÍ GPS body. Nikde nebylo zaškrtnuto uložení pozice.")
                messagebox.showwarning("Prázdné GPX",
                                       "Nebyly nalezeny žádné souřadnice k exportu (žádná fotka nebyla označena jako Hlavní GPS).")
                return

            gpx = ET.Element("gpx", version="1.1", creator="InvenTree Desktop",
                             xmlns="http://www.topografix.com/GPX/1/1")

            for name, (lat, lon) in sorted(points_by_folder.items()):
                wpt = ET.SubElement(gpx, "wpt", lat=str(lat), lon=str(lon))
                name_elem = ET.SubElement(wpt, "name")
                name_elem.text = name

            xml_str = minidom.parseString(ET.tostring(gpx)).toprettyxml(indent="  ", encoding="utf-8")

            safe_project_name = "".join([c for c in project_name if c.isalnum() or c in " _-"])
            gpx_filename = f"{safe_project_name}_mapa.gpx"
            output_path = Path(self.selected_folder) / gpx_filename

            with open(output_path, "wb") as f:
                f.write(xml_str)

            self._log(f"✅ GPX vytvořen: {output_path.name} ({len(points_by_folder)} bodů)")
            messagebox.showinfo("GPX Vytvořeno", f"GPX bodů bylo uloženo ({len(points_by_folder)} stromů).")
        except Exception as e:
            self._log(f"❌ Chyba při tvorbě GPX: {str(e)}")
            messagebox.showerror("Chyba", f"Nastala chyba: {e}")


if __name__ == "__main__":
    app = InvenTreeDesktopApp()
    app.mainloop()