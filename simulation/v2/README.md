# V2 spring–impactor simulation

This is the event-driven Python model referenced in the July process reports. It screens whether a **V2** impactor can separate from a prescribed moving floor, undergo free spring–mass motion, and make further contact.

**`measured_v1`, `measured_v2`, and `measured_v3` name analysis-pipeline revisions. They are not the three physical tile designs. This code does not simulate the V3 center punch.**

## Model and scope

The coordinate direction is downward. During contact, the impactor follows the supplied floor displacement. The simplified contact force is

\[
N(t)=m\,a_p(t)+k\,y_p(t).
\]

A confirmed crossing into negative required force indicates separation. Free motion uses the undamped spring–mass analytic solution; a restitution coefficient controls velocity changes at subsequent contacts. See `config.py`, `floor_motion.py`, and `event_sim.py` for the implemented assumptions.

The plate trajectory is prescribed and does not respond to the impactor. Continuous damping, a coupled plate model, piezoelectric conversion, and a charging circuit are outside this model. Its impact-energy values are mechanical screening indices, not capacitor energy predictions or disc-fracture measurements.

## Files

| File/folder | Purpose |
| --- | --- |
| `config.py` | Shared physical assumptions and numerical settings |
| `floor_motion.py`, `event_sim.py` | Floor-input interpolation and event-driven contact mechanics |
| `sweep.py`, `plotting.py` | Parameter sweeps and figure generation |
| `run_all.py` | Earlier parameterized-input study |
| `run_measured.py` | Six measured curves, preprocessing/smoothing comparisons, and sweeps |
| `run_measured_summary.py` | Candidate classification from the recorded `measured_v3_sim_sweep.csv` |
| `data/` | Six input curves: `time_s` and `compression_mm` |
| `results/` | Recorded 432-run sweep, 216-row clamp classification, and strong-candidate table |
| `figures/` | Selected original overview and candidate maps |

The original camera-to-curve mapping and the conversion from 120 fps video to 0.01 s samples remain limitations documented in the process reports. Interpolated root-finding precision must not be interpreted as sub-millisecond measurement precision.

## Run

From this directory, in a Python environment satisfying `requirements.txt`:

```bash
python run_measured_summary.py
```

This summarizes the bundled sweep without rerunning it and writes result tables and plots. To rerun the full measured-input study:

```bash
python run_measured.py
python run_measured_summary.py
```

The archived analysis identified 100 g and 0.5 N/mm as an initial physical-test candidate under one fast-step input. It did not establish a universally optimal spring or a prediction for V3 performance.
