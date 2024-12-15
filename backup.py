# Make a backup of the Minecraft_Server World as Zip in Backup (1 Backup a Day)
import os
import shutil
import glob
from datetime import datetime

TEMP_PATH = ".temp"
BACKUP_PATH = "backups"


def remake_temp():
    shutil.rmtree(TEMP_PATH)


def make_folders():
    try:
        os.makedirs(TEMP_PATH)
    except FileExistsError:
        pass
    try:
        os.makedirs(BACKUP_PATH)
    except FileExistsError:
        pass


def copy_worlds():
    src_folder = "world"
    dst_folder = ".temp/world"
    shutil.copytree(src_folder, dst_folder, dirs_exist_ok=True)

    # Need this if used the recommended Paper Server
    try:
        src_folder = "world_nether"
        dst_folder = ".temp/world_nether"
        shutil.copytree(src_folder, dst_folder, dirs_exist_ok=True)
    except FileExistsError:
        pass

    try:
        src_folder = "world_the_end"
        dst_folder = ".temp/world_the_end"
        shutil.copytree(src_folder, dst_folder, dirs_exist_ok=True)
    except FileExistsError:
        pass


def make_backup():
    make_folders()
    copy_worlds()

    # Name of ZIP-File
    now = datetime.now()
    zip_file_name = f'backup_{now.strftime("%d-%m-%Y")}'

    checkup = glob.glob(f"{BACKUP_PATH}/*.zip")

    if f"{BACKUP_PATH}\\{zip_file_name}.zip" not in checkup:

        file_to_add = "time.txt"
        with open(file_to_add, "w") as file:
            file.write(now.strftime("%H:%M:%S"))

        shutil.move(file_to_add, TEMP_PATH)

        shutil.make_archive(zip_file_name, 'zip', TEMP_PATH)

        shutil.move(f"{zip_file_name}.zip", BACKUP_PATH)

        remake_temp()
        cleanup_backup()

        return "Backup saved!"

    else:
        remake_temp()
        cleanup_backup()

        return "Backup for today is already done!"


def cleanup_backup():
    check = glob.glob(f"{BACKUP_PATH}/*zip")

    if len(check) >= 3:
        new = []
        for i, name in enumerate(check):
            temp = name.replace(f"{BACKUP_PATH}\\backup_", "").replace(".zip", "").split("-")
            temp = temp[::-1]
            temp = int("".join(map(str, temp)))

            new.append([temp, i])

        new = sorted(new, key=lambda x: x[0])

        remove_id = new.pop(0)[1]

        os.remove(check[remove_id])
