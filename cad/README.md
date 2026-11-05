# CAD and meshes

| Version | Available material | Notes |
| --- | --- | --- |
| V1 | [Photos and construction views](../assets/images/v1/) | No V1 CAD model was supplied. |
| V2 | [Original full assembly STL download](https://github.com/yuxuan-518/piezoelectric-floor-tile/releases/download/project-archive-2026-11-04/v2-full-cad.zip), [layout and section views](../assets/images/v2/) | The original assembly is about 366 MB, so it is distributed as a release asset. The mesh has not been simplified. |
| V3 | [Center-punch assembly STL](v3/center-punch-assembly.stl), [section drawing](../assets/images/v3/center-punch-section.png) | Supplied assembly mesh and mechanism drawing. |
| Component | [Impactor STL](components/impactor.stl) | Supplied as `撞击物(1).stl`; assignment to a particular build has not been independently confirmed. |

**Shuoqi Yang** led V1/V2 CAD modeling, with assistance from **Wenhao Jia**, who also contributed to V3 mechanism modeling and animation. **Shaoxuan Xiong** led V2 mechanism development, Python simulation, and spring-parameter selection, with support from Shuoqi Yang. Shuoqi Yang assembled the physical model; Shaoxuan Xiong revised, reorganized, and checked it, and they finalized it together. [Full contributions](../CREDITS.md).

STL is a triangulated surface format and does not store dimensional units or editable design features. Consult the drawings for dimensions and assembly interpretation. A full assembly mesh is not automatically a set of separately printable parts.

Source-file hashes are recorded in [the source manifest](../data/source-file-manifest.csv). The V2 archive includes the original mesh hash internally and has its own checksum in [release-assets.csv](../data/release-assets.csv).
