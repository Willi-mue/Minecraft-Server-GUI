from PyQt5.QtCore import Qt, pyqtSignal, QObject
from backup import make_backup
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QPlainTextEdit, QLabel, QAction, QMenu, QLineEdit
import subprocess
import threading
import time
import psutil
import sys
import re

MIN_RAM = '-Xms1G'
MAX_RAM = '-Xmx3G'
SERVER_PATH = "server.jar"

def remove_ansi_codes(text):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class ServerProcess(QObject):
    output_signal = pyqtSignal(str)
    player_count_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.process = None
        self.stdout_thread = None
        self.player_number = 0
        self.start_time = time.time()
        self.player_names = []

    def start(self):
        if self.process is None or self.process.poll() is not None:
            command = ['java', MIN_RAM, MAX_RAM, '-jar', SERVER_PATH, '-nogui']
            print(f"Starting server with command: {' '.join(command)}")  # debug

            try:
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd='Server',
                    bufsize=1,
                    universal_newlines=True
                )
            except Exception as e:
                self.output_signal.emit(f"Failed to start server: {e}")
                return
            
            self.running = True

            self.stdout_thread = threading.Thread(target=self._output_reader, daemon=True)
            self.stdout_thread.start()
            self.output_signal.emit("Server started.")

    def _schedule_list_check(self):
        if self.running:
            self.send_command("list")
            threading.Timer(10, self._schedule_list_check).start()

    def stop_slow(self, restart=False):
        if self.process is not None and self.process.poll() is None:
            try:
                for seconds in [30, 15, 10, 5, 4, 3, 2, 1]:
                    msg = f"say Server {'startet neu' if restart else 'stoppt'} in {seconds} Sekunden"
                    self.process.stdin.write(f'{msg}\n')
                    self.process.stdin.flush()
                    if seconds > 10:
                        time.sleep(15 if seconds == 30 else 5)
                    else:
                        time.sleep(1)

                self.process.stdin.write('stop\n')
                self.process.stdin.flush()
                self.process.wait()
                self.player_number = 0
                status_msg = "Server stopped for restart." if restart else "Server stopped slowly."
                self.output_signal.emit(status_msg)
                self.running = False
            except Exception as e:
                self.output_signal.emit(f"Error during slow stop: {e}")

    def stop_fast(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.stdin.write('stop\n')
                self.process.stdin.flush()
                self.process.wait()
                self.player_number = 0
                self.output_signal.emit("Server stopped fast.")
                self.running = False
            except Exception as e:
                self.output_signal.emit(f"Error during fast stop: {e}")

    def restart(self):
        self.output_signal.emit('Server-Restart started ..')
        self.stop_slow(restart=True)
        self.start()

    def backup(self):
        self.output_signal.emit('Server-Backup started ..')
        self.stop_slow()
        try:
            msg = make_backup()
            self.output_signal.emit(msg)
        except Exception as e:
            self.output_signal.emit(f"Backup failed: {e}")
        self.start()

    def _output_reader(self):
        try:
            while True:
                if self.process.stdout is None:
                    self.output_signal.emit("No stdout available.")
                    break
                output = self.process.stdout.readline()
                if output == '' and self.process.poll() is not None:
                    self.output_signal.emit("Process ended.")
                    break
                if output:
                    clean_output = remove_ansi_codes(output.strip())
                    self.output_signal.emit(clean_output)
                    self.on_output(clean_output)
        except Exception as e:
            self.output_signal.emit(f"Error reading server output: {e}")

    def on_output(self, output):

        if "joined the game" in output:
            self.player_number += 1
            self.player_count_signal.emit(self.player_number)

        elif "left the game" in output:
            self.player_number = max(0, self.player_number - 1)
            self.player_count_signal.emit(self.player_number)

        if hasattr(self, 'on_log_output') and callable(self.on_log_output):
            self.on_log_output(output)


    def player_text(self, msg):
        clean_msg = remove_ansi_codes(msg)
        if re.search(r']:\s<[^>]+>', clean_msg):  # Chatnachrichten
            return True
        if "joined the game" in clean_msg or "left the game" in clean_msg:
            return True
        return False


    def send_command(self, cmd):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.stdin.write(f'{cmd}\n')
                self.process.stdin.flush()
            except Exception as e:
                self.output_signal.emit(f"Failed to send command: {e}")


class MainWindow(QMainWindow):
    update_log_signal = pyqtSignal(str)
    update_pc_info_signal = pyqtSignal(dict)

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
        self.server_process.output_signal.connect(self.log_update)
        self.server_process.player_count_signal.connect(self.update_player_count)

        # GUI
        self.init_UI()

        # Signals for thread-safe updates
        self.update_log_signal.connect(self.log_update)
        self.update_pc_info_signal.connect(self.update_pc_info_labels)

        # get Info
        info = threading.Thread(target=self.get_pc_info, daemon=True)
        info.start()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.commands_used and self.commands_used_pointer > 0:
                self.commands_used_pointer -= 1
                self.command_input.setText(self.commands_used[self.commands_used_pointer])

        elif event.key() == Qt.Key_Down:
            if self.commands_used and self.commands_used_pointer < len(self.commands_used) - 1:
                self.commands_used_pointer += 1
                self.command_input.setText(self.commands_used[self.commands_used_pointer])
            else:
                self.commands_used_pointer = len(self.commands_used)
                self.command_input.clear()

        elif event.key() == Qt.Key_F11:
            if not self.full_screen:
                self.showFullScreen()
                self.full_screen = True
            else:
                self.showNormal()
                self.full_screen = False

    def init_UI(self):
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

        # Command input
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

        # Buttons
        self.start_button.setGeometry(init_x_button + 210 * 0, 500, 200, 50)
        self.start_button.clicked.connect(self.start_server)

        self.stop_button.setGeometry(init_x_button + 210 * 1, 500, 200, 50)
        self.stop_button.clicked.connect(self.stop_server_slow)

        self.shutdown_button.setGeometry(init_x_button + 210 * 2, 500, 200, 50)
        self.shutdown_button.clicked.connect(self.stop_server_fast)

        self.restart_button.setGeometry(init_x_button + 210 * 3, 500, 200, 50)
        self.restart_button.clicked.connect(self.restart_server)

        self.backup_button.setGeometry(init_x_button + 210 * 4, 500, 200, 50)
        self.backup_button.clicked.connect(self.backup_server)

        self.player_count_label.setGeometry(init_x_button + 210 * 5, 500, 300, 50)
        self.player_count_label.setText("Players: -")

        # PC Info Labels
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
        self.pc_info_byte_send.setText(f"Bytes Sent: {self.net_io}")

        self.pc_info_byte_received.setGeometry(init_x_button, init_y_pc_info + y_pc_info_jump * 5, 400, 50)
        self.pc_info_byte_received.setText(f"Bytes Received: {self.net_io}")

    def start_server(self):
        self.server_process.start()

    def stop_server_slow(self):
        threading.Thread(target=self.server_process.stop_slow, daemon=True).start()

    def stop_server_fast(self):
        threading.Thread(target=self.server_process.stop_fast, daemon=True).start()

    def restart_server(self):
        threading.Thread(target=self.server_process.restart, daemon=True).start()

    def backup_server(self):
        threading.Thread(target=self.server_process.backup, daemon=True).start()

    def log_update(self, message):
        clean_message = remove_ansi_codes(message)

        if self.server_process.player_text(clean_message):
            # Nur in den Chat (rechter Bereich)
            self.player_chat.appendPlainText(clean_message)
            self.player_chat.viewport().update()
        else:
            # Nur ins Log (linker Bereich)
            self.log_text.appendPlainText(clean_message)
            self.log_text.viewport().update()

    def get_pc_info(self):
        while True:
            time.sleep(1)
            try:
                cpu = psutil.cpu_percent()
                mem = psutil.virtual_memory()
                net_io = psutil.net_io_counters()
                disk_io = psutil.disk_io_counters()

                info = {
                    'cpu_percent': cpu,
                    'memory_percent': mem.percent,
                    'memory_used': mem.used // (1024 * 1024),
                    'memory_available': mem.available // (1024 * 1024),
                    'mb_sent': round(net_io.bytes_sent / (1024 * 1024), 2),
                    'mb_recv': round(net_io.bytes_recv / (1024 * 1024), 2),
                }

                self.update_pc_info_signal.emit(info)
            except Exception as e:
                self.update_log_signal.emit(f"Error getting PC info: {e}")

    def update_pc_info_labels(self, info):
        self.pc_info_cpu.setText(f"CPU Usage: {info['cpu_percent']}%")
        self.pc_info_ram.setText(f"RAM Usage: {info['memory_percent']}%")
        self.pc_info_ram_used.setText(f"Used Memory: {info['memory_used']} MB")
        self.pc_info_ram_not_used.setText(f"Available Memory: {info['memory_available']} MB")
        self.pc_info_byte_send.setText(f"Bytes Sent: {info['mb_sent']} MB")
        self.pc_info_byte_received.setText(f"Bytes Received: {info['mb_recv']} MB")

    def send_command(self):
        cmd = self.command_input.text().strip()
        if cmd == '':
            return

        self.server_process.send_command(cmd)
        self.commands_used.append(cmd)
        self.commands_used_pointer = len(self.commands_used)
        self.command_input.clear()

    def closeEvent(self, event):
        if self.server_process.process is not None and self.server_process.process.poll() is None:
            self.server_process.stop_fast()
        event.accept()

    def update_player_count(self, count):
        self.player_count_label.setText(f"Players: {count}")



def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
