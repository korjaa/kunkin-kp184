import csv
import time
import datetime
import logging
import pathlib
import threading
from typing import Optional

import serial

logger = logging.getLogger(__name__)

class ChecksumError(Exception):
    pass

class Kp184:
    MODES = ["CV", "CC", "CR", "CW"]

    def __init__(self, port: str):
        self.port = port
        self.serial = None
        self.serial_lock = threading.Lock()

        self.set_output_on = lambda v: self._modbus_write(0x010e, int(v))  # True / False
        self.is_output_on = lambda: self._modbus_read(0x010e) == 1

        self.set_mode = lambda v: self._modbus_write(0x0110, self.MODES.index(v))
        self.get_mode = lambda: self.MODES[self._modbus_read(0x0110)]

        self.set_cv_V = lambda v: self._modbus_write(0x0112, int(v * 1e3))
        self.get_cv_V = lambda: self._modbus_read(0x0112) / 1e3

        self.set_cc_A = lambda v: self._modbus_write(0x0116, int(v * 1e3))
        self.get_cc_A = lambda: self._modbus_read(0x0116) / 1e3

        self.set_cr_ohm = lambda v: self._modbus_write(0x011A, int(v))
        self.get_cr_ohm = lambda: self._modbus_read(0x011A)

        self.set_cw_W = lambda v: self._modbus_write(0x011E, int(v * 1e1))
        self.get_cw_W = lambda: self._modbus_read(0x011E) / 1e1

        self.measure_voltage = lambda: self._modbus_read(0x0122) / 1e3
        self.measure_current = lambda: self._modbus_read(0x0126) / 1e3

    def measure_voltage_and_current(self) -> dict:
        # TODO: Would be twice as fast if 0x0300 "read voltage and current" worked
        with self.serial_lock:
            result = {
                "Voltage": self._modbus_read_unsafe(0x0122) / 1e3,
                "Current": self._modbus_read_unsafe(0x0126) / 1e3
            }
        return result

    def __enter__(self):
        self.serial = serial.Serial(
            port=self.port, baudrate=19200, parity="N", stopbits=1, timeout=0.2)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.set_output_on(False)
        self.serial.close()

    def background_monitor(self, log_file: pathlib.Path, interval_s: float):
        return BackgroundMonitor(device=self, log_file=log_file, interval_s=interval_s)

    @staticmethod
    def _crc(byts):
        result = 0xFFFF
        for byt in byts:
            result ^= byt
            for i in range(8):
                even = result & 1
                result >>= 1
                result ^= 0xA001 if even else 0
        return result.to_bytes(length=2, byteorder="little")

    def _raise_checksum(self, response):
        received = response[-2:]
        expected = self._crc(response[:-2])
        if received != expected:
            raise ChecksumError

    def _modbus_read(self, *args, **kwargs):
        with self.serial_lock:
            return self._modbus_read_unsafe(*args, **kwargs)

    def _modbus_read_unsafe(self, address: int) -> int:
        # Build command
        msg = b"\x01\x03"  # Device + Read op
        msg += address.to_bytes(length=2, byteorder="big")
        msg += b"\x00\x04"  # Read length
        msg += self._crc(msg)
        msg_hex = msg.hex()

        # Send command
        logger.debug(f"Read request *0x{address:04x} -> {msg.hex()}")
        self.serial.write(msg)

        # Read response
        response = self.serial.read(9)
        response_hex = response.hex()
        logger.debug(f"Response <- {response.hex()}")
        self._raise_checksum(response)

        # Extract payload
        payload_length = response[2]
        payload = response[3:3+payload_length]
        if address == 0x0110:
            logger.warning("Applying 0x0110 payload cut workaround.")
            payload = payload[1:]
        result = int.from_bytes(payload, byteorder="big")
        return result

    def _modbus_write(self, *args, **kwargs):
        with self.serial_lock:
            return self._modbus_write_unsafe(*args, **kwargs)

    def _modbus_write_unsafe(self, address: int, value: int) -> None:
        # Build command
        msg = b"\x01\x06"  # Device + Write op
        msg += address.to_bytes(length=2, byteorder="big")
        msg += b"\x00\x01\x04"  # Something + Write payload length
        msg += value.to_bytes(length=4, byteorder="big")
        msg += self._crc(msg)

        # Send command
        logger.debug(f"Writing *0x{address:04x}=0x{value:02x} -> {msg.hex()}")
        self.serial.write(msg)

        # Readback command (not sure of the exact format)
        readback = self.serial.read(8)
        self._raise_checksum(readback)

        readback_addr = int.from_bytes(readback[2:4], byteorder="big")
        if readback_addr != address:
            raise ChecksumError

        readback_value = int.from_bytes(readback[4:6], byteorder="big")
        if readback_value != (value & 0xFFFF):
            raise ChecksumError

class BackgroundMonitor:
        def __init__(self, device: Kp184, interval_s: float, log_file: Optional[pathlib.Path] = None):
            self.interval_s = interval_s
            self.time_next = None
            self.log_file = log_file
            self.device = device
            self.alive = False
            self.index = None
            self.timestamp = None
            self.voltage = None
            self.current = None
            self.tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            self.worker_start = None
            self.log = None

        def _interwaller(self):
            self.index += 1
            next_sample_time = self.worker_start + self.index * self.interval_s
            sleep_to_next = next_sample_time - time.time()
            if sleep_to_next < 0.0:
                logger.warning(f"BackgroundTracer cannot keep up with {self.interval_s=} ({sleep_to_next=} s)")
            else:
                time.sleep(sleep_to_next)

        def _refresh(self):
            self.voltage, self.current = \
                    self.device.measure_voltage_and_current().values()
            self.timestamp = datetime.datetime.now(tz=self.tz).isoformat()

        def _worker(self):
            while self.alive:
                self._refresh()

                if self.log is not None:
                    self.log.writerow([self.timestamp, self.voltage, self.current])

                self._interwaller()

        def __enter__(self):
            # Prepare optional log file
            if self.log_file is not None:
                file_existed = self.log_file.exists()
                fid = self.log_file.open("a", newline="")
                self.log = csv.writer(fid)
                if not file_existed:
                    self.log.writerow(["Timestamp", "Voltage", "Current"])

            # Start monitor thread
            self.index = 0
            self.alive = True
            self.worker_thread = threading.Thread(target=self._worker)
            self._refresh()
            self.worker_start = time.time()
            self.worker_thread.start()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.alive = False
            self.worker_thread.join()