"""A daily weather series: maximum and minimum temperature (°C) and rain (mm/day).

One value per day, in date order. NASA POWER gives it for the farm; the climate models are
applied to it (step 3). Immutable by convention: every change returns a new series.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace

import numpy as np

_FIRST_DAY_OF_YEAR = 1
_EPOCH = 1970


@dataclass(frozen=True, eq=False)
class DailyWeather:
    """Columns of equal length. `month` is 1 to 12 and `day_of_year` 1 to 366."""

    year: np.ndarray
    month: np.ndarray
    day_of_year: np.ndarray
    tmax: np.ndarray
    tmin: np.ndarray
    rain: np.ndarray

    def __post_init__(self) -> None:
        sizes = {
            len(c)
            for c in (self.year, self.month, self.day_of_year, self.tmax, self.tmin, self.rain)
        }
        if len(sizes) != 1:
            raise ValueError("DailyWeather : toutes les colonnes doivent avoir la même longueur")

    @staticmethod
    def calendar_columns(first_year: int, last_year: int) -> dict[str, np.ndarray]:
        """Year, month and day of year of every day from 1 January of `first_year` to 31 December
        of `last_year`."""
        days = np.arange(
            np.datetime64(f"{first_year}-01-01"),
            np.datetime64(f"{last_year + 1}-01-01"),
            dtype="datetime64[D]",
        )
        years = days.astype("datetime64[Y]")
        return {
            "year": years.astype(int) + _EPOCH,
            "month": days.astype("datetime64[M]").astype(int) % 12 + 1,
            "day_of_year": (days - years.astype("datetime64[D]")).astype(int) + _FIRST_DAY_OF_YEAR,
        }

    @classmethod
    def from_series(
        cls,
        first_year: int,
        last_year: int,
        tmax: np.ndarray,
        tmin: np.ndarray,
        rain: np.ndarray,
    ) -> DailyWeather:
        """A series on the calendar of `first_year`…`last_year` with these daily values."""
        return cls(
            **cls.calendar_columns(first_year, last_year),
            tmax=np.asarray(tmax, dtype=float),
            tmin=np.asarray(tmin, dtype=float),
            rain=np.asarray(rain, dtype=float),
        )

    def __len__(self) -> int:
        return len(self.year)

    @property
    def first_year(self) -> int:
        return int(self.year[0])

    @property
    def last_year(self) -> int:
        return int(self.year[-1])

    @property
    def daily_mean(self) -> np.ndarray:
        """Daily mean temperature (tmax + tmin) / 2."""
        return (self.tmax + self.tmin) / 2

    def between(self, first_year: int, last_year: int) -> DailyWeather:
        """The days of the years `first_year` to `last_year` (both included)."""
        keep = (self.year >= first_year) & (self.year <= last_year)
        return DailyWeather(
            year=self.year[keep],
            month=self.month[keep],
            day_of_year=self.day_of_year[keep],
            tmax=self.tmax[keep],
            tmin=self.tmin[keep],
            rain=self.rain[keep],
        )

    def with_values(
        self,
        tmax: np.ndarray | None = None,
        tmin: np.ndarray | None = None,
        rain: np.ndarray | None = None,
    ) -> DailyWeather:
        """Same days with other values (columns not given are kept)."""
        return replace(
            self,
            tmax=self.tmax if tmax is None else tmax,
            tmin=self.tmin if tmin is None else tmin,
            rain=self.rain if rain is None else rain,
        )

    def shifted_by(self, delta_c: float) -> DailyWeather:
        """Every temperature shifted by `delta_c` °C; the rain is unchanged."""
        return self.with_values(tmax=self.tmax + delta_c, tmin=self.tmin + delta_c)

    def year_slices(self) -> Iterator[tuple[int, slice]]:
        """Each year of the series with the slice of its days (the series is in date order)."""
        starts = np.concatenate(([0], np.flatnonzero(np.diff(self.year)) + 1))
        ends = np.concatenate((starts[1:], [len(self)]))
        for start, end in zip(starts, ends, strict=True):
            yield int(self.year[start]), slice(int(start), int(end))
