from PyQt5.QtCore import Qt
from backup import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QPlainTextEdit, QLabel, QAction, QMenu, QLineEdit
import subprocess
import threading
import time
import psutil

MIN_RAM = '-Xms1G'
MAX_RAM = '-Xmx3G'
SERVER_PATH = "server.jar"


class ServerProcess:
    def __init__(self):
        self.process = None
        self.stdout_thread = None
        self.player_number = 0
        self.start_time = time.time()
        self.player_names = []

    def start(self):
        if self.process is None or self.process.poll() is not None:
            command = ['java', MIN_RAM, MAX_RAM, '-jar', SERVER_PATH, '-nogui']

            self.process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stdin=subprocess.PIPE, stderr=subprocess.STDOUT, cwd='.')

            self.stdout_thread = threading.Thread(target=self._output_reader, daemon=True)
            self.stdout_thread.start()

    def stop_slow(self):
        if self.process is not None and self.process.poll() is None:
            self.process.stdin.write('say Server stoppt in 30 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(15)
            self.process.stdin.write('say Server stoppt in 15 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(5)
            self.process.stdin.write('say Server stoppt in 10 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(5)
            self.process.stdin.write('say Server stoppt in 5 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(1)
            self.process.stdin.write('say Server stoppt in 4 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(1)
            self.process.stdin.write('say Server stoppt in 3 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(1)
            self.process.stdin.write('say Server stoppt in 2 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(1)
            self.process.stdin.write('say Server stoppt in 1 Sekunden\n'.encode('utf-8'))
            self.process.stdin.flush()
            time.sleep(1)

            self.process.stdin.write('stop\n'.encode('utf-8'))
            self.process.stdin.flush()

            self.process.wait()

            self.player_number = 0

    def stop_fast(self):
        if self.process is not None and self.process.poll() is None:
            self.process.stdin.write('stop\n'.encode('utf-8'))
            self.process.stdin.flush()
            self.process.wait()
            self.player_number = 0

    def restart(self):
        self.process.stdin.write('say Server-Restart started ..\n'.encode('utf-8'))
        self.stop_slow()
        self.start()

    def backup(self):
        self.process.stdin.write('say Server-Backup started ..\n'.encode('utf-8'))
        self.process.stdin.flush()

        self.stop_slow()
        msg = make_backup()
        self.on_output(msg)
        self.start()

    def _output_reader(self):

        while True:
            output = self.process.stdout.readline().decode('utf-8')

            if not output and self.process.poll() is not None:
                break
            if output:
                self.on_output(output.strip())

    def on_output(self, output):
        ...

    def player_count(self):
        if self.process is not None and self.process.poll() is None:
            self.process.stdin.write('list\n'.encode('utf-8'))
            self.process.stdin.flush()

            output = self.process.stdout.readline().decode('utf-8').strip()

            if 'There are ' in output:
                out_s = output.split()
                self.player_names = out_s[12:]
                self.player_number = out_s[4]

    def player_text(self, msg):
        if self.process is not None and self.process.poll() is None:
            for i in self.player_names:
                if f'<{i}>' in msg:
                    return True
            return False

    def send_command(self, cmd):
        if self.process is not None and self.process.poll() is None:
            self.process.stdin.write(f'{cmd}\n'.encode('utf-8'))
            self.process.stdin.flush()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.log_text = QPlainTextEdit(self)
        self.player_chat = QPlainTextEdit(self)
        self.command_input = QLineEdit(self)
        self.commands_used = []
        self.commands_used_pointer = 0
        self.update_flag = False
        self.full_screen = False

        # font
        self.font = self.command_input.font()
        self.font.setPointSize(12)

        # Pc info
        self.cpu_percent = ".."
        self.memory = ".."
        self.net_io = ".."
        self.disk_io = ".."

        # Buttons
        self.stop_button = QPushButton('Stop Server', self)
        self.start_button = QPushButton('Start Server', self)
        self.restart_button = QPushButton('Restart Server', self)
        self.shutdown_button = QPushButton('Shutdown Server', self)
        self.backup_button = QPushButton('Backup', self)

        self.player_count_label = QLabel(self)
        self.pc_info_cpu = QLabel(self)
        self.pc_info_ram_used = QLabel(self)
        self.pc_info_ram_not_used = QLabel(self)
        self.pc_info_ram = QLabel(self)
        self.pc_info_byte_send = QLabel(self)
        self.pc_info_byte_received = QLabel(self)
        # Font settings
        self.command_input.setFont(self.font)
        self.player_count_label.setFont(self.font)
        self.pc_info_cpu.setFont(self.font)
        self.pc_info_ram_used.setFont(self.font)
        self.pc_info_ram_not_used.setFont(self.font)
        self.pc_info_ram.setFont(self.font)
        self.pc_info_byte_send.setFont(self.font)
        self.pc_info_byte_received.setFont(self.font)
        self.stop_button.setFont(self.font)
        self.start_button.setFont(self.font)
        self.restart_button.setFont(self.font)
        self.shutdown_button.setFont(self.font)
        self.backup_button.setFont(self.font)
        self.log_text.setFont(self.font)
        self.player_chat.setFont(self.font)

        # Minecraft Server
        self.server_process = ServerProcess()

        # GUI
        self.init_UI()

        # get Info
        info = threading.Thread(target=self.get_pc_info, daemon=True)
        info.start()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.commands_used_pointer > 0:
                self.commands_used_pointer -= 1
            self.command_input.setText(self.commands_used[self.commands_used_pointer])

        if event.key() == Qt.Key_Down:
            if self.commands_used_pointer < len(self.commands_used) - 1:
                self.commands_used_pointer += 1
            self.command_input.setText(self.commands_used[self.commands_used_pointer])

        if event.key() == Qt.Key_F11:
            if not self.full_screen:
                self.showFullScreen()
                self.full_screen = True
            else:
                self.showNormal()
                self.full_screen = False

    def init_UI(self):

        # GUI hard for 1980x1080
        self.setWindowTitle('Minecraft Server GUI')
        self.setGeometry(100, 100, 1980, 1080)

        # Logs
        self.log_text.setReadOnly(True)
        self.log_text.ensureCursorVisible()
        self.log_text.setGeometry(10, 20, 830, 460)

        # Chat
        self.player_chat.setReadOnly(True)
        self.player_chat.ensureCursorVisible()
        self.player_chat.setGeometry(850, 20, 780, 460)

        # Command
        self.command_input.setGeometry(10, 570, 830, 40)
        self.command_input.returnPressed.connect(self.send_command)

        # Menu
        log_menu = QMenu('Log', self.menuBar())
        chat_menu = QMenu('Chat', self.menuBar())

        self.menuBar().addMenu(log_menu)
        self.menuBar().addMenu(chat_menu)

        clear_log = QAction('Clear', self)
        clear_log.triggered.connect(self.log_text.clear)

        clear_chat = QAction('Clear', self)
        clear_chat.triggered.connect(self.player_chat.clear)

        log_menu.addAction(clear_log)
        chat_menu.addAction(clear_chat)

        init_x_button = 10

        # Start-Button erstellen
        self.start_button.setGeometry(init_x_button + 210 * 0, 500, 200, 50)
        self.start_button.clicked.connect(self.start_server)

        # Stop-Button erstellen
        self.stop_button.setGeometry(init_x_button + 210 * 1, 500, 200, 50)
        self.stop_button.clicked.connect(self.stop_server_slow)

        # Fast-Shutdown-Button erstellen
        self.shutdown_button.setGeometry(init_x_button + 210 * 2, 500, 200, 50)
        self.shutdown_button.clicked.connect(self.stop_server_fast)

        # Restart-Button erstellen
        self.restart_button.setGeometry(init_x_button + 210 * 3, 500, 200, 50)
        self.restart_button.clicked.connect(self.restart_server)

        # Backup-Button erstellen
        self.backup_button.setGeometry(init_x_button + 210 * 4, 500, 200, 50)
        self.backup_button.clicked.connect(self.backup_server)

        # Label für Spieleranzahl erstellen

        self.player_count_label.setGeometry(init_x_button + 210 * 5, 500, 300, 50)
        self.player_count_label.setText("Players: -")

        # Label für Pc info erstellen
        init_y_pc_info = 620
        y_pc_info_jump = 30

        self.pc_info_cpu.setGeometry(init_x_button, init_y_pc_info + y_pc_info_jump * 0, 400, 50)
        self.pc_info_cpu.setText(f"CPU Usage: {self.cpu_percent}%")

        self.pc_info_ram.setGeometry(init_x_button, init_y_pc_info + y_pc_info_jump * 1, 400, 50)
        self.pc_info_ram.setText(f"RAM Usage: {self.memory}%")

        self.pc_info_ram_used.setGeometry(init_x_button, init_y_pc_info + y_pc_info_jump * 2, 400, 50)
        self.pc_info_ram_used.setText(f"Used Memory: {self.memory} MB")

        self.pc_info_ram_not_used.setGeometry(init_x_button, init_y_pc_info + y_pc_info_jump * 3, 400, 50)
        self.pc_info_ram_not_used.setText(f"Available Memory: {self.memory} MB")

        self.pc_info_byte_send.setGeometry(init_x_button, init_y_pc_info + y_pc_info_jump * 4, 400, 50)
        self.pc_info_byte_send.setText(f"Bytes sent: {self.net_io} MB")

        self.pc_info_byte_received.setGeometry(init_x_button, init_y_pc_info + y_pc_info_jump * 5, 400, 50)
        self.pc_info_byte_received.setText(f"Bytes received: {self.net_io} MB")

    def get_pc_info(self):
        while True:
            time.sleep(1)

            self.cpu_percent = psutil.cpu_percent()
            self.memory = psutil.virtual_memory()
            self.net_io = psutil.net_io_counters()
            self.disk_io = psutil.disk_io_counters()

            self.pc_info_cpu.setText(f"CPU Usage: {self.cpu_percent}%")
            self.pc_info_ram_used.setText(f"Used Memory: {self.memory.used / (1024 ** 2):.2f} MB")
            self.pc_info_ram_not_used.setText(f"Available Memory: {self.memory.available / (1024 ** 2):.2f} MB")
            self.pc_info_ram.setText(f"RAM Usage: {self.memory.percent}%")
            self.pc_info_byte_send.setText(f"Bytes sent: {self.net_io.bytes_sent / (1024 ** 2):.2f} MB")
            self.pc_info_byte_received.setText(f"Bytes received: {self.net_io.bytes_recv / (1024 ** 2):.2f} MB")

    def log_update(self, message):

        if self.server_process.player_text(message):
            self.player_chat.appendPlainText(message)
            self.player_chat.viewport().update()
        else:
            if "Timings Reset" in message:
                self.update_flag = True

            self.log_text.appendPlainText(message)
            self.log_text.viewport().update()

        # Update
        if self.update_flag:
            self.server_process.player_count()
            self.player_count_label.setText(f"Players: {self.server_process.player_number}")

    def start_server(self):
        if self.server_process.process is not None and self.server_process.process.poll() is None:
            self.log_update('Server is already running.')
        else:
            self.server_process.on_output = self.log_update
            self.server_process.start()
            self.log_update('Starting server...')

    def stop_server_slow(self):
        if self.server_process.process is None or self.server_process.process.poll() is not None:
            self.log_update('Server is not running.')
        else:
            self.update_flag = False
            self.player_count_label.setText("Players: -")
            stop_warning = threading.Thread(target=self.server_process.stop_slow, daemon=True)
            stop_warning.start()
            self.log_update('Stopping server...')

    def stop_server_fast(self):
        if self.server_process.process is None or self.server_process.process.poll() is not None:
            self.log_update('Server is not running.')
        else:
            self.update_flag = False
            self.player_count_label.setText("Players: -")
            stop = threading.Thread(target=self.server_process.stop_fast, daemon=True)
            stop.start()
            self.log_update('Stopping server...')

    def restart_server(self):
        if self.server_process.process is None or self.server_process.process.poll() is not None:
            self.log_update('Server is not running.')
        else:
            self.update_flag = False
            self.player_count_label.setText("Players: -")
            restart = threading.Thread(target=self.server_process.restart, daemon=True)
            restart.start()
            self.log_update('Restarting server...')

    def backup_server(self):
        if self.server_process.process is None or self.server_process.process.poll() is not None:
            msg = make_backup()
            self.log_update(msg)
        else:
            self.update_flag = False
            self.player_count_label.setText("Players: -")
            self.log_update('Backup server...')
            backup = threading.Thread(target=self.server_process.backup, daemon=True)
            backup.start()
            self.log_update('Restarting server...')

    def send_command(self):
        cmd = self.command_input.text().strip()
        self.server_process.send_command(cmd)
        self.commands_used.append(cmd)
        self.commands_used_pointer = len(self.commands_used)
        self.command_input.clear()


if __name__ == '__main__':
    app = QApplication([])
    main_window = MainWindow()
    main_window.show()
    app.exec_()
