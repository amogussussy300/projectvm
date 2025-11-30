
from PyQt6.QtCore import QThread, pyqtSignal
import re
import math

class CalculationWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, task='fetch', cpu_name=None, gpu_name=None, api_base="http://localhost:8000"):
        super().__init__()
        self.task = task
        self.cpu_name = cpu_name
        self.gpu_name = gpu_name
        self.api_base = api_base

    @staticmethod
    def _parse_watt(s: str) -> int:
        if not s:
            return 0
        m = re.search(r"(\d+)", str(s))
        return int(m.group(1)) if m else 0

    def run(self):
        import requests
        try:
            if self.task == 'fetch':
                cpus_resp = requests.get(f"{self.api_base}/cpus/", timeout=5)
                gpus_resp = requests.get(f"{self.api_base}/gpus/", timeout=5)
                psus_resp = requests.get(f"{self.api_base}/psus/", timeout=5)

                cpus = cpus_resp.json().get("data", [])
                gpus = gpus_resp.json().get("data", [])
                psus = psus_resp.json().get("data", [])

                self.finished.emit({"cpus": cpus, "gpus": gpus, "psus": psus})
                return

            if self.task == 'calc':
                cpus_resp = requests.get(f"{self.api_base}/cpus/", timeout=5)
                gpus_resp = requests.get(f"{self.api_base}/gpus/", timeout=5)
                psus_resp = requests.get(f"{self.api_base}/psus/", timeout=5)

                cpus = cpus_resp.json().get("data", [])
                gpus = gpus_resp.json().get("data", [])
                psus = psus_resp.json().get("data", [])

                def find_entry(entries, name):
                    if not name:
                        return None
                    for e in entries:
                        if e.get("name", "") == name:
                            return e
                    for e in entries:
                        if name.lower() in e.get("name", "").lower():
                            return e
                    return None

                cpu_entry = find_entry(cpus, self.cpu_name)
                gpu_entry = find_entry(gpus, self.gpu_name)

                cpu_w = self._parse_watt(cpu_entry.get("consumption", "")) if cpu_entry else 0
                gpu_w = self._parse_watt(gpu_entry.get("consumption", "")) if gpu_entry else 0

                overhead = 200
                raw_total = cpu_w + gpu_w + overhead
                required = math.ceil(raw_total * 1.20)

                psu_filtered = []
                for p in psus:
                    try:
                        watt = int(str(p.get("wattage", "")).strip())
                    except Exception:
                        watt = self._parse_watt(p.get("wattage", ""))
                    if watt >= required:
                        psu_filtered.append({"name": p.get("name", ""), "wattage": watt})

                psu_filtered.sort(key=lambda x: x["wattage"])
                top5 = psu_filtered[:5]

                self.finished.emit({
                    "required": required,
                    "cpu_w": cpu_w,
                    "gpu_w": gpu_w,
                    "overhead": overhead,
                    "psus": top5
                })
                return

            self.finished.emit({"error": f"Unknown task: {self.task}"})
        except Exception as e:
            self.finished.emit({"error": str(e)})
