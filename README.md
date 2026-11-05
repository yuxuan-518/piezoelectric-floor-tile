# Piezoelectric Floor Tile

An experimental footstep energy-harvesting project by **Shaoxuan Xiong, Shuoqi Yang, and Wenhao Jia**. Three mechanical designs explore how to load a piezoelectric disc, protect it from damage, and deliver repeatable energy to a storage capacitor.

The project began with a replication of [Selim, Yehia and Saleeb (2024)](https://doi.org/10.1007/s42417-024-01379-z). During our replication, the hot-melt glue-stick contacts deformed and damaged the discs. We replaced those contacts with sponge pads, then developed spring–impactor and center-punch mechanisms.

## Three design iterations

<table>
  <tr><th>V1 · Sponge sandwich</th><th>V2 · Spring–impactor</th><th>V3 · Center punch</th></tr>
  <tr>
    <td><img src="assets/images/v1/sponge-sandwich-tile.jpg" alt="V1 plywood plate and eight-disc sponge sandwich" width="260"></td>
    <td><img src="assets/images/v2/cad-module-layout.jpg" alt="V2 CAD layout of spring–impactor modules and return springs" width="260"></td>
    <td><img src="assets/images/v3/center-punch-section.png" alt="Section drawing of the V3 center-punch mechanism" width="180"></td>
  </tr>
</table>

| Version | Design change | What we learned |
| --- | --- | --- |
| **V1** | Sponge pads transmit the load to an eight-disc parallel array. | The softer interface followed damage observed with glue-stick contacts. Output also varied with stepping position. |
| **V2** | Spring–impactor modules and separate travel-limiting/return springs allow separation and repeated contact. | The moving plate and impactor produced variable responses. This motivated a more deliberately triggered release. |
| **V3** | A center-punch-style mechanism stores spring energy and releases it at a mechanical trigger. | The mechanism has been printed, assembled, and successfully triggered. V3 is structure **B** in the comparison data. |

[Design development and observations](docs/design-evolution.md) · [CAD downloads](cad/README.md) · [Videos](assets/videos/README.md)

## A/B experiments

**A is a single-disc adaptation of V1; B is the single-disc V3 structure.** A was reduced to one disc to match B's piezo count. The original eight-disc V1 tile is a separate historical configuration.

The same operator used the same shoes and stepping location, alternating A/B under normal stepping. Disc model, rectifier bridge, and post-step waiting time matched. The **4.7 μF** capacitor was discharged before each single-step trial.

| Measurement | A · V1-derived | B · V3 | Records per structure |
| --- | ---: | ---: | ---: |
| Single-step stored energy, mean ± sample SD | **11.6 ± 6.3 μJ** | **72.5 ± 12.8 μJ** | 100, in 5 groups of 20 |
| Quasi-open-circuit Vpp, mean ± sample SD | 40.2 ± 3.9 V | 94.9 ± 16.7 V | 60, in 3 groups of 20 |

Mean single-step stored energy for B was about **6.23 times A's (B/A = 6.23)** in these tests. Travel and stepping speed were not controlled or recorded, and mechanical input energy was not measured; this is a storage comparison under normal stepping, not a conversion-efficiency ratio. Statistics use displayed workbook values captured on November 4, 2026.

![A/B capacitor energy measurements, with single-step records and multi-step charging results](assets/figures/ab-energy-comparison.png)

[Test conditions and interpretation](docs/experiments.md) · [Data and formula review](data/README.md)

## Explore the project

| Material | Location |
| --- | --- |
| CAD meshes and original V2 assembly download | [cad/](cad/README.md) |
| Structure photos, sketches, and CAD views | [assets/images/](assets/images/README.md) |
| Mechanism, structural-simulation, and LED videos | [assets/videos/](assets/videos/README.md) |
| A/B trial snapshots and reproducible summary | [data/](data/README.md), [analysis/](analysis/README.md) |
| V2 mechanical simulation, six displacement inputs, and recorded results | [simulation/v2/](simulation/v2/README.md) |
| Chinese laboratory summaries and process reports | [docs/process-reports/](docs/process-reports/README.md) |
| Full V2 CAD and historical V1/V2 measurement archive | [Project archive release](https://github.com/yuxuan-518/piezoelectric-floor-tile/releases/tag/project-archive-2026-11-04) |

## Contributors

| Contributor | Contributions |
| --- | --- |
| **Shaoxuan Xiong** | **Research lead and first author of the project manuscript.** Developed the research idea, workflow, and methods. Led early circuit assembly, capacitor selection, and V1/V2 measurements; assessed data quality and plausibility and led the overall analysis. Reviewed the V3 data collected independently by Wenhao Jia and Shuoqi Yang, then performed the complete analysis and prepared the figures. Led V2 mechanism development, Python simulation, and spring-parameter selection. Revised and checked the physical model assembled by Shuoqi Yang. Set the manuscript structure and revised Wenhao Jia's first draft into the final manuscript. |
| **Shuoqi Yang** | Led V1/V2 CAD modeling and contributed to structural redesign and V2 mechanism development. Assembled the complete physical model for review and revision with Shaoxuan Xiong. Performed most routine circuit preparation and acted as the stepping operator. Contributed substantially to V1/V2 data organization, analysis, and figures. Independently collected the V3 dataset together with Wenhao Jia and sent it to Shaoxuan Xiong for review and analysis. |
| **Wenhao Jia** | Wrote the first manuscript draft from Shaoxuan Xiong's outline. Assisted V1/V2 CAD modeling and contributed to V3 mechanism modeling and animation. Helped with circuit preparation, reported readings for Shaoxuan Xiong to record, and filmed experiments. Independently collected the V3 dataset together with Shuoqi Yang and sent it to Shaoxuan Xiong for review and analysis. |

[Detailed contributions and attribution](CREDITS.md).

## Reference

Selim, K. K., Yehia, H. M., & Saleeb, D. A. (2024). *Energy Harvesting Floor Tile Using Piezoelectric Patches for Low-Power Applications*. Journal of Vibration Engineering & Technologies, 12, 8613–8622. [doi:10.1007/s42417-024-01379-z](https://doi.org/10.1007/s42417-024-01379-z). Performance reported in that paper belongs to its prototype and is not presented as our measured output.
