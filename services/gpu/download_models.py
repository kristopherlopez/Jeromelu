"""Bake pyannote + InsightFace model weights into the Docker image.

Runs in the Dockerfile's model-downloader stage. Reads `HF_TOKEN` from
the environment (passed via Buildkit secret) and pulls every model the
inference container will need at runtime, so cold-start in production
doesn't pay the network round-trip.

Models downloaded:
  - pyannote/speaker-diarization-3.1   (pipeline config)
  - pyannote/segmentation-3.0          (~6 MB, segmentation model)
  - pyannote/wespeaker-voxceleb-resnet34-LM  (~30 MB, embedder)
  - insightface buffalo_l pack         (~280 MB, RetinaFace + ArcFace)
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
    if not token:
        print("ERROR: HF_TOKEN must be set as a build secret", file=sys.stderr)
        return 2

    print("[bake] Downloading pyannote speaker-diarization-3.1 …")
    from pyannote.audio import Pipeline
    Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=token,
    )
    # The pipeline pulls segmentation-3.0 and wespeaker-voxceleb-resnet34-LM
    # transitively, so the next two lines are belt-and-braces in case the
    # pipeline later only loads them on first inference.
    from pyannote.audio import Model
    print("[bake] Downloading pyannote segmentation-3.0 …")
    Model.from_pretrained("pyannote/segmentation-3.0", use_auth_token=token)
    print("[bake] Downloading pyannote wespeaker-voxceleb-resnet34-LM …")
    Model.from_pretrained(
        "pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=token,
    )

    print("[bake] Downloading InsightFace buffalo_l …")
    from insightface.app import FaceAnalysis
    fa = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))

    print("[bake] All models downloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
