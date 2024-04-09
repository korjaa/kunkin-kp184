import pathlib
import logging
import time

from kunkin import Kp184

logger = logging.getLogger(__name__)

def test(load_current: float, cell_count: int, stop_voltage: float):
    with Kp184("/dev/ttyUSB0") as kun:
        kun.set_output_on(False)

        kun.set_mode("CC")
        kun.set_cc_A(0.2)

        print(f"{kun.get_mode()=}")
        print(f"{kun.get_cc_A()=}")

        kun.set_output_on(True)

        log_file = pathlib.Path("battery_test.txt")
        with kun.background_monitor(log_file=log_file, interval_s=0.25) as monitor:
            test_stop = False
            try:
                while True:
                    # Rest phase
                    logger.info("Resting phase")
                    kun.set_cc_A(0)
                    time.sleep(5)

                    # Pulse phase
                    logger.info(f"Load phase {load_current=} A")
                    kun.set_cc_A(load_current)

                    # Monitor for too big sag
                    for _ in range(10):
                        print(f"Cell voltage {monitor.voltage / cell_count} V ({monitor.voltage=} V)")
                        if monitor.voltage < stop_voltage * cell_count:
                            test_stop = True
                            break
                        time.sleep(1.0)
                    if test_stop:
                        break
            except KeyboardInterrupt:
                logger.info("Stop")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test(
        load_current=10.0,
        cell_count=5,
        stop_voltage=3.1)