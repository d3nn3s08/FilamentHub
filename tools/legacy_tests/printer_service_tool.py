class PrinterService:
    def __init__(self):
        self.printers = {}

    def register(self, name, model, ip, mqtt_version):
        self.printers[name] = {
            "model": model,
            "ip": ip,
            "mqtt_version": mqtt_version,
            "data": None
        }

    def update_printer(self, name, data):
        self.printers[name]["data"] = data
        print(f"[SERVICE] {name} → State: {data.state}, Progress: {data.progress}")

    def get(self, name):
        return self.printers[name]["data"]

    def get_all(self):
        return {n: d["data"] for n, d in self.printers.items()}
