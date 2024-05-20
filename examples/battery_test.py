import pathlib
import logging
import time

from kunkin import Kp184

logger = logging.getLogger(__name__)

def test(load_current: float, cell_count: int, stop_voltage: float, make: str, serno: str):
    resting_time_s: int = 10
    loading_time_s: int = 5
    actual_stop_voltage = stop_voltage * cell_count

    with Kp184("/dev/ttyUSB0") as kun:
        kun.set_output_on(False)
        kun.clear_ah()
        kun.set_mode("CC")
        kun.set_cc_A(0.0)
        kun.set_output_on(True)

        log_file = pathlib.Path(
            f"{make}_5ah_{resting_time_s}s_{loading_time_s}s_{load_current:.0f}A_{serno}.txt")

        with kun.background_monitor(log_file=log_file, interval_s=0.2) as monitor:
            try:
                test_stop = False
                while True:
                    # Rest phase
                    logger.info(f"Resting phase {resting_time_s=}")
                    kun.set_cc_A(0)
                    time.sleep(resting_time_s)

                    # Pulse phase
                    logger.info(f"Load phase {load_current=} A for {loading_time_s=}")
                    kun.set_cc_A(load_current)

                    # Monitor for too big sag
                    for _ in range(loading_time_s):
                        logger.info(f"Cell voltage {monitor.voltage / cell_count} V ({monitor.voltage=} V > {actual_stop_voltage=} V)")
                        if monitor.voltage < actual_stop_voltage:
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
        load_current=9,
        cell_count=10,
        stop_voltage=3.1,
        make="ninebot",
        serno="36200121051004293")
