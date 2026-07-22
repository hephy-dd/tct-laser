import csv
import os

import yaml

from tct_laser.core.utils import safe_iso_timestamp

YAML_SEP = "---"


class RasterScanFileWriter:
    def __init__(self, output_path: str) -> None:
        output_path = os.path.abspath(output_path)
        output_ts = safe_iso_timestamp()
        output_prefix = "raster_scan"
        self.output_file = os.path.join(output_path, f"{output_prefix}_{output_ts}.txt")

    def create_output_path(self) -> None:
        output_path = os.path.dirname(self.output_file)
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    def write_header(self, data: dict) -> None:
        with open(self.output_file, "w", newline="") as f:
            f.write(f"{YAML_SEP}\n")
            yaml.safe_dump(data, f, sort_keys=False)
            f.write(f"{YAML_SEP}\n")

    def write_table_header(self, columns: list) -> None:
        with open(self.output_file, "a", newline="") as f:
            f.write("\n")
            writer = csv.writer(f, delimiter=" ")
            writer.writerow(columns)

    def write_table_row(self, row: list) -> None:
        with open(self.output_file, "a", newline="") as f:
            writer = csv.writer(f, delimiter=" ")
            writer.writerow(row)

    def write_footer(self) -> None:
        with open(self.output_file, "a", newline="") as f:
            f.write(f"{YAML_SEP}\n")
