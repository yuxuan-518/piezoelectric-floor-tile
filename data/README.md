# Data

## Current A/B comparison

[Live source: 地砖数据.xlsx](https://1drv.ms/x/c/ec731eaab7075a35/IQBu0pYTxfz4QIeSvFwY5F9VATk93ZKyLGgmgde4zelluMU)

The `ab-comparison/` files snapshot displayed values read from Excel Online on **2026-11-04**. They preserve a readable, versioned comparison while the linked workbook can continue to change. They are not a full-precision export or a complete copy of the workbook.

| File | Contents |
| --- | --- |
| [single-step.csv](ab-comparison/single-step.csv) | 200 records: 100 each for A and B, five groups of 20 |
| [quasi-open-circuit.csv](ab-comparison/quasi-open-circuit.csv) | 120 records: 60 each for A and B, three groups of 20 |
| [multi-step.csv](ab-comparison/multi-step.csv) | 30 runs: five per structure for each of 5, 10, and 20 steps |
| [summary.csv](ab-comparison/summary.csv) | Means and sample SD calculated from the copied records |
| [workbook-display-copy-2026-11-04.json](ab-comparison/workbook-display-copy-2026-11-04.json) | Compact copied values, source URL, retrieval date, and capture method |
| [ab-formula-review-2026-11-05.xlsx](ab-comparison/ab-formula-review-2026-11-05.xlsx) | Derived review workbook: formula-based summary, copied trial values, and voltage-rounding checks; not the original XLSX |

**A = one-disc V1-derived sponge structure. B = one-disc V3 center-punch structure.** The full historical V1 tile used eight parallel discs.

### Column dictionary

| Column | Meaning |
| --- | --- |
| `structure` | A or B, as defined above |
| `group`, `trial` | Original adjacent-column group and row index within that group; not a paired-trial claim |
| `replicate`, `steps` | Multi-step run index and number of steps in that run |
| `voltage_before_display_v` | Displayed capacitor voltage before the trial/run, V |
| `voltage_after_display_v` | Displayed capacitor voltage after the trial/run, V |
| `recorded_energy_display_uj` | Energy value displayed in the source sheet, μJ, based on 4.7 μF |
| `vmax_v`, `vmin_v`, `vpp_v` | Quasi-open-circuit positive peak, negative peak, and peak-to-peak voltage, V |
| `source_sheet`, `source_row`, `source_voltage_cell`, `source_energy_cell` | Locations in the live source workbook |
| `n`, `mean`, `sample_sd` | Descriptive record count, arithmetic mean, and sample standard deviation |

For single-step data, displayed voltage has one decimal place. Keep the workbook's recorded energy rather than treating a calculation from rounded voltage as full precision. Multi-step energy is the **total after that many steps**, not energy per step. [Measurement details and summary discrepancy](../docs/experiments.md).

### Formula review and original-workbook status

The review workbook is built from these CSV snapshots. Its `Summary` sheet replaces the outdated summary for this local review only: 100 single steps per structure, 60 quasi-open-circuit steps per structure, and five runs per structure at each multi-step count. Formula-based means and sample SD reproduce `summary.csv` without excluding records.

`Capacitor` preserves the copied voltages and recorded energy in separate input columns. The recalculated column applies `0.5 * C * (V1^2 - V0^2)` to rounded voltage, so its difference from recorded energy is visible rather than overwritten. Lower/upper energy bounds use ±0.05 V for single-step and ±0.005 V for multi-step voltage displays, with corresponding energy-display rounding. A compatible value means the rounding intervals overlap; it does not recover hidden cell precision or verify the original formula. `Voltage` preserves copied Vmax/Vmin/Vpp and checks their arithmetic.

The ratio of means **B/A = 6.233** and relative increase **(B−A)/A = 523.3%** are labeled separately. Neither is a conversion-efficiency estimate. The live source's older “提升倍” values use an increase relative to A, so they must not be interpreted directly as B/A.

The original `.xlsx` has **not** been archived: the read-only Excel Online “Download a copy” command did not return a file on November 5, 2026. Original cell formulas and full-precision values therefore remain unavailable. The live workbook, including its older “条件” summary, has not been changed. When an original export becomes available, preserve it separately and reconcile it against this dated snapshot before replacing any published statistics.

## Historical V1/V2 measurements

The [historical measurement archive](https://github.com/yuxuan-518/piezoelectric-floor-tile/releases/download/project-archive-2026-11-04/historical-v1-v2-measurements.zip) holds oscilloscope photos, capacitor recordings, the slow-step displacement table, and original motion videos. The archive retains the source subfolder labels and group/step identifiers.

[historical-v1-v2-manifest.csv](historical-v1-v2-manifest.csv) lists its files and SHA256 hashes. These records describe earlier configurations and are not substitutes for missing raw A/B oscilloscope exports.

## V2 simulation inputs and outputs

Six measured displacement curves are included in [simulation/v2/data/](../simulation/v2/data/): `fast_1`–`fast_3` and `slow_1`–`slow_3`. They contain time in seconds and compression in millimeters. Original motion-video to CSV mapping is not fully confirmed by the archived report.

The [V2 simulation results](../simulation/v2/results/) concern mechanical separation and impact. `measured_v3` denotes an analysis-pipeline revision for V2 and must not be read as V3 device measurements.

## Reproduce the summary

Run `python analysis/summarize.py` from the repository root. It checks sample counts, Vpp arithmetic, and capacitor energy consistency at the displayed voltage precision, then reproduces `summary.csv` and the A/B figure. Requires NumPy and Matplotlib; the supplied [simulation requirements](../simulation/v2/requirements.txt) include them.
