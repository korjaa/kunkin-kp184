import logging
import pathlib
from typing import List

import scipy
import pandas
import numpy
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def process_file(csv_file: pathlib.Path, color: str, axs: List[plt.Axes]):
    df = pandas.read_csv(
        csv_file,
        delimiter=",",
        parse_dates=[0],
        index_col=0
    )
    df["Cell Voltage"] = df["Voltage"] / 5
    df["Loaded"] = df["Current"] > 9.9
    df["Relaxed"] = df["Current"] < 0.1

    # Remove sloping current (Load transition cleaning 1)
    smaller_than = df["Current"] < 0.1
    larger_than = df["Current"] > 9.9
    valid_values = smaller_than | larger_than
    df = df[valid_values]
    logger.info(f"Removed {sum(~valid_values)} transition samples")

    # Erode close by samples (Load transition cleaning 2)
    mask = scipy.ndimage.binary_erosion(
        input=df["Current"].diff().abs() < 9,
        iterations=2
    )
    df = df[mask]
    logger.info(f"Eroded {sum(~mask)} transition samples")

    # Fill NaN values between resting/loading phases
    df["Loaded Battery Voltage"] = numpy.nan
    df.loc[df["Loaded"], "Loaded Battery Voltage"] = \
        df.loc[df["Loaded"], "Voltage"]
    df["Relaxed Battery Voltage"] = numpy.nan
    df.loc[df["Relaxed"], "Relaxed Battery Voltage"] = \
        df.loc[df["Relaxed"], "Voltage"]
    df["Loaded Battery Voltage"] = df["Loaded Battery Voltage"].interpolate()
    df["Relaxed Battery Voltage"] = df["Relaxed Battery Voltage"].interpolate()

    # Calculate Voltage drop and resistance
    df["Battery Voltage Drop"] = df["Relaxed Battery Voltage"] - df["Loaded Battery Voltage"]
    df["Battery Resistance mOhm"] = (df["Battery Voltage Drop"] / 10.0) * 1e3

    df.plot(ax=axs[0], x="AH", y=["Relaxed Battery Voltage", "Loaded Battery Voltage"],
            color=color, legend=False)
    df.plot(ax=axs[1], x="AH", y="Battery Resistance mOhm",
            color=color, legend=False)


def process_files(csv_files: List[pathlib.Path], plt_name: pathlib.Path):
    colors_available = plt.rcParams['axes.prop_cycle'].by_key()['color']

    # Setup plot
    plt.clf()
    axs: List[plt.Axes]
    fig, axs = plt.subplots(nrows=2, ncols=1)
    axs[0].set_ylabel("Voltage [V]")
    axs[1].set_ylabel("Resistance [mΩ]")

    # Process files
    for color, csv_file in zip(colors_available, csv_files):
        logging.info(f"Analyzing {csv_file}")
        process_file(csv_file, color, axs)

    axs[0].legend(
        (plt.Line2D([0], [0], color=color, lw=1) for color in colors_available),
        csv_files
    )

    # Post adjust
    for ax in axs:
        ax.set_xlim([0, 4])
        ax.grid(True)
        if ax != axs[-1]:
            ax.tick_params(axis="x", which="both", labelbottom=False)
            ax.set_xlabel(None)

    fig.set_size_inches(10, 10)
    plt.subplots_adjust(left=0.07, bottom=0.1, right=0.95, top=0.90, hspace=0.1)
    plt.savefig(plt_name)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    process_files(
        csv_files=list(pathlib.Path(".").glob("ryobi_[45]ah_*old.txt")),
        plt_name=pathlib.Path("compare_old_batteries.png"))

    process_files(
        csv_files=list(pathlib.Path(".").glob("ryobi_[45]ah_*new.txt")),
        plt_name=pathlib.Path("compare_new_batteries.png"))
