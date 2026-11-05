# Reproduce the A/B summary

From the repository root:

```bash
python analysis/summarize.py
```

Requires NumPy and Matplotlib. The script reads the three CSV snapshots in `data/ab-comparison/`, validates record counts and arithmetic at the recorded display precision, and writes the descriptive summary and figure.

Single-step statistics use the workbook's displayed **energy** cells. Squaring its displayed one-decimal voltages would introduce a different rounding error. All records remain in their original groups. No observations are excluded, no p-values are inferred, and matching A/B row numbers are not treated as proof of paired trials.

Multi-step results are total capacitor energy after 5, 10, or 20 steps. Error bars are sample SD across the five displayed runs for each condition. The [experiment documentation](../docs/experiments.md) records the older summary-sheet discrepancy and the distinction between stored energy and conversion efficiency.
