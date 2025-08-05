from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QPlainTextEdit, QLabel, QLineEdit, QGroupBox, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from backup import make_backup
import re
import sys
import time
import psutil
import threading
import subprocess

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
            print(f"Starting server with command: {' '.join(command)}") 

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

    def stop_slow(self, restart=False, reason=None):
        if self.process is not None and self.process.poll() is None:
            try:
                for seconds in [30, 15, 10, 5, 4, 3, 2, 1]:
                    if reason:
                        msg = f"say Server {reason} in {seconds} seconds"
                    else:
                        msg = f"say Server {'restarting' if restart else 'stopping'} in {seconds} seconds"
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
        self.stop_slow(reason='backup starts')
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
        if re.search(r']:\s<[^>]+>', clean_msg):
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

        self.player_count_label = QLabel(self)
        self.pc_info_cpu = QLabel(self)
        self.pc_info_ram_used = QLabel(self)
        self.pc_info_ram_not_used = QLabel(self)
        self.pc_info_ram = QLabel(self)
        self.pc_info_byte_send = QLabel(self)
        self.pc_info_byte_received = QLabel(self)

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
        self.resize(1200, 800)

        font = self.font
        font.setPointSize(12)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        self.player_count_label.setText("0 players online")
        self.player_count_label.setFont(font)

        player_group = QGroupBox("Players")
        player_group.setFont(font)

        player_layout = QVBoxLayout()
        player_layout.addWidget(self.player_count_label)
        player_group.setLayout(player_layout)
        main_layout.addWidget(player_group)

        self.log_text.setFont(font)
        self.player_chat.setFont(font)
        log_chat_layout = QHBoxLayout()
        log_chat_layout.addWidget(self.log_text, 2)
        log_chat_layout.addWidget(self.player_chat, 2)
        main_layout.addLayout(log_chat_layout)

        self.command_input.setFont(font)
        self.command_input.returnPressed.connect(self.send_command)

        main_layout.addWidget(self.command_input)

        button_layout = QHBoxLayout()

        self.start_button = QPushButton('Start Server')
        self.stop_button = QPushButton('Stop Server (Slow)')
        self.shutdown_button = QPushButton('Stop Server (Fast)')
        self.restart_button = QPushButton('Restart Server')
        self.backup_button = QPushButton('Backup')

        for btn in [self.start_button, self.stop_button, self.shutdown_button, self.restart_button, self.backup_button]:
            btn.setFont(font)
            btn.setMinimumHeight(40)
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)

        self.start_button.clicked.connect(self.start_server)
        self.stop_button.clicked.connect(lambda: threading.Thread(target=self.server_process.stop_slow, daemon=True).start())
        self.shutdown_button.clicked.connect(lambda: threading.Thread(target=self.server_process.stop_fast, daemon=True).start())
        self.restart_button.clicked.connect(lambda: threading.Thread(target=self.server_process.restart, daemon=True).start())
        self.backup_button.clicked.connect(lambda: threading.Thread(target=self.server_process.backup, daemon=True).start())

        pc_info_group = QGroupBox("PC Information")
        pc_info_group.setFont(font)

        pc_info_layout = QGridLayout()

        pc_info_layout.addWidget(QLabel("CPU Usage:"), 0, 0)
        pc_info_layout.addWidget(self.pc_info_cpu, 0, 1)

        pc_info_layout.addWidget(QLabel("Total RAM:"), 1, 0)
        pc_info_layout.addWidget(self.pc_info_ram, 1, 1)

        pc_info_layout.addWidget(QLabel("RAM Used:"), 2, 0)
        pc_info_layout.addWidget(self.pc_info_ram_used, 2, 1)

        pc_info_layout.addWidget(QLabel("RAM Free:"), 3, 0)
        pc_info_layout.addWidget(self.pc_info_ram_not_used, 3, 1)

        pc_info_layout.addWidget(QLabel("Network Sent:"), 4, 0)
        pc_info_layout.addWidget(self.pc_info_byte_send, 4, 1)

        pc_info_layout.addWidget(QLabel("Network Received:"), 5, 0)
        pc_info_layout.addWidget(self.pc_info_byte_received, 5, 1)

        for i in range(6):
            for j in range(2):
                widget = pc_info_layout.itemAtPosition(i, j).widget()
                widget.setFont(font)

        pc_info_group.setLayout(pc_info_layout)
        main_layout.addWidget(pc_info_group)



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
            self.player_chat.appendPlainText(clean_message)
            self.player_chat.viewport().update()
        else:
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
        self.pc_info_cpu.setText(f"{info['cpu_percent']}%")
        self.pc_info_ram.setText(f"{info['memory_percent']}%")
        self.pc_info_ram_used.setText(f"{info['memory_used']} MB")
        self.pc_info_ram_not_used.setText(f"{info['memory_available']} MB")
        self.pc_info_byte_send.setText(f"{info['mb_sent']} MB")
        self.pc_info_byte_received.setText(f"{info['mb_recv']} MB")

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
