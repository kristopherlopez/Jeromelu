"""Bake pyannote + InsightFace model weights into the Docker image.

Runs in the Dockerfile's model-downloader stage. Reads ``HF_TOKEN`` from
the environment (passed via Buildkit secret) and pulls every model the
inference container will need at runtime, so cold-start in production
doesn't pay the network round-trip.

Models downloaded:
  - pyannote/speaker-diarization-community-1   (pipeline config + segmentation)
  - pyannote/wespeaker-voxceleb-resnet34-LM    (~30 MB, embedder — still
                                                used by identify_voice.py
                                                for matching; pipeline-3.1
                                                used it too)
  - insightface buffalo_l pack                 (~280 MB, RetinaFace + ArcFace)

community-1 ships with its own pipeline-internal segmentation model; we
don't need to download segmentation-3.0 separately as we did under 3.1.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
    if not token:
        print("ERROR: HF_TOKEN must be set as a build secret", file=sys.stderr)
        return 2

    print("[bake] Downloading pyannote speaker-diarization-community-1 …")
    from pyannote.audio import Pipeline
    Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1",
        token=token,
    )

    # wespeaker is still our voice embedder — used by identify_voice.py
    # for matching. community-1 may or may not transitively pull this,
    # so download explicitly.
    from pyannote.audio import Model
    print("[bake] Downloading pyannote wespeaker-voxceleb-resnet34-LM …")
    Model.from_pretrained(
        "pyannote/wespeaker-voxceleb-resnet34-LM",
        token=token,
    )

    print("[bake] Downloading InsightFace buffalo_l …")
    from insightface.app import FaceAnalysis
    fa = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))

    print("[bake] All models downloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
