"""CSV export schema test: header comments + new metadata columns."""
import csv
import os

import numpy as np
import pytest

import wb_quantifier_advanced as wba
from conftest import bare_app, stub_var


@pytest.fixture
def export_app(tmp_path, monkeypatch):
    out_csv = str(tmp_path / 'export.csv')
    monkeypatch.setattr(wba.filedialog, 'asksaveasfilename',
                        lambda *a, **k: out_csv)
    monkeypatch.setattr(wba.messagebox, 'showinfo', lambda *a, **k: None)
    monkeypatch.setattr(wba.messagebox, 'showwarning', lambda *a, **k: None)

    interactive_band = dict(
        lane=1, band=1,
        area=2500.0, height=90.0, width=12,
        peak_position=10, start=5, end=15,
        baseline_source='manual_region',
        baseline_value=123.5,
        baseline_region=(10, 20),
        integration_method='interactive',
        fit_method='single_gaussian',
        fit_params=(1.0, 2.0, 3.0),
        fit_polarity=1.0,
        fit_area=777.0,
        fit_area_scope='full_curve',
    )
    auto_band = dict(
        lane=2, band=1,
        area=5000.0, height=45.0, width=8,
        peak_position=12, start=8, end=16,
        baseline_source='none',
        baseline_value=None,
        baseline_region=None,
        integration_method='fixed_width',
        fit_method='none',
        fit_params=None,
        fit_polarity=None,
        fit_area=None,
        fit_area_scope=None,
    )
    app = bare_app(
        band_data=[interactive_band, auto_band],
        lane_profiles=[np.linspace(0, 10, 30), np.linspace(5, 15, 30)],
        lanes=[(0, 0, 4, 20), (0, 0, 4, 20)],
        lane_size=(4, 20),
        image_path='blot.tif',
        background_boxes=[],
        background_lane_map=[],
        original_image=None,
        peak_threshold=stub_var(0.1),
        image_page=0,
    )
    app.export_data()
    assert os.path.exists(out_csv)
    return out_csv, interactive_band, auto_band


def _read_export(path):
    with open(path) as f:
        lines = f.readlines()
    comments = [l.strip() for l in lines if l.startswith('#')]
    data_lines = [l for l in lines if not l.startswith('#')]
    rows = list(csv.DictReader(data_lines))
    return comments, rows


def test_export_writes_header_comments(export_app):
    path, _, _ = export_app
    comments, _ = _read_export(path)
    text = '\n'.join(comments)
    assert any(c.startswith('# display_scale=') for c in comments)
    assert any(c.startswith('# tool_version=') for c in comments)
    assert any(c.startswith('# git_commit=') for c in comments)
    assert any(c.startswith('# tool=') for c in comments)
    assert any(c.startswith('# export_utc=') for c in comments)


def test_export_header_columns(export_app):
    path, _, _ = export_app
    _, rows = _read_export(path)
    assert len(rows) == 2
    cols = set(rows[0].keys())
    original = {'Source_File', 'Lane', 'Band', 'Area_corrected', 'Area_display',
                'Area_raw', 'LOQ', 'LOQ_model', 'LOQ_empirical',
                'BG_Mean', 'BG_Median', 'BG_SD',
                'BG_Area_mean_empirical', 'BG_Area_SD_empirical',
                'BG_Area_N_empirical', 'SNR_area_empirical',
                'Height', 'Width', 'Peak_Position', 'Start', 'End'}
    new_cols = {'Baseline_Method', 'Baseline_Value', 'Baseline_Region_Start',
                'Baseline_Region_End', 'Integration_Method', 'Fit_Method',
                'Fit_Area_Scope', 'Fit_Area', 'Fit_Amp', 'Fit_Mu',
                'Fit_Sigma', 'Fit_Polarity'}
    assert original | new_cols <= cols


def test_export_row_values(export_app):
    path, interactive_band, auto_band = export_app
    _, rows = _read_export(path)

    r1 = next(r for r in rows if r['Lane'] == '1')
    assert r1['Source_File'] == 'blot.tif'
    assert r1['Baseline_Method'] == 'manual_region'
    assert r1['Baseline_Value'] == '{:.12e}'.format(123.5)
    assert r1['Baseline_Region_Start'] == '10'
    assert r1['Baseline_Region_End'] == '20'
    assert r1['Integration_Method'] == 'interactive'
    assert r1['Fit_Method'] == 'single_gaussian'
    assert r1['Fit_Area_Scope'] == 'full_curve'
    assert r1['Fit_Area'] == '{:.12e}'.format(777.0)
    assert r1['Fit_Amp'] == '{:.12e}'.format(1.0)
    assert r1['Fit_Mu'] == '{:.12e}'.format(2.0)
    assert r1['Fit_Sigma'] == '{:.12e}'.format(3.0)
    assert r1['Fit_Polarity'] == '{:.6g}'.format(1.0)
    assert r1['Start'] == str(interactive_band['start'])
    assert r1['End'] == str(interactive_band['end'])

    r2 = next(r for r in rows if r['Lane'] == '2')
    assert r2['Integration_Method'] == 'fixed_width'
    assert r2['Baseline_Value'] == ''
    assert r2['Baseline_Region_Start'] == ''
    assert r2['Fit_Area'] == ''
    assert r2['Fit_Amp'] == ''
    assert r2['Fit_Polarity'] == ''


def test_export_area_raw_from_profile(export_app):
    path, interactive_band, _ = export_app
    _, rows = _read_export(path)
    r1 = next(r for r in rows if r['Lane'] == '1')
    prof = np.linspace(0, 10, 30)
    expected_raw = float(np.trapz(prof[interactive_band['start']:interactive_band['end']]))
    assert float(r1['Area_raw']) == pytest.approx(expected_raw, rel=1e-9)


def test_export_no_data_warns_and_returns(tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(wba.filedialog, 'asksaveasfilename',
                        lambda *a, **k: str(tmp_path / 'x.csv'))
    monkeypatch.setattr(wba.messagebox, 'showwarning',
                        lambda *a, **k: warnings.append(a))
    app = bare_app(band_data=[])
    app.export_data()
    assert warnings  # early-return path hit
    assert not os.path.exists(str(tmp_path / 'x.csv'))
