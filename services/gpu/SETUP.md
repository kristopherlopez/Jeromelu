# Lineup on SageMaker Async — one-time setup

Phase 5.5 ships Lineup's GPU-bound steps (pyannote diarization +
InsightFace visual ID) as a SageMaker Async Inference endpoint, so the
audit loop drops from ~50 min CPU to ~10–15 min wall time.

This doc lists the **one-time AWS resources** you create before
the first `make lineup-build` / `make lineup-deploy`.

> Region: `ap-southeast-2` (Sydney). Matches the existing buckets so no
> cross-region S3 fees.

---

## 1 — ECR repository for the container image

```bash
aws ecr create-repository \
    --repository-name jeromelu/lineup-gpu \
    --region ap-southeast-2 \
    --image-scanning-configuration scanOnPush=true
```

Idempotent — re-running emits a "RepositoryAlreadyExists" error you can ignore.

## 2 — IAM role for SageMaker

The endpoint runs under an IAM role that needs S3 read on the audio
bucket, S3 read+write on the raw-transcripts bucket, ECR pull, and
CloudWatch logs.

### 2a. Trust policy (`trust-policy.json`)

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

### 2b. Inline policy (`lineup-policy.json`)

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
      "Sid": "ListBuckets",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::jeromelu-raw-audio",
        "arn:aws:s3:::jeromelu-raw-transcripts"
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

### 2c. Create the role + attach policy

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

Copy the ARN into project-root `.env`:

```dotenv
LINEUP_REMOTE=1
LINEUP_SAGEMAKER_ROLE_ARN=arn:aws:iam::<YOUR_ACCOUNT_ID>:role/JeromeluSagemakerLineup
```

## 3 — Local prerequisites

You need Docker BuildKit (default in modern Docker), AWS CLI authenticated
to your account, and Python deps in the API venv. The `boto3` client is
already pulled in by the existing `services/api/requirements.txt`.

## 4 — First build + deploy

```bash
# Build the GPU container and push to ECR. Pulls the AWS DLC PyTorch base
# image (~3 GB), bakes pyannote + InsightFace weights into the image, and
# pushes to your ECR repo.
make lineup-build

# Create / update the SageMaker model + endpoint config + endpoint, and
# wait for the endpoint to enter `InService`. First deployment takes
# ~5–10 min while SageMaker provisions the g4dn instance and pulls the
# image.
make lineup-deploy
```

After `make lineup-deploy` reports OK:

```bash
# Set LINEUP_REMOTE=1 in .env (one-time), then:
make transcribe SOURCE_ID=<uuid> FORCE=1
```

The CLI will print `[Lineup remote] diarize submitted → s3://…` and the
end-to-end run should complete in ~10–15 min instead of ~50 min.

## 5 — Tear down when not iterating

SageMaker Async charges only during inference seconds, so an idle endpoint
is free. But if you want to be clean:

```bash
make lineup-delete
```

This deletes the endpoint. The model + endpoint config remain (negligible
cost). To re-deploy, `make lineup-deploy` again.

## 6 — Iterating on the container

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

- **Per source:** ~$0.13 compute (10 min on `ml.g4dn.xlarge` at $0.736/hr).
- **Storage:** ECR ~$0.30/month for the 3 GB image. SageMaker model storage
  is a few cents.
- **Idle:** $0 on SageMaker Async (scale-to-zero).
- **Network:** S3 and SageMaker are in `ap-southeast-2`; data transfer is
  in-region (free).

## Troubleshooting

- `model_fn` failed during endpoint warmup → check
  `aws logs tail /aws/sagemaker/Endpoints/jeromelu-lineup-async --follow`
  for the Python traceback. Most common: missing HF token or expired
  ECR credentials during base-image pull.
- Endpoint stuck `Updating` for > 15 min → likely waiting on instance
  provisioning. Check the Service Quotas console for ml.g4dn.xlarge
  availability in `ap-southeast-2`.
- "AccessDenied: ListBucket" in the container logs → re-check the
  inline policy on `JeromeluSagemakerLineup` includes both buckets.
