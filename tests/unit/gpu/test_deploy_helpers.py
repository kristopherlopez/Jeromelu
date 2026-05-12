"""Unit tests for services.gpu.deploy pure constructors.

Covers ECR image-uri formatting and SageMaker model/config name derivation.
The boto3-driven create/update flow needs LocalStack or moto and lives in
integration/ if it ever lands.
"""

import sys
from pathlib import Path

import pytest

# services/gpu isn't on the default pythonpath (it's a deploy script, not a
# package). Splice it in for this test file only.
GPU_DIR = Path(__file__).resolve().parents[3] / "services" / "gpu"
sys.path.insert(0, str(GPU_DIR))

from deploy import _config_name, _image_uri, _model_name  # noqa: E402


# ---------------------------------------------------------------------------
# _image_uri
# ---------------------------------------------------------------------------

class TestImageUri:
    def test_canonical_format(self):
        uri = _image_uri(
            account="123456789012",
            region="ap-southeast-2",
            repo="jeromelu/lineup-gpu",
            tag="v3",
        )
        assert uri == "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/lineup-gpu:v3"

    def test_default_tag_is_latest(self):
        uri = _image_uri(account="123", region="us-east-1", repo="foo/bar")
        assert uri.endswith(":latest")

    def test_account_and_region_pinned_in_host(self):
        uri = _image_uri("999", "eu-west-1", "x/y", "t")
        # The ECR host must encode both account and region — a swap or
        # missing segment would produce an unreachable hostname.
        assert "999.dkr.ecr.eu-west-1.amazonaws.com" in uri

    def test_repo_with_slashes_preserved(self):
        # ECR allows nested repo paths — they must survive verbatim.
        uri = _image_uri("1", "r", "team/sub/repo", "tag")
        assert "/team/sub/repo:tag" in uri


# ---------------------------------------------------------------------------
# _model_name and _config_name
# ---------------------------------------------------------------------------

class TestModelName:
    def test_combines_endpoint_and_tag(self):
        assert _model_name("jeromelu-lineup-async", "v3") == "jeromelu-lineup-async-v3"

    def test_each_tag_yields_distinct_name(self):
        # The whole point of putting the tag in the name is so SageMaker
        # can keep one model per image tag. Two distinct tags must give
        # two distinct names.
        a = _model_name("ep", "v1")
        b = _model_name("ep", "v2")
        assert a != b


class TestConfigName:
    def test_combines_endpoint_and_tag_with_cfg_marker(self):
        # The 'cfg' segment makes endpoint-config rows visually distinct
        # from model rows in the SageMaker console.
        assert _config_name("jeromelu-lineup-async", "v3") == "jeromelu-lineup-async-cfg-v3-g4dn"

    def test_does_not_collide_with_model_name(self):
        endpoint, tag = "ep", "v1"
        assert _model_name(endpoint, tag) != _config_name(endpoint, tag)
