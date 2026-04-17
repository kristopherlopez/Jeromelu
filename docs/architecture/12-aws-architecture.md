# AWS Artefacts Needed

This is the practical AWS shape for Jaromelu V1.

## Networking / Foundation

### VPC
Create one VPC with:
- 2 or 3 Availability Zones
- public subnets for edge-facing load balancers only
- private subnets for app services, workers, Temporal, and databases
- route tables and NAT where needed

### Security Groups
Create separate security groups for:
- load balancer
- web/api services
- worker services
- database
- cache if added later

### IAM Roles
At minimum:
- ECS task execution role
- ECS task role(s) for app/worker permissions
- CI/CD deploy role
- operator/admin access roles

## Compute / Containers

### Amazon ECS
Use Amazon ECS as the container orchestration layer. Amazon ECS is a fully managed container orchestration service, and AWS documents Fargate as the serverless option so you do not need to manage EC2 clusters.

Artifacts:
- ECS cluster
- ECS services for `web` and `api`
- ECS services or scheduled tasks for workers
- ECS task definitions for each service
- capacity provider / Fargate configuration

### AWS Fargate
Use Fargate for V1 so you avoid server management overhead. AWS documents that Fargate runs containers without managing EC2 instances.

## Container Registry

### Amazon ECR
Store Docker images for:
- web
- api
- worker-ingestion
- worker-extraction
- worker-decision
- worker-publishing

Artifacts:
- one ECR repository per service, or a small shared repo strategy
- lifecycle policies to clean old images

## Edge / Delivery

### Application Load Balancer
Use an ALB in public subnets for:
- Next.js app
- FastAPI backend
- routing by host/path if you keep them separate

### Amazon CloudFront
Use CloudFront in front of the public experience for caching and lower-latency delivery. AWS documents that CloudFront distributes static and dynamic content and can use S3 buckets or load balancers as origins.

Artifacts:
- CloudFront distribution
- origin for ALB
- optional origin for static assets bucket
- cache policies
- response headers policies

### Route 53
Artifacts:
- hosted zone
- DNS records for root domain and subdomains

### ACM (AWS Certificate Manager)
Artifacts:
- TLS certificates for domain and subdomains

## Data Layer

### Amazon RDS for PostgreSQL
Use RDS for PostgreSQL as the canonical database. AWS documents that RDS for PostgreSQL supports backups, point-in-time restore, Multi-AZ deployments, read replicas, and VPC deployment.

Artifacts:
- PostgreSQL instance or cluster
- parameter group
- subnet group
- automated backups
- secrets for credentials

Notes:
- confirm pgvector support for the chosen engine/version in your build plan
- start simple unless load proves otherwise

### Object Storage — Amazon S3
Use S3 for raw transcripts, cleaned documents, and artefacts. AWS documents S3 as object storage with buckets as the unit of storage.

Artifacts:
- `jeromelu-raw-transcripts`
- `jeromelu-clean-documents`
- `jeromelu-public-assets`
- lifecycle policies for archival / cleanup
- bucket policies
- versioning where appropriate

## Secrets / Configuration

### AWS Secrets Manager
Artifacts:
- database credentials
- OpenAI API key
- third-party source credentials if needed
- session/auth secrets

### AWS Systems Manager Parameter Store
Artifacts:
- non-secret config values
- feature flags
- environment settings

## Queues / Async Support

### Amazon SQS
Even if Temporal is your primary workflow engine, SQS is useful for decoupled asynchronous events and dead-letter handling.

Artifacts:
- optional ingestion queue
- optional publish queue
- dead-letter queues for failed jobs

## Observability / Operations

### Amazon CloudWatch
Artifacts:
- log groups for each ECS service
- metrics dashboards
- alarms on task failures, high latency, and DB stress

### AWS X-Ray or OpenTelemetry-compatible tracing path
If you want native AWS tracing, X-Ray is the obvious option. If not, send traces to your preferred platform.

### CloudTrail
Artifacts:
- account-level audit logging for AWS control-plane actions

## Access / Security

### AWS WAF
Recommended in front of CloudFront or ALB for basic protection.

Artifacts:
- web ACL
- managed rules
- rate limiting rules

### KMS
Artifacts:
- keys for encrypting S3, Secrets Manager, and possibly RDS

## CI/CD

### GitHub Actions or AWS-native pipeline
For AWS-native, the likely artefacts are:
- CodeBuild
- CodePipeline

But if you already prefer GitHub Actions, use that and deploy into ECS/ECR.

## Temporal Deployment Choices

### Option A — Temporal Cloud
Best if you want less operational drag.

AWS artefacts still needed:
- worker services on ECS
- outbound connectivity
- secrets for Temporal connection

### Option B — Self-hosted Temporal on AWS
Only do this if you actually want the operational burden.

Extra artefacts needed:
- Temporal server services
- persistence database(s)
- internal networking and service discovery
- monitoring and backups

For V1, Option A is cleaner.

## Recommended Minimum AWS Inventory

If you want the shortest realistic list, it is this:

- VPC
- public and private subnets
- security groups
- IAM roles
- ECR repositories
- ECS cluster
- ECS services and task definitions
- Fargate configuration
- ALB
- CloudFront distribution
- Route 53 records
- ACM certificates
- RDS for PostgreSQL
- S3 buckets
- Secrets Manager secrets
- Parameter Store entries
- CloudWatch log groups and alarms
- WAF web ACL
- KMS keys

## AWS Mapping By Jaromelu Container

### `web`
- ECS service on Fargate
- ALB target group
- CloudFront origin
- CloudWatch logs

### `api`
- ECS service on Fargate
- ALB target group
- Secrets Manager access
- RDS access
- S3 access
- CloudWatch logs

### `worker-ingestion`
- ECS service or scheduled ECS task on Fargate
- S3 write access
- RDS write access
- outbound internet/NAT access

### `worker-extraction`
- ECS service or worker task on Fargate
- RDS access
- S3 access
- outbound LLM API access

### `worker-decision`
- ECS service or worker task on Fargate
- RDS access
- Parameter Store / feature flag access

### `worker-publishing`
- ECS service or worker task on Fargate
- RDS access
- S3 access if publishing derived artefacts

### `postgres`
- Amazon RDS for PostgreSQL in private subnets

### `object-store`
- Amazon S3 buckets

## Practical Recommendation

For Jaromelu V1 on AWS, I would deploy:
- Next.js and FastAPI as containers on ECS Fargate
- worker services on ECS Fargate
- PostgreSQL on RDS
- transcript/artifact storage on S3
- CloudFront in front of the public app
- Route 53 + ACM for domain/TLS
- Secrets Manager for secrets
- CloudWatch for logs/alarms
- WAF for basic protection
- Temporal Cloud instead of self-hosting Temporal

That is the cleanest AWS shape for this project.
