import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import struct
import numpy as np

class FastGRIB2Exporter:

    def __init__(self, output_dir="grib2_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _denorm(self, arr, params):
        return arr * (params['max'] - params['min']) + params['min']

    def create_grib2_fast(self, predictions, scaler_params, timestamp):

        features = ['LAT', 'LON', 'WMO_WIND', 'WMO_PRES', 'USA_WIND', 'USA_PRES']
        res = {}

        for i, feat in enumerate(features):
            res[feat] = self._denorm(predictions[:, i], scaler_params[feat])

        hours = len(predictions)
        times = [timestamp + timedelta(hours=i) for i in range(hours)]

        df = pd.DataFrame({
            "LATITUDE": res["LAT"],
            "LONGITUDE": res["LON"],
            "TIME": times,
            "STEP": [f"{i}h" for i in range(hours)],
            "PRMSL": res["WMO_PRES"] * 100,
            "T": [302.3] * hours,
            "U10": res["WMO_WIND"] * 0.5,
            "V10": res["WMO_WIND"] * 0.866,
        })

        name = timestamp.strftime("%Y%m%d_%H%M%S")
        csv_path = self.output_dir / f"{name}.csv"
        df.to_csv(csv_path, index=False)

        bin_path = self.output_dir / f"{name}.grib2"
        with open(bin_path, "wb") as f:
            f.write(b"GRIB")
            f.write(struct.pack(">H", 2))

            for i in range(hours):
                record = struct.pack(
                    ">ffffffffff",
                    df.iloc[i]["LATITUDE"],
                    df.iloc[i]["LONGITUDE"],
                    df.iloc[i]["PRMSL"],
                    df.iloc[i]["T"],
                    df.iloc[i]["U10"],
                    df.iloc[i]["V10"],
                    float(i), 0, 0, 0,
                )
                f.write(record)

            f.write(b"7777")

        print(f"💾 Saved: {csv_path}, {bin_path}")
        return df
