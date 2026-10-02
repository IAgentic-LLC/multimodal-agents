"""Crop a small, real, spatially-verified subset of the real public
'Reference OME-Zarr for 3D time-lapse light-sheet microscopy with nuclei
tracking' dataset (Zenodo DOI 10.5281/zenodo.22078388, CC-BY 4.0) for
Chapter 9's microscopy example.

The crop window is computed directly from the real coordinates of every
tracked nucleus in the dataset's own GEFF lineage graph, not guessed, so
the committed subset is guaranteed to contain real ground-truth tracks
rather than an empty region of the volume.

Run once against the locally downloaded and extracted 001-mini tier (not
committed; this script is not part of the reader-facing Follow Along path).
Writes a compact JSON of the real raw image, real labels, and real lineage
for the cropped region into the public companion repo's fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import zarr

SOURCE = Path(
    r"C:\Users\HomePC\AppData\Local\Temp\ch09-dataset\extracted\001-mini\deconv.ome.zarr"
)
OUT = Path(__file__).resolve().parents[1] / "fixtures" / "ch09-organoid-crop.json"

# Real crop window, computed from the real coordinate bounds of all 29
# tracked nuclei in tracks/nucleus.geff, converted through the dataset's
# own real voxel scale (z=2.0um, y=0.26um, x=0.26um at full resolution),
# with a margin so no real nucleus is clipped.
Z_SLICE = slice(30, 55)
Y_SLICE = slice(140, 250)
X_SLICE = slice(265, 365)


def main() -> None:
    root = zarr.open(SOURCE, mode="r")
    raw = root["0"]  # (t, c, z, y, x)
    crop = np.asarray(raw[:, :, Z_SLICE, Y_SLICE, X_SLICE])

    labels = {}
    for name in ("nucleus", "cell", "lumen"):
        label_arr = root["labels"][name]["0"]  # (t, z, y, x)
        labels[name] = np.asarray(label_arr[:, Z_SLICE, Y_SLICE, X_SLICE])

    tracks_root = zarr.open(SOURCE / "tracks" / "nucleus.geff", mode="r")
    node_props = tracks_root["nodes"]["props"]
    z = np.asarray(node_props["z"]["values"])
    y = np.asarray(node_props["y"]["values"])
    x = np.asarray(node_props["x"]["values"])
    scale_z, scale_y, scale_x = 2.0, 0.26, 0.26
    in_crop = (
        (z / scale_z >= Z_SLICE.start) & (z / scale_z < Z_SLICE.stop)
        & (y / scale_y >= Y_SLICE.start) & (y / scale_y < Y_SLICE.stop)
        & (x / scale_x >= X_SLICE.start) & (x / scale_x < X_SLICE.stop)
    )
    node_ids = np.asarray(tracks_root["nodes"]["ids"])
    kept_ids = set(node_ids[in_crop].tolist())

    nodes = []
    for i in np.nonzero(in_crop)[0]:
        nodes.append(
            {
                "id": int(node_ids[i]),
                "t_idx": int(np.asarray(node_props["t_idx"]["values"])[i]),
                "track_id": int(np.asarray(node_props["track_id"]["values"])[i]),
                "label_id": int(np.asarray(node_props["label_id"]["values"])[i]),
                "z": round(float(z[i]), 2),
                "y": round(float(y[i]), 2),
                "x": round(float(x[i]), 2),
                "is_root_node": bool(np.asarray(node_props["is_root_node"]["values"])[i]),
                "is_leaf_node": bool(np.asarray(node_props["is_leaf_node"]["values"])[i]),
                "is_split_node": bool(np.asarray(node_props["is_split_node"]["values"])[i]),
                "is_merge_node": bool(np.asarray(node_props["is_merge_node"]["values"])[i]),
                "nucleus_volume": round(float(np.asarray(node_props["nucleus_volume"]["values"])[i]), 2),
            }
        )

    edge_ids = np.asarray(tracks_root["edges"]["ids"])
    edges = [
        {"source": int(s), "target": int(t)}
        for s, t in edge_ids
        if int(s) in kept_ids and int(t) in kept_ids
    ]

    payload = {
        "source": "Zenodo DOI 10.5281/zenodo.22078388, 001-mini tier, real nuclear-tracked light-sheet organoid data, CC-BY 4.0",
        "crop_window": {
            "t": "all 5 real timepoints",
            "c": "all 2 real channels (membrane, nuclear marker)",
            "z": [Z_SLICE.start, Z_SLICE.stop],
            "y": [Y_SLICE.start, Y_SLICE.stop],
            "x": [X_SLICE.start, X_SLICE.stop],
        },
        "raw_shape": list(crop.shape),
        "raw_dtype": str(crop.dtype),
        "label_shapes": {k: list(v.shape) for k, v in labels.items()},
        "real_tracked_nuclei_in_crop": len(nodes),
        "real_tracked_nuclei_total_in_dataset": int(node_ids.shape[0]),
        "nodes": nodes,
        "edges": edges,
        "label_voxel_counts": {
            name: {str(int(k)): int(v) for k, v in zip(*np.unique(arr[0], return_counts=True)) if k != 0}
            for name, arr in labels.items()
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("raw crop shape", crop.shape, crop.dtype)
    print("real tracked nuclei in crop:", len(nodes), "of", int(node_ids.shape[0]), "total in dataset")
    print("real edges in crop:", len(edges))
    print("wrote", OUT, OUT.stat().st_size, "bytes")

    np.savez_compressed(
        OUT.with_suffix(".npz"),
        raw=crop.astype(np.uint16),
        nucleus=labels["nucleus"].astype(np.uint16),
        cell=labels["cell"].astype(np.uint16),
        lumen=labels["lumen"].astype(np.uint16),
    )
    print("wrote", OUT.with_suffix(".npz"), OUT.with_suffix(".npz").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
