import time
import logging

from kunkin import Kp184

def main():
    logging.basicConfig(level=logging.INFO)

    with Kp184("/dev/ttyUSB0") as kun:
        kun.set_output_on(True)

        kun.set_cv_V(130.0)
        kun.set_cc_A(0.201)
        kun.set_cr_ohm(1)
        kun.set_cw_W(1.0)

        print(f"{kun.get_cv_V()=}")
        print(f"{kun.get_cc_A()=}")
        print(f"{kun.get_cr_ohm()=}")
        print(f"{kun.get_cw_W()=}")

        try:
            while True:
                print(f"{kun.measure_voltage()} V, {kun.measure_current()} A")
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nClose")

if __name__ == "__main__":
    main()