import sys
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QFileDialog, QMessageBox)
from PyQt6.QtCore import pyqtSignal
from database import Database

class ConfigWindow(QWidget):
    configuration_saved = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.init_ui()
        self.check_initial_config()

    def init_ui(self):
        self.setWindowTitle('Configuration')
        self.layout = QVBoxLayout()

        self.label = QLabel('Select the executable to monitor:')
        self.layout.addWidget(self.label)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.layout.addWidget(self.path_edit)

        self.browse_button = QPushButton('Browse...')
        self.browse_button.clicked.connect(self.browse_executable)
        self.layout.addWidget(self.browse_button)

        self.save_button = QPushButton('Save')
        self.save_button.clicked.connect(self.save_configuration)
        self.layout.addWidget(self.save_button)

        # Add a Reset button for testing
        self.reset_button = QPushButton('Reset (Allow Changing Executable)')
        self.reset_button.clicked.connect(self.reset_configuration)
        self.layout.addWidget(self.reset_button)

        self.setLayout(self.layout)

    def check_initial_config(self):
        executable_path = self.db.get_config('executable_path')
        if executable_path:
            self.path_edit.setText(executable_path)
            self.browse_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.label.setText('Monitored Executable (cannot be changed):')
            self.reset_button.setEnabled(True)
        else:
            self.browse_button.setEnabled(True)
            self.save_button.setEnabled(True)
            self.reset_button.setEnabled(False)

    def reset_configuration(self):
        # Remove the executable_path from config for testing
        self.db.set_config('executable_path', '')
        self.path_edit.clear()
        self.browse_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.reset_button.setEnabled(False)
        self.label.setText('Select the executable to monitor:')

    def browse_executable(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Executable", "", "Executable Files (*.exe)")
        if file_path:
            self.path_edit.setText(file_path)

    def save_configuration(self):
        executable_path = self.path_edit.text()
        if not executable_path:
            QMessageBox.warning(self, 'Warning', 'Please select an executable file.')
            return
        
        self.db.set_config('executable_path', executable_path)
        QMessageBox.information(self, 'Success', 'Configuration saved. The application will now monitor this executable.')
        
        self.configuration_saved.emit(executable_path)
        self.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    config_win = ConfigWindow()
    config_win.show()
    sys.exit(app.exec())
