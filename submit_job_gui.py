import sys
import os
import types
from io import StringIO

# 1. Qt Compatibility Layer
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtWidgets import QFileDialog, QMessageBox
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore, QtGui
        from PySide2.QtWidgets import QFileDialog, QMessageBox
    except ImportError:
        print("Error: neither PySide6 nor PySide2 is installed.")
        print("Please install one via: pip install PySide6 (or PySide2)")
        sys.exit(1)

# Import submission logic
# Ensure we can find submit_job.py relative to this script
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    import submit_job
except ImportError:
    print(f"Error: Could not import submit_job module from {current_dir}")

# Global variable to hold the window instance (prevents garbage collection)
_submitter_window_instance = None

class SubmissionWorker(QtCore.QThread):
    """
    Worker thread to handle the deadline submission process without freezing the UI.
    """
    finished_signal = QtCore.Signal(str) # Output log
    error_signal = QtCore.Signal(str)    # Error message
    
    def __init__(self, args):
        super().__init__()
        self.args = args

    def run(self):
        # Capture stdout
        old_stdout = sys.stdout
        redirected_output = StringIO()
        sys.stdout = redirected_output

        try:
            # Execute submission
            submit_job.submit_to_deadline(self.args)
            
            # Get output and emit
            output = redirected_output.getvalue()
            self.finished_signal.emit(output)
        except Exception as e:
            # Emit error
            self.error_signal.emit(str(e))
        finally:
            # Restore stdout
            sys.stdout = old_stdout

def show_ui(parent=None):
    """
    Entry point for DCC applications (Maya, Houdini, Nuke).
    Usage:
        import submit_job_gui
        submit_job_gui.show_ui()
    """
    global _submitter_window_instance
    
    # Close existing window if open
    if _submitter_window_instance:
        try:
            _submitter_window_instance.close()
            _submitter_window_instance.deleteLater()
        except:
            pass
        _submitter_window_instance = None

    # Create new window
    _submitter_window_instance = SubmitJobWindow(parent)
    _submitter_window_instance.show()
    return _submitter_window_instance

class SubmitJobWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenCV Distortion Deadline Submitter")
        self.resize(600, 500)
        self.init_ui()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(main_layout)

        # Form Layout for Inputs
        form_layout = QtWidgets.QFormLayout()
        
        # 1. Job Name
        self.job_name_edit = QtWidgets.QLineEdit("OpenCV Distortion Task")
        form_layout.addRow("Job Name:", self.job_name_edit)

        # 1.5 Deadline Command Path
        self.deadline_layout = QtWidgets.QHBoxLayout()
        self.deadline_edit = QtWidgets.QLineEdit()
        self.deadline_btn = QtWidgets.QPushButton("Browse")
        self.deadline_btn.clicked.connect(self.browse_deadline)
        self.deadline_layout.addWidget(self.deadline_edit)
        self.deadline_layout.addWidget(self.deadline_btn)
        form_layout.addRow("Deadline Command:", self.deadline_layout)
        
        # Try to auto-detect
        detected_cmd = submit_job.get_deadline_command()
        if detected_cmd:
            self.deadline_edit.setText(detected_cmd)

        # 2. Input Pattern
        self.input_layout = QtWidgets.QHBoxLayout()
        self.input_edit = QtWidgets.QLineEdit()
        self.input_edit.setPlaceholderText("path/to/image.####.exr")
        self.input_btn = QtWidgets.QPushButton("Browse")
        self.input_btn.clicked.connect(self.browse_input)
        self.input_layout.addWidget(self.input_edit)
        self.input_layout.addWidget(self.input_btn)
        form_layout.addRow("Input Pattern:", self.input_layout)

        # 3. Output Directory
        self.output_layout = QtWidgets.QHBoxLayout()
        self.output_edit = QtWidgets.QLineEdit()
        self.output_btn = QtWidgets.QPushButton("Browse")
        self.output_btn.clicked.connect(self.browse_output)
        self.output_layout.addWidget(self.output_edit)
        self.output_layout.addWidget(self.output_btn)
        form_layout.addRow("Output Dir:", self.output_layout)

        # 4. JSON Path
        self.json_layout = QtWidgets.QHBoxLayout()
        self.json_edit = QtWidgets.QLineEdit()
        self.json_btn = QtWidgets.QPushButton("Browse")
        self.json_btn.clicked.connect(self.browse_json)
        self.json_layout.addWidget(self.json_edit)
        self.json_layout.addWidget(self.json_btn)
        form_layout.addRow("JSON Path:", self.json_layout)

        # 5. Frame Range
        self.frames_edit = QtWidgets.QLineEdit()
        self.frames_edit.setPlaceholderText("e.g. 1001-1100")
        form_layout.addRow("Frame Range:", self.frames_edit)

        # 6. Chunk Size
        self.chunk_spin = QtWidgets.QSpinBox()
        self.chunk_spin.setRange(1, 1000)
        self.chunk_spin.setValue(10)
        form_layout.addRow("Chunk Size:", self.chunk_spin)

        # 7. Priority
        self.priority_spin = QtWidgets.QSpinBox()
        self.priority_spin.setRange(0, 100)
        self.priority_spin.setValue(50)
        form_layout.addRow("Priority:", self.priority_spin)

        # 8. Comment
        self.comment_edit = QtWidgets.QLineEdit("Submitted via GUI")
        form_layout.addRow("Comment:", self.comment_edit)

        # 9. Mode (Distort/Undistort)
        self.mode_group = QtWidgets.QGroupBox("Mode")
        self.mode_layout = QtWidgets.QHBoxLayout()
        self.undistort_radio = QtWidgets.QRadioButton("Undistort (Restore)")
        self.distort_radio = QtWidgets.QRadioButton("Distort (Reverse)")
        self.undistort_radio.setChecked(True)
        self.mode_layout.addWidget(self.undistort_radio)
        self.mode_layout.addWidget(self.distort_radio)
        self.mode_group.setLayout(self.mode_layout)
        form_layout.addRow(self.mode_group)

        main_layout.addLayout(form_layout)

        # Submit Button
        self.submit_btn = QtWidgets.QPushButton("Submit to Deadline")
        self.submit_btn.setMinimumHeight(40)
        self.submit_btn.clicked.connect(self.submit_job)
        main_layout.addWidget(self.submit_btn)

        # Console Output Log
        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)
        main_layout.addWidget(self.log_output)


    def browse_deadline(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select deadlinecommand executable", "", "Executables (*.exe);;All Files (*)")
        if file_path:
            self.deadline_edit.setText(file_path)

    def browse_input(self):
        # Allow selecting a file, user might need to edit it to add #### later if selecting a single frame
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Input File (select one frame)", "", "Images (*.exr *.jpg *.png *.tif);;All Files (*)")
        if file_path:
            # Try to smart-detect sequence
            # If user selected image.1001.exr, suggest image.####.exr
            import re
            match = re.search(r'(\d+)(\.[a-zA-Z]+)$', file_path)
            if match:
                frame_num = match.group(1)
                ext = match.group(2)
                padding = len(frame_num)
                padding_char = "#" * padding
                new_path = file_path[:match.start(1)] + padding_char + ext
                self.input_edit.setText(new_path)
            else:
                self.input_edit.setText(file_path)

    def browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_edit.setText(dir_path)

    def browse_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select JSON Calibration File", "", "JSON (*.json);;All Files (*)")
        if file_path:
            self.json_edit.setText(file_path)

    def log(self, message):
        self.log_output.append(message)
        # Scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def submit_job(self):
        # Validate Inputs
        input_pattern = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip()
        json_path = self.json_edit.text().strip()
        frames = self.frames_edit.text().strip()
        
        if not all([input_pattern, output_dir, json_path, frames]):
            QMessageBox.warning(self, "Validation Error", "Please fill in all required fields (Input, Output, JSON, Frames).")
            return

        self.log("Preparing submission...")
        self.submit_btn.setEnabled(False) # Prevent double submission

        # Construct Args object
        args = types.SimpleNamespace()
        args.input_pattern = input_pattern
        args.output_dir = output_dir
        args.json_path = json_path
        args.frames = frames
        args.chunk_size = self.chunk_spin.value()
        args.job_name = self.job_name_edit.text()
        args.comment = self.comment_edit.text()
        args.priority = self.priority_spin.value()
        args.undistort = self.undistort_radio.isChecked()
        args.deadline_command = self.deadline_edit.text().strip()

        # Start Thread
        self.worker = SubmissionWorker(args)
        self.worker.finished_signal.connect(self.on_submission_finished)
        self.worker.error_signal.connect(self.on_submission_error)
        self.worker.start()

    def on_submission_finished(self, output):
        self.log(output)
        self.submit_btn.setEnabled(True)
        if "Job Info created at" in output:
            QMessageBox.information(self, "Success", "Job submitted successfully! Check log for details.")
        else:
             QMessageBox.warning(self, "Warning", "Job submission finished but check logs for confirmation.")

    def on_submission_error(self, error_msg):
        self.log(f"Error: {error_msg}")
        self.submit_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_msg}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    show_ui()
    sys.exit(app.exec_())