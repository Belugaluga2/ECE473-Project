"""Scientific safeguards for the observed-production pilot; no network or R dependency."""
import io
import re
import zipfile

import numpy as np
import pandas as pd
import pytest

from agri_hedge import dairy_validation as dv
from agri_hedge.remote_archive import HTTPRangeFile


@pytest.mark.parametrize("method", ["growth", "trend"])
def test_preseason_forecasts_do_not_read_current_or_future_milk(method):
    milk = pd.Series(100 * 1.02 ** np.arange(30), index=range(1981, 2011))
    before = dv.preseason_baseline(milk, method=method)
    changed = milk.copy()
    changed.loc[2001:] *= 3
    after = dv.preseason_baseline(changed, method=method)
    assert before.loc[2001] == pytest.approx(milk.loc[2001])
    assert after.loc[2001] == pytest.approx(before.loc[2001])
    assert after.loc[2002] != pytest.approx(before.loc[2002])


def test_missing_milk_is_not_interpolated_across_year_gaps():
    milk = pd.Series(np.arange(20) + 100, index=range(1981, 2001)).drop(1995)
    predicted = dv.preseason_baseline(milk)
    assert pd.isna(predicted.loc[1996])
    assert np.isfinite(dv.preseason_baseline(milk, method="trend").loc[1996])


def test_cover_fit_is_unchanged_when_validation_weather_and_losses_change():
    years = np.arange(1981, 2019)
    x = np.linspace(0, 30, len(years))
    y = np.maximum(x - 8, 0) * .001
    fitted = dv.fit_cover(years, x, y)
    x[years > 2000] += 1000
    y[years > 2000] += 10
    assert dv.fit_cover(years, x, y) == fitted
    assert np.max(fitted.payout(x)) <= dv.LIMIT_FRACTION


def test_price_never_uses_current_or_future_weather():
    years, index = np.arange(1981, 2019), np.arange(38, dtype=float)
    cover = dv.Cover(trigger=10, slope=.001)
    before = dv.earlier_premiums(years, index, cover)
    index[years >= 2005] += 100
    after = dv.earlier_premiums(years, index, cover)
    assert after[years == 2005] == pytest.approx(before[years == 2005])
    assert after[years == 2006] > before[years == 2006]


def test_he_alone_does_not_measure_constant_underpayment():
    y = np.array([.02, .03, .04, .05])
    m = dv.protection_metrics(y, y - .01)
    assert m["he_gross"] == pytest.approx(1)
    assert m["nrmse"] > 0 and m["bias_fraction"] < 0
    assert m["payout_recovery"] < 1


def test_premium_cost_is_visible_even_when_variance_does_not_change():
    y = np.array([.01, .02, .03, .04])
    m = dv.protection_metrics(y, y, np.full(4, .005))
    assert m["he_gross"] == pytest.approx(1)
    assert m["he_net"] == pytest.approx(1)
    assert m["p95_net_shortfall_fraction"] == pytest.approx(.005)
    assert m["mean_premium_fraction"] == pytest.approx(.005)


def test_zero_variance_is_not_reported_as_perfect_protection():
    m = dv.protection_metrics(np.zeros(10), np.zeros(10))
    assert np.isnan(m["he_gross"]) and np.isnan(m["nrmse"])


def test_bootstrap_is_paired_and_reproducible():
    y = np.array([0, .01, .03, .02, .04])
    assert dv.he_interval(y, y, repetitions=100) == pytest.approx([1, 1])
    assert dv.he_interval(y, .5 * y, repetitions=100) == dv.he_interval(y, .5 * y, repetitions=100)


class Response:
    def __init__(self, body, start, end, ignore_range=False):
        self.status_code = 200 if ignore_range else 206
        self.headers = {"Content-Range": f"bytes {start}-{end}/{len(body)}"}
        self.raw = io.BytesIO(body if ignore_range else body[start:end + 1])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Session:
    def __init__(self, body, ignore_range=False):
        self.body, self.ignore_range = body, ignore_range
        self.responses = []

    def get(self, url, headers, **kwargs):
        start, end = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", headers["Range"]).groups())
        r = Response(self.body, start, end, self.ignore_range)
        self.responses.append(r)
        return r


def test_remote_archive_extracts_only_requested_member():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("DataGenerated/panel.txt", b"small public panel")
        z.writestr("large.txt", np.random.default_rng(473).bytes(100_000))
    body = data.getvalue()
    remote = HTTPRangeFile("https://example.invalid/archive.zip", session=Session(body))
    with zipfile.ZipFile(remote) as z:
        assert z.read("DataGenerated/panel.txt") == b"small public panel"
    assert remote.bytes_received < len(body) / 10
    with pytest.raises(OSError, match="unbounded"):
        remote.max_read = 10
        remote.seek(0)
        remote.read()


def test_server_ignoring_ranges_is_rejected_before_body_download():
    session = Session(b"large body", ignore_range=True)
    with pytest.raises(OSError, match="206"):
        HTTPRangeFile("https://example.invalid/archive.zip", session=session)
    assert session.responses[0].raw.tell() == 0
