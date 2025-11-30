from PyQt6.QtCore import QThread, pyqtSignal


class CalculationWorker(QThread):
    """
    будет изменен
    """
    finished = pyqtSignal(dict)

    def __init__(self, cpu_id, gpu_id, ram_id, mem_id):
        super().__init__()
        self.cpu_id = cpu_id
        self.gpu_id = gpu_id
        self.ram_id = ram_id
        self.mem_id = mem_id

    def run(self):
        result = dict() # не используется пока что
        self.finished.emit(result)