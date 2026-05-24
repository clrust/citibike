"""
Download raw bikeshare trip data needed for main and placebo analyses.

The downloader skips files that already exist and are valid ZIP archives. New
downloads are written to a .part file first, verified as ZIPs, then moved into
place.
"""

from __future__ import annotations

import argparse
import shutil
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FILES = (
    # Citi Bike
    ("citi_bike", "202508-citibike-tripdata.zip", "https://s3.amazonaws.com/tripdata/202508-citibike-tripdata.zip"),
    ("citi_bike", "202409-citibike-tripdata.zip", "https://s3.amazonaws.com/tripdata/202409-citibike-tripdata.zip"),
    ("citi_bike", "202411-citibike-tripdata.zip", "https://s3.amazonaws.com/tripdata/202411-citibike-tripdata.zip"),
    # Divvy
    ("divvy", "202508-divvy-tripdata.zip", "https://divvy-tripdata.s3.amazonaws.com/202508-divvy-tripdata.zip"),
    ("divvy", "202409-divvy-tripdata.zip", "https://divvy-tripdata.s3.amazonaws.com/202409-divvy-tripdata.zip"),
    ("divvy", "202411-divvy-tripdata.zip", "https://divvy-tripdata.s3.amazonaws.com/202411-divvy-tripdata.zip"),
    # Bluebikes
    ("bluebike", "202508-bluebikes-tripdata.zip", "https://s3.amazonaws.com/hubway-data/202508-bluebikes-tripdata.zip"),
    ("bluebike", "202409-bluebikes-tripdata.zip", "https://s3.amazonaws.com/hubway-data/202409-bluebikes-tripdata.zip"),
    ("bluebike", "202411-bluebikes-tripdata.zip", "https://s3.amazonaws.com/hubway-data/202411-bluebikes-tripdata.zip"),
    # Capital Bikeshare
    ("capitalbike", "202508-capitalbikeshare-tripdata.zip", "https://s3.amazonaws.com/capitalbikeshare-data/202508-capitalbikeshare-tripdata.zip"),
    ("capitalbike", "202409-capitalbikeshare-tripdata.zip", "https://s3.amazonaws.com/capitalbikeshare-data/202409-capitalbikeshare-tripdata.zip"),
    ("capitalbike", "202411-capitalbikeshare-tripdata.zip", "https://s3.amazonaws.com/capitalbikeshare-data/202411-capitalbikeshare-tripdata.zip"),
    # Indego quarterly files. 2025 Q3 is already expected to exist, but keeping
    # it here makes the required raw set explicit and reproducible.
    ("indego", "indego-trips-2025-q3.zip", "https://www.rideindego.com/wp-content/uploads/2025/10/indego-trips-2025-q3.zip"),
    ("indego", "indego-trips-2024-q3.zip", "https://www.rideindego.com/wp-content/uploads/2024/10/indego-trips-2024-q3.zip"),
    ("indego", "indego-trips-2024-q4.zip", "https://www.rideindego.com/wp-content/uploads/2025/01/indego-trips-2024-q4.zip"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=PROJECT_ROOT / "data_raw")
    parser.add_argument("--force", action="store_true", help="Download even if a valid ZIP already exists.")
    return parser.parse_args()


def is_valid_zip(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0 and zipfile.is_zipfile(path)


def download(url: str, destination: Path, force: bool) -> str:
    if is_valid_zip(destination) and not force:
        return f"skip valid {destination} ({destination.stat().st_size / 1024**2:.1f} MB)"

    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    if part.exists():
        part.unlink()

    print(f"Downloading {url}", flush=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request) as response, part.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)

    if not is_valid_zip(part):
        raise RuntimeError(f"Downloaded file is not a valid ZIP: {part}")

    part.replace(destination)
    return f"wrote {destination} ({destination.stat().st_size / 1024**2:.1f} MB)"


def main() -> None:
    args = parse_args()
    for subdir, filename, url in FILES:
        destination = args.raw_root / subdir / filename
        print(download(url, destination, args.force), flush=True)


if __name__ == "__main__":
    main()
