from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

try:
    import serial.tools.list_ports
except ImportError:
    serial = None

from .protocol import DIRECTION_VALUES, TeleshakeController, Transaction, format_hex


class TeleshakeSimpleControl:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Orbital Shaking Station")
        self.root.geometry("310x430")
        self.root.resizable(False, False)

        self.controller: TeleshakeController | None = None
        self.is_running = False
        self.reply_lines: list[str] = []

        self.port_var = tk.StringVar(value="COM4")
        self.rpm_var = tk.StringVar(value="100")
        self.direction_var = tk.StringVar(value="NWSE")
        self.status_var = tk.StringVar(value="Disconnected")

        self._build_ui()
        self._refresh_ports()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        conn = ttk.LabelFrame(main, text="Connection", padding=8)
        conn.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(conn, text="Port").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.port_combo = ttk.Combobox(conn, textvariable=self.port_var, width=10)
        self.port_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(conn, text="Refresh", command=self._refresh_ports).grid(
            row=0, column=2, sticky="w", padx=4, pady=4
        )

        self.connect_button = ttk.Button(conn, text="Connect", command=self._toggle_connection)
        self.connect_button.grid(row=1, column=0, columnspan=3, sticky="ew", padx=4, pady=(6, 4))

        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(0, 8))

        station = ttk.Frame(main)
        station.pack(fill=tk.X)

        rpm_box = ttk.LabelFrame(station, text="RPM", padding=10)
        rpm_box.pack(fill=tk.X, pady=(0, 10))
        ttk.Entry(rpm_box, textvariable=self.rpm_var, width=8).pack(side=tk.LEFT)
        ttk.Label(rpm_box, text="(100 - 2000 RPM)").pack(side=tk.LEFT, padx=(10, 0))

        direction_box = ttk.LabelFrame(station, text="Stir direction", padding=10)
        direction_box.pack(fill=tk.X, pady=(0, 10))
        ttk.Combobox(
            direction_box,
            textvariable=self.direction_var,
            values=list(DIRECTION_VALUES.keys()),
            width=10,
            state="readonly",
        ).pack(anchor="w")
        ttk.Label(
            direction_box,
            text="*Note: Diagonal movements generate the\nmost motion.",
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(10, 0))

        self.start_stop_button = ttk.Button(station, text="Start", command=self._toggle_shaker)
        self.start_stop_button.pack(fill=tk.X, ipady=8, pady=(0, 12))

        ttk.Button(station, text="Emergency Stop", command=self._stop_shaker).pack(
            fill=tk.X, ipady=4, pady=(0, 12)
        )

        log_box = ttk.LabelFrame(main, text="Command log", padding=8)
        log_box.pack(fill=tk.BOTH, expand=True)
        self.reply_log = tk.Text(log_box, height=5, width=34, wrap=tk.WORD)
        self.reply_log.pack(fill=tk.BOTH, expand=True)
        self.reply_log.configure(state=tk.DISABLED)

    def _refresh_ports(self) -> None:
        if serial is None:
            self.port_combo["values"] = ["COM4"]
            self.status_var.set("Install pyserial first: pip install pyserial")
            return

        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports or ["COM4"]
        if self.port_var.get() not in ports and ports:
            self.port_var.set(ports[0])

    def _toggle_connection(self) -> None:
        if self.controller and self.controller.is_connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        try:
            self.controller = TeleshakeController(port=self.port_var.get().strip())
            self.controller.connect()
        except Exception as exc:
            self.status_var.set("Connection failed")
            messagebox.showerror("Connection failed", str(exc))
            return

        self.status_var.set(f"Connected to {self.port_var.get()} at 9600 8N1")
        self.connect_button.configure(text="Disconnect")

    def _disconnect(self) -> None:
        if self.is_running:
            self._stop_shaker()
        if self.controller:
            self.controller.disconnect()
        self.controller = None
        self.is_running = False
        self.start_stop_button.configure(text="Start")
        self.connect_button.configure(text="Connect")
        self.status_var.set("Disconnected")

    def _toggle_shaker(self) -> None:
        if self.is_running:
            self._stop_shaker()
        else:
            self._start_shaker()

    def _start_shaker(self) -> None:
        if not self._ensure_connected():
            return

        try:
            rpm = int(self.rpm_var.get().strip())
        except ValueError:
            messagebox.showwarning("Invalid RPM", "RPM must be a whole number.")
            return

        direction = self.direction_var.get()
        self._clear_log()
        self.status_var.set("Starting...")

        try:
            transactions = self.controller.start(rpm=rpm, direction=direction)
        except Exception as exc:
            self.status_var.set("Start failed")
            messagebox.showerror("Start failed", str(exc))
            return

        for transaction in transactions:
            self._append_transaction(transaction)

        self.is_running = True
        self.start_stop_button.configure(text="Stop")
        self.status_var.set(f"Running at {rpm} RPM, {direction}")

    def _stop_shaker(self) -> None:
        if not self._ensure_connected():
            return

        try:
            transaction = self.controller.stop()
        except Exception as exc:
            self.status_var.set("Stop failed")
            messagebox.showerror("Stop failed", str(exc))
            return

        self._append_transaction(transaction)
        self.is_running = False
        self.start_stop_button.configure(text="Start")
        self.status_var.set("Stopped")

    def _ensure_connected(self) -> bool:
        if self.controller and self.controller.is_connected:
            return True
        messagebox.showwarning("Not connected", "Connect to COM4 first.")
        return False

    def _clear_log(self) -> None:
        self.reply_lines.clear()
        self.reply_log.configure(state=tk.NORMAL)
        self.reply_log.delete("1.0", tk.END)
        self.reply_log.configure(state=tk.DISABLED)

    def _append_transaction(self, transaction: Transaction) -> None:
        self._append_text(
            f"{transaction.label}: TX {format_hex(transaction.tx)} | RX {format_hex(transaction.rx)}"
        )

    def _append_text(self, text: str) -> None:
        self.reply_lines.append(text)
        self.reply_lines = self.reply_lines[-8:]
        self.reply_log.configure(state=tk.NORMAL)
        self.reply_log.delete("1.0", tk.END)
        self.reply_log.insert(tk.END, "\n".join(self.reply_lines))
        self.reply_log.see(tk.END)
        self.reply_log.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        self._disconnect()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    TeleshakeSimpleControl(root)
    root.mainloop()
