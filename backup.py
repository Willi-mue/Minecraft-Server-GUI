import os
import shutil
import glob
from datetime import datetime

# Basisverzeichnis für alles
BASE_PATH = "Server"
TEMP_PATH = os.path.join(BASE_PATH, ".temp")
BACKUP_PATH = os.path.join(BASE_PATH, "backups")

def remake_temp():
    if os.path.exists(TEMP_PATH):
        shutil.rmtree(TEMP_PATH)

def make_folders():
    os.makedirs(TEMP_PATH, exist_ok=True)
    os.makedirs(BACKUP_PATH, exist_ok=True)

def copy_worlds():
    world_names = ["world", "world_nether", "world_the_end"]
    for world in world_names:
        src = os.path.join(BASE_PATH, world)
        dst = os.path.join(TEMP_PATH, world)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)

def make_backup():
    make_folders()
    copy_worlds()

    now = datetime.now()
    zip_file_name = f'backup_{now.strftime("%d-%m-%Y")}'
    zip_path = os.path.join(BACKUP_PATH, f"{zip_file_name}.zip")

    if not os.path.exists(zip_path):
        # Erstelle Zeitdatei
        time_file = os.path.join(TEMP_PATH, "time.txt")
        with open(time_file, "w") as file:
            file.write(now.strftime("%H:%M:%S"))

        # Archiv erstellen
        shutil.make_archive(zip_file_name, 'zip', TEMP_PATH)

        # Archiv verschieben
        shutil.move(f"{zip_file_name}.zip", zip_path)

        remake_temp()
        cleanup_backup()

        return "Backup saved!"
    else:
        remake_temp()
        cleanup_backup()
        return "Backup for today is already done!"

def cleanup_backup():
    zip_files = glob.glob(os.path.join(BACKUP_PATH, "backup_*.zip"))

    if len(zip_files) >= 3:
        # Extrahiere Datum und sortiere
        dated_files = []
        for path in zip_files:
            name = os.path.basename(path)
            date_part = name.replace("backup_", "").replace(".zip", "")
            try:
                dt = datetime.strptime(date_part, "%d-%m-%Y")
                dated_files.append((dt, path))
            except ValueError:
                continue

        # Sortieren und älteste Datei löschen
        dated_files.sort(key=lambda x: x[0])
        if dated_files:
            os.remove(dated_files[0][1])
