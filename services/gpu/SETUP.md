# Lineup on SageMaker Async — one-time setup

Phase 5.5 ships Lineup's GPU-bound steps (pyannote diarization +
InsightFace visual ID) as a SageMaker Async Inference endpoint, so the
audit loop drops from ~50 min CPU to ~3 min wall time end-to-end.

This doc lists the **one-time AWS resources** you create before
the first `make lineup-build` / `make lineup-deploy`. The dynamic
resources (SageMaker model, endpoint config, endpoint) are managed
by `services/gpu/deploy.py` and are *not* covered here.

> **Regions split.** SageMaker endpoint runs in `us-east-1` (capacity is
> tight in Sydney for both `ml.g4dn` and `ml.g5` families). The artefact
> buckets stay in `ap-southeast-2`. A small staging bucket in `us-east-1`
> bridges SageMaker's internal async I/O — the per-source cross-region
> S3 transfer cost is negligible (~$0.001/source). To run end-to-end in
> Sydney instead, see [§ 6 — Region migration](#6--region-migration).

---

## 1 — ECR repository for the container image

```bash
aws ecr create-repository \
    --repository-name jeromelu/lineup-gpu \
    --region us-east-1 \
    --image-scanning-configuration scanOnPush=true
```

Idempotent — re-running emits a "RepositoryAlreadyExists" error you can
ignore.

## 2 — Staging bucket for SageMaker async I/O

SageMaker Async requires its input + output S3 paths to be in the same
region as the endpoint. Audio + transcripts live in Sydney; the endpoint
runs in us-east-1. This bucket exists only to carry small invoke
request/response JSONs.

```bash
aws s3api create-bucket \
    --bucket jeromelu-sagemaker-async \
    --region us-east-1
```

## 3 — IAM role for SageMaker

IAM roles are global (account-scoped, not regional), so the role you
create here works regardless of which region the endpoint ends up in.

The role needs S3 read on the audio bucket, S3 read+write on the
raw-transcripts bucket, S3 read+write on the staging bucket, ECR pull,
and CloudWatch logs.

### 3a. Trust policy (`trust-policy.json`)

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "sagemaker.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

### 3b. Inline policy (`lineup-policy.json`)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadAudio",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::jeromelu-raw-audio/*"]
    },
    {
      "Sid": "ReadWriteRawTranscripts",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::jeromelu-raw-transcripts/*"]
    },
    {
      "Sid": "ReadWriteSagemakerStaging",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::jeromelu-sagemaker-async/*"]
    },
    {
      "Sid": "ListBuckets",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::jeromelu-raw-audio",
        "arn:aws:s3:::jeromelu-raw-transcripts",
        "arn:aws:s3:::jeromelu-sagemaker-async"
      ]
    },
    {
      "Sid": "PullContainerImage",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:CreateLogGroup",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
    }
  ]
}
```

### 3c. Create the role + attach policy

```bash
aws iam create-role \
    --role-name JeromeluSagemakerLineup \
    --assume-role-policy-document file://trust-policy.json

aws iam put-role-policy \
    --role-name JeromeluSagemakerLineup \
    --policy-name JeromeluSagemakerLineupInline \
    --policy-document file://lineup-policy.json

# Print the ARN so you can drop it in `.env`:
aws iam get-role --role-name JeromeluSagemakerLineup --query Role.Arn --output text
```

> **Pending follow-up:** these three resources (ECR repo, staging bucket,
> IAM role) belong in `infra/terraform/` for consistency with the rest
> of the project. Tracked in
> [docs/todo/speaker-identification-plan.md](../../docs/todo/speaker-identification-plan.md).

Copy the ARN into project-root `.env`:

```dotenv
LINEUP_REMOTE=1
LINEUP_SAGEMAKER_ROLE_ARN=arn:aws:iam::<YOUR_ACCOUNT_ID>:role/JeromeluSagemakerLineup
```

## 4 — Local prerequisites

You need Docker BuildKit (default in modern Docker), AWS CLI authenticated
to your account, and Python deps in the API venv. The `boto3` client is
already pulled in by the existing `services/api/requirements.txt`.

## 5 — First build + deploy

```bash
# Build the GPU container and push to us-east-1 ECR. Pulls the AWS DLC
# PyTorch base image (~3 GB), bakes pyannote + InsightFace weights into
# the image, and pushes to your ECR repo. ~10–12 min on first run; ~3
# min on subsequent rebuilds (Docker layer cache).
make lineup-build

# Create / update the SageMaker model + endpoint config + endpoint, and
# wait for the endpoint to enter `InService`. First deployment takes
# ~5–10 min while SageMaker provisions the g4dn.xlarge instance and pulls
# the image.
make lineup-deploy
```

After `make lineup-deploy` reports OK:

```bash
# Set LINEUP_REMOTE=1 in .env (one-time), then:
make transcribe SOURCE_ID=<uuid> FORCE=1
```

The CLI prints `[Lineup remote] diarize submitted → s3://…` and the
end-to-end run completes in ~3 min instead of ~50 min.

## 6 — Region migration

If you want to move the endpoint to a different region (e.g. when Sydney
g5 capacity returns), the steps are:

1. Create the ECR repo (§ 1) and staging bucket (§ 2) in the new region.
2. Update the inline IAM policy (§ 3b) if your new staging bucket has a
   different name. The trust policy stays the same — IAM is global.
3. Update `lineup_aws_region` (and `lineup_staging_bucket` if renamed) in
   `packages/shared/jeromelu_shared/config.py` defaults, or override via
   `.env`.
4. `make lineup-build && make lineup-deploy`. The previous region's
   resources can be deleted with `make lineup-delete` then manual ECR
   `delete-repository` once empty.

## 7 — Tear down when not iterating

SageMaker Async charges only during inference seconds, so an idle endpoint
is free. But if you want to be clean:

```bash
make lineup-delete
```

This deletes the endpoint. The model + endpoint config remain (negligible
cost). To re-deploy, `make lineup-deploy` again.

## 8 — Iterating on the container

When you change Python code in `services/api/app/analyst/` or
`services/gpu/inference.py`:

```bash
# Rebuild + push (use a new tag to force re-pull on the endpoint side):
make lineup-build TAG=v2
make lineup-deploy TAG=v2
```

The deploy is a rolling update — SageMaker spins up a new instance with
the new image, then drains the old one. No request loss.

## Cost notes

- **Per source:** ~$0.10 GPU compute (~7-8 min on `ml.g4dn.xlarge` at $0.736/hr)
  + ~$0.001 cross-region S3 transfer + $0.30 Deepgram = **~$0.40/source**.
- **Storage:** ECR ~$0.30/month for the 3 GB image. SageMaker model
  storage is a few cents. Staging bucket is empty between runs.
- **Idle:** $0 on SageMaker Async (scale-to-zero).

## Troubleshooting

- `model_fn` failed during endpoint warmup → check
  `aws logs tail /aws/sagemaker/Endpoints/jeromelu-lineup-async --follow --region us-east-1`
  for the Python traceback.
- Endpoint stuck `Updating` for > 15 min → likely waiting on instance
  provisioning. Check the Service Quotas console for `ml.g4dn.xlarge`
  availability in `us-east-1`.
- Endpoint goes `Failed` with "InsufficientInstanceCapacity" → AWS is
  out of `ml.g4dn.xlarge` in this region right now. Try a different region
  per § 6, or wait an hour and redeploy.
- "AccessDenied" in container logs touching the staging bucket → re-check
  the inline policy on `JeromeluSagemakerLineup` includes
  `jeromelu-sagemaker-async`.
- Pyannote returned in seconds but visual_id timed out at 20 min →
  InsightFace is running on CPU inside the GPU container. The fix is
  in `visual_id.py:_get_face_app` — providers list is auto-detected via
  `onnxruntime.get_available_providers()`. If you see this after a code
  change, verify `onnxruntime-gpu` is in `services/gpu/requirements.txt`
  (not plain `onnxruntime`).
