# Jaromelu — AWS Infrastructure Setup Guide

**Purpose:** Step-by-step instructions for setting up all AWS resources needed for Jaromelu V1. Designed to be followed sequentially via the AWS Console.

**Project:** Jaromelu — Autonomous AI NRL SuperCoach character
**Region:** ap-southeast-2 (Sydney)
**Domain:** jeromelu.ai (currently registered with Namecheap)

---

## Pre-Flight Checklist

Before starting, confirm:

- [ ] Logged into the correct AWS account
- [ ] Region is set to **ap-southeast-2 (Sydney)** in the top-right corner
- [ ] You have admin-level IAM permissions
- [ ] The domain `jeromelu.ai` is accessible in your Namecheap account

---

## Phase 1 — Networking Foundation

### Step 1.1 — Create VPC

Navigate to: **VPC Console > Your VPCs > Create VPC**

Settings:

- **Resources to create:** VPC and more
- **Name tag auto-generation:** `jeromelu`
- **IPv4 CIDR block:** `10.0.0.0/16`
- **Number of Availability Zones:** 2
- **Number of public subnets:** 2
- **Number of private subnets:** 2
- **NAT gateways:** In 1 AZ (cost-saving for V1)
- **VPC endpoints:** S3 Gateway (free, saves NAT costs)

Click **Create VPC** and wait for all resources to provision.

Record these values after creation:

- VPC ID: \_\_\_
- Public subnet 1 ID: \_\_\_
- Public subnet 2 ID: \_\_\_
- Private subnet 1 ID: \_\_\_
- Private subnet 2 ID: \_\_\_

### Step 1.2 — Create Security Groups

Navigate to: **VPC Console > Security Groups > Create security group**

Create these four security groups inside the `jeromelu` VPC:

**1. `jeromelu-alb-sg`** (Load Balancer)

- Inbound: HTTP (80) from `0.0.0.0/0`, HTTPS (443) from `0.0.0.0/0`
- Outbound: All traffic

**2. `jeromelu-app-sg`** (Web + API services)

- Inbound: TCP 3000 from `jeromelu-alb-sg`, TCP 8000 from `jeromelu-alb-sg`
- Outbound: All traffic

**3. `jeromelu-worker-sg`** (Worker services)

- Inbound: None required
- Outbound: All traffic

**4. `jeromelu-db-sg`** (Database)

- Inbound: TCP 5432 from `jeromelu-app-sg`, TCP 5432 from `jeromelu-worker-sg`
- Outbound: None required (or restrict to VPC)

---

## Phase 2 — Domain, DNS & Certificates

### Step 2.1 — Create Route 53 Hosted Zone

Navigate to: **Route 53 Console > Hosted zones > Create hosted zone**

Settings:

- **Domain name:** `jeromelu.ai`
- **Type:** Public hosted zone

After creation, note the **4 NS (nameserver) records**. You will need these for Namecheap.

### Step 2.2 — Point Namecheap Domain to Route 53

Open a new tab and go to: **Namecheap > Domain List > jeromelu.ai > Manage**

1. Find the **Nameservers** section
2. Change the dropdown from "Namecheap BasicDNS" to **"Custom DNS"**
3. Enter all 4 Route 53 nameserver values (without trailing dots):
   - `ns-1048.awsdns-03.org`
   - `ns-372.awsdns-46.com`
   - `ns-1723.awsdns-23.co.uk`
   - `ns-858.awsdns-43.net`
4. Click the **green checkmark** to save

**Note:** DNS propagation can take up to 48 hours, but usually completes within 1-2 hours. You can continue with the remaining steps while this propagates.

### Step 2.3 — Request TLS Certificate (ACM)

Navigate to: **ACM Console > Request a certificate**

**Important:** For CloudFront, you must create this certificate in **us-east-1 (N. Virginia)**. Switch region temporarily.

Settings:

- **Certificate type:** Request a public certificate
- **Domain names:** Add both:
  - `jeromelu.ai`
  - `*.jeromelu.ai`
- **Validation method:** DNS validation

After requesting:

1. Click into the certificate
2. Click **Create records in Route 53** — this auto-creates the CNAME validation records
3. Wait for status to change from "Pending validation" to **"Issued"** (usually 5-30 minutes)

Now create a **second certificate** in **ap-southeast-2 (Sydney)** for the ALB:

- Same settings: `jeromelu.ai` and `*.jeromelu.ai`
- DNS validate via Route 53 (records may already exist from above)

Switch back to **ap-southeast-2** for all remaining steps.

---

## Phase 3 — Data Layer

### Step 3.1 — Create RDS PostgreSQL Instance

Navigate to: **RDS Console > Create database**

Settings:

- **Creation method:** Standard create
- **Engine:** PostgreSQL
- **Engine version:** 16.x (latest 16 — supports pgvector)
- **Templates:** Free tier (or Dev/Test for slightly more headroom)
- **DB instance identifier:** `jeromelu-db`
- **Master username:** `jeromelu_admin`
- **Credentials management:** Self managed — set a strong password and record it
- **DB instance class:** `db.t4g.micro` (V1 / cost-saving) or `db.t4g.small`
- **Storage type:** gp3, 20 GB, enable autoscaling with max 100 GB
- **VPC:** `jeromelu` VPC
- **Subnet group:** Create new — select both private subnets
- **Public access:** No
- **Security group:** `jeromelu-db-sg`
- **Initial database name:** `jeromelu`
- **Backup retention:** 7 days
- **Enable deletion protection:** Yes

Click **Create database**.

Record:

- RDS endpoint: \_\_\_
- Master password: \_\_\_ (store securely, will go into Secrets Manager next)

### Step 3.2 — Create S3 Buckets

Navigate to: **S3 Console > Create bucket**

Create three buckets (all in ap-southeast-2):

**1. `jeromelu-raw-transcripts`**

- Block all public access: Yes
- Versioning: Enabled
- Default encryption: SSE-S3

**2. `jeromelu-clean-documents`**

- Block all public access: Yes
- Versioning: Disabled
- Default encryption: SSE-S3

**3. `jeromelu-public-assets`**

- Block all public access: Yes (CloudFront will serve these)
- Versioning: Disabled
- Default encryption: SSE-S3

---

## Phase 4 — Secrets & Configuration

### Step 4.1 — Create Secrets in Secrets Manager

Navigate to: **Secrets Manager Console > Store a new secret**

**Secret 1: `jeromelu/db-credentials`**

- Secret type: Credentials for Amazon RDS database
- Username: `jeromelu_admin`
- Password: (the password you set in Step 3.1)
- Database: select `jeromelu-db`

**Secret 2: `jeromelu/openai-api-key`**

- Secret type: Other type of secret
- Key/value: `OPENAI_API_KEY` = (your OpenAI API key)

**Secret 3: `jeromelu/app-secrets`**

- Secret type: Other type of secret
- Key/value pairs:
  - `SESSION_SECRET` = (generate a random 64-char string)
  - `ADMIN_API_KEY` = (generate a random 64-char string)

### Step 4.2 — Create Parameter Store Entries

Navigate to: **Systems Manager Console > Parameter Store > Create parameter**

Create these parameters (all type `String`):

| Name                                  | Value                      |
| ------------------------------------- | -------------------------- |
| `/jeromelu/env`                       | `production`               |
| `/jeromelu/region`                    | `ap-southeast-2`           |
| `/jeromelu/db-name`                   | `jeromelu`                 |
| `/jeromelu/s3-raw-bucket`             | `jeromelu-raw-transcripts` |
| `/jeromelu/s3-clean-bucket`           | `jeromelu-clean-documents` |
| `/jeromelu/s3-assets-bucket`          | `jeromelu-public-assets`   |
| `/jeromelu/feature/chat-enabled`      | `true`                     |
| `/jeromelu/feature/contrarian-mode`   | `true`                     |
| `/jeromelu/feature/publishing-paused` | `false`                    |

---

## Phase 5 — Container Registry

### Step 5.1 — Create ECR Repositories

Navigate to: **ECR Console > Repositories > Create repository**

Create 6 private repositories:

1. `jeromelu/web`
2. `jeromelu/api`
3. `jeromelu/worker-ingestion`
4. `jeromelu/worker-extraction`
5. `jeromelu/worker-decision`
6. `jeromelu/worker-publishing`

For each:

- Visibility: Private
- Tag immutability: Enabled
- Image scanning: Enable on push

After creating all 6, add a **lifecycle policy** to each:

- Rule: Expire untagged images older than 14 days
- Rule: Keep only the last 10 tagged images

---

## Phase 6 — IAM Roles

### Step 6.1 — ECS Task Execution Role

Navigate to: **IAM Console > Roles > Create role**

**Role: `jeromelu-ecs-execution-role`**

- Description: `ECS task execution role for Jaromelu services. Allows ECS to pull container images, write logs, and read secrets/parameters at container startup.`
- Trusted entity type: **AWS service**
- Use case: **Elastic Container Service**
- Then select: **Elastic Container Service Task**
- Attach policies:
  - `AmazonECSTaskExecutionRolePolicy` (AWS managed)
- Add inline policy `jeromelu-execution-secrets`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:ap-southeast-2:111424988703:secret:jeromelu/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameters",
        "ssm:GetParameter",
        "ssm:GetParametersByPath"
      ],
      "Resource": "arn:aws:ssm:ap-southeast-2:111424988703:parameter/jeromelu/*"
    }
  ]
}
```

### Step 6.2 — ECS App Task Role

**Role: `jeromelu-app-task-role`**

- Description: `Runtime task role for Jaromelu application containers. Grants access to S3 buckets, Secrets Manager, Parameter Store, and CloudWatch Logs.`
- Trusted entity type: **AWS service**
- Use case: **Elastic Container Service**
- Then select: **Elastic Container Service Task**
- Add inline policy `jeromelu-app-permissions`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::jeromelu-raw-transcripts",
        "arn:aws:s3:::jeromelu-raw-transcripts/*",
        "arn:aws:s3:::jeromelu-clean-documents",
        "arn:aws:s3:::jeromelu-clean-documents/*",
        "arn:aws:s3:::jeromelu-public-assets",
        "arn:aws:s3:::jeromelu-public-assets/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:ap-southeast-2:111424988703:secret:jeromelu/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameters",
        "ssm:GetParameter",
        "ssm:GetParametersByPath"
      ],
      "Resource": "arn:aws:ssm:ap-southeast-2:111424988703:parameter/jeromelu/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:ap-southeast-2:111424988703:log-group:/ecs/jeromelu/*"
    }
  ]
}
```

### Step 6.3 — CI/CD Deploy Role (for GitHub Actions)

**Role: `jeromelu-cicd-deploy-role`** — *Skip for now, set up when configuring GitHub Actions*

- Trusted entity type: **Web identity**
- Identity provider: **GitHub OIDC provider** (must be configured in IAM first)
- Attach policies:
  - `AmazonEC2ContainerRegistryPowerUser`
- Add inline policy for ECS deploy permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "iam:PassRole"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Phase 7 — ECS Cluster & Services

### Step 7.1 — Create ECS Cluster

**Important:** Confirm you are in **ap-southeast-2 (Sydney)** — you may still be in us-east-1 from the ACM certificate step.

Navigate to: **ECS Console > Clusters > Create cluster**

Settings:

- **Cluster name:** `jeromelu`
- **Infrastructure:** AWS Fargate (serverless)

### Step 7.2 — Create CloudWatch Log Groups

Navigate to: **CloudWatch Console > Log groups > Create log group**

Create these log groups:

1. `/ecs/jeromelu/web`
2. `/ecs/jeromelu/api`
3. `/ecs/jeromelu/worker-ingestion`
4. `/ecs/jeromelu/worker-extraction`
5. `/ecs/jeromelu/worker-decision`
6. `/ecs/jeromelu/worker-publishing`

For each: set retention to **30 days**.

### Step 7.3 — Create Application Load Balancer

Navigate to: **EC2 Console > Load Balancers > Create Load Balancer > Application Load Balancer**

Settings:

- **Name:** `jeromelu-alb`
- **Scheme:** Internet-facing
- **IP address type:** IPv4
- **VPC:** `jeromelu` VPC
- **Mappings:** Select both public subnets
- **Security group:** `jeromelu-alb-sg`
- **Listeners:**
  - HTTP:80 — default action: redirect to HTTPS:443
  - HTTPS:443 — default action: return fixed 503 (will configure targets later)
  - Certificate: select the **ap-southeast-2** ACM certificate for `jeromelu.ai`

Create two **target groups** (before or after ALB creation):

**1. `jeromelu-web-tg`**

- Target type: **IP addresses** (required for Fargate — tasks register by private IP)
- IP address type: **IPv4**
- Protocol: **HTTP**
- Port: **3000**
- Protocol version: **HTTP1**
- VPC: `jeromelu` VPC
- Health check path: `/`
- Do not register any IP targets now — ECS will register them automatically when services are created

**2. `jeromelu-api-tg`**

- Target type: **IP addresses** (required for Fargate — tasks register by private IP)
- IP address type: **IPv4**
- Protocol: **HTTP**
- Port: **8000**
- Protocol version: **HTTP1**
- VPC: `jeromelu` VPC
- Health check path: `/health`
- Do not register any IP targets now — ECS will register them automatically when services are created

After ALB creation, add **listener rules** on the HTTPS:443 listener:

- If host is `api.jeromelu.ai` -> forward to `jeromelu-api-tg`
- Default -> forward to `jeromelu-web-tg`

Record:

- ALB DNS name: \_\_\_
- ALB hosted zone ID: \_\_\_

### Step 7.4 — Create ECS Task Definitions

Navigate to: **ECS Console > Task definitions > Create new task definition**

Create placeholder task definitions for each service. These will be updated by CI/CD once Docker images are pushed. Repeat the following process 6 times.

Common settings for all 6:
- **Launch type:** AWS Fargate
- **OS/Arch:** Linux/X86_64
- **Task size:** 0.5 vCPU, 1 GB memory
- **Task execution role:** `jeromelu-ecs-execution-role`
- **Task role:** `jeromelu-app-task-role`
- **Essential container:** Yes (each task has one container — it must be essential)
- **Log driver:** awslogs
- **Log region:** `ap-southeast-2`
- **Log stream prefix:** `ecs`

---

**Task Definition 1: `jeromelu-web`**

- Task definition family: `jeromelu-web`
- Container name: `web`
- Image URI: `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/web:latest`
- Port mappings: **3000** (TCP)
- Port name: leave blank
- App protocol: **HTTP**
- Log group: `/ecs/jeromelu/web`

---

**Task Definition 2: `jeromelu-api`**

- Task definition family: `jeromelu-api`
- Container name: `api`
- Image URI: `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/api:latest`
- Port mappings: **8000** (TCP)
- Port name: leave blank
- App protocol: **HTTP**
- Log group: `/ecs/jeromelu/api`

---

**Task Definition 3: `jeromelu-worker-ingestion`**

- Task definition family: `jeromelu-worker-ingestion`
- Container name: `worker-ingestion`
- Image URI: `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/worker-ingestion:latest`
- Port mappings: **none**
- Log group: `/ecs/jeromelu/worker-ingestion`

---

**Task Definition 4: `jeromelu-worker-extraction`**

- Task definition family: `jeromelu-worker-extraction`
- Container name: `worker-extraction`
- Image URI: `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/worker-extraction:latest`
- Port mappings: **none**
- Log group: `/ecs/jeromelu/worker-extraction`

---

**Task Definition 5: `jeromelu-worker-decision`**

- Task definition family: `jeromelu-worker-decision`
- Container name: `worker-decision`
- Image URI: `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/worker-decision:latest`
- Port mappings: **none**
- Log group: `/ecs/jeromelu/worker-decision`

---

**Task Definition 6: `jeromelu-worker-publishing`**

- Task definition family: `jeromelu-worker-publishing`
- Container name: `worker-publishing`
- Image URI: `111424988703.dkr.ecr.ap-southeast-2.amazonaws.com/jeromelu/worker-publishing:latest`
- Port mappings: **none**
- Log group: `/ecs/jeromelu/worker-publishing`

### Step 7.5 — Create ECS Services

Navigate to: **ECS Console > Clusters > jeromelu > Create service**

**Service 1: `jeromelu-web`**

- Service name: `jeromelu-web`
- Task definition family: `jeromelu-web`
- Task definition revision: `1 (LATEST)`
- Scheduling strategy: **Replica**
- Compute configuration: **Launch type — Fargate**
- Platform version: **LATEST**
- Desired tasks: 1
- VPC: `jeromelu` VPC, **private subnets only** (deselect public)
- Public IP: **Off**
- Security group: `jeromelu-app-sg` (remove default SG)
- Load balancer: **Use an existing load balancer** — select `jeromelu-alb`, HTTPS:443 listener, target group `jeromelu-web-tg`, container `web:3000`
- Service Connect: **Off**
- Service Discovery: **Off**

**Service 2: `jeromelu-api`**

- Service name: `jeromelu-api`
- Task definition family: `jeromelu-api`
- Task definition revision: `1 (LATEST)`
- Scheduling strategy: **Replica**
- Compute configuration: **Launch type — Fargate**
- Platform version: **LATEST**
- Desired tasks: 1
- VPC: `jeromelu` VPC, **private subnets only** (deselect public)
- Public IP: **Off**
- Security group: `jeromelu-app-sg` (remove default SG)
- Load balancer: **Use an existing load balancer** — select `jeromelu-alb`, HTTPS:443 listener, target group `jeromelu-api-tg`, container `api:8000`
- Service Connect: **Off**
- Service Discovery: **Off**

**Services 3-6: Workers** (`worker-ingestion`, `worker-extraction`, `worker-decision`, `worker-publishing`)

- Service name: `jeromelu-{worker-name}` (e.g. `jeromelu-worker-ingestion`)
- Task definition family: matching worker name
- Task definition revision: `1 (LATEST)`
- Scheduling strategy: **Replica**
- Compute configuration: **Launch type — Fargate**
- Platform version: **LATEST**
- Desired tasks: **0** (set to 0 until Docker images are pushed)
- VPC: `jeromelu` VPC, **private subnets only** (deselect public)
- Public IP: **Off**
- Security group: `jeromelu-worker-sg` (remove default SG)
- No load balancer
- Service Connect: **Off**
- Service Discovery: **Off**

---

## Phase 8 — CloudFront Distribution

Navigate to: **CloudFront Console > Create distribution**

### Wizard Step 1 — Choose a plan

- Select **Free** (limited to 3 distributions per account — sufficient for V1)

### Wizard Step 2 — Get started

- **Distribution name:** `jeromelu`
- **Description:** `Jaromelu public experience`
- **Distribution type:** Website
- **Route 53 domain:** Select `jeromelu.ai` (links hosted zone to the free plan — includes Route 53 costs)

### Wizard Step 3 — Specify origin

- **Origin type:** Elastic Load Balancer — select `jeromelu-alb`
- **Use recommended origin settings:** Yes
- **Cache policy:** Change from `UseOriginCacheControlHeaders` to **CachingDisabled** (for V1 — all requests pass through to ALB)
- **Origin request policy:** **AllViewer** (forwards Host header to ALB — required for subdomain routing)

### Wizard Step 4 — Enable security (WAF)

This replaces Phase 9 Step 9.1 — WAF is included in the free plan (up to 5 rules).

- **Included security protections:** leave enabled
- **Monitor mode:** **Off** (block traffic, not just count)
- **Rate limiting:** **Enable** — change from 300 to **2000** requests per IP per 5 minutes
- **SQL protections:** not available on free plan, skip

### Wizard Step 5 — Get TLS certificate

- Select the existing certificate: **jeromelu.ai (361488ce-fcf5-46ed-8f98-ab25d21c7f0e)** from us-east-1
- Do not create a new one — this was already created in Phase 2 Step 2.3

Click **Create distribution** and wait for it to deploy (can take a few minutes).

Record:

- CloudFront distribution ID: \_\_\_
- CloudFront distribution domain: \_\_\_

---

## Phase 9 — Security

### Step 9.1 — WAF Web ACL

**Handled during Phase 8 CloudFront setup** — WAF is enabled as part of the CloudFront free plan wizard (Step 4: Enable security). Up to 5 rules included in the free plan.

If you need to add custom rules later (e.g. rate limiting), go to **WAF Console > Web ACLs** and edit the auto-created ACL.

### Step 9.2 — Create KMS Key

Navigate to: **KMS Console > Customer managed keys > Create key**

**Step 1 — Configure key:**
- **Key type:** Symmetric
- **Key usage:** Encrypt and decrypt
- **Key material origin:** KMS (recommended)
- **Regionality:** Single-region key

**Step 2 — Add labels:**
- **Alias:** `jeromelu-master-key`

**Step 3 — Define key administrative permissions:**
- **Key administrators:** Your IAM user/role

**Step 4 — Define key usage permissions:**
- **Key users:** Select `jeromelu-ecs-execution-role` and `jeromelu-app-task-role`

---

## Phase 10 — DNS Records

Navigate to: **Route 53 Console > Hosted zones > jeromelu.ai**

Create these records:

**1. Root domain → CloudFront**

- Record name: (leave empty — this creates the root `jeromelu.ai` record)
- Record type: A
- Alias: Yes
- Route traffic to: **Alias to CloudFront distribution** → select `d2rchevv847e7k.cloudfront.net`
- Routing policy: **Simple routing**

**2. www → CloudFront**

- Record name: `www`
- Record type: A
- Alias: Yes
- Route traffic to: **Alias to CloudFront distribution** → if dropdown is empty, type `d2rchevv847e7k.cloudfront.net` manually
- Routing policy: **Simple routing**

**3. API subdomain → ALB**

- Record name: `api`
- Record type: A
- Alias: Yes
- Route traffic to: **Alias to Application and Classic Load Balancer** → ap-southeast-2 → select `jeromelu-alb`
- Routing policy: **Simple routing**

---

## Phase 11 — Observability

### Step 11.1 — Create CloudWatch Dashboard

Navigate to: **CloudWatch Console > Dashboards > Create dashboard**

- **Name:** `jeromelu-operations`

Add the following widgets:

**Widget 1 — ECS CPU Utilisation**
- Type: Line chart
- Metric: ECS > ClusterName, ServiceName > CPUUtilization
- Add all 6 services:
  - `jeromelu-web`
  - `jeromelu-api`
  - `jeromelu-worker-ingestion`
  - `jeromelu-worker-extraction`
  - `jeromelu-worker-decision`
  - `jeromelu-worker-publishing`

**Widget 2 — ECS Memory Utilisation**
- Type: Line chart
- Metric: ECS > ClusterName, ServiceName > MemoryUtilization
- Add all 6 services (same as above)

**Widget 3 — RDS Database**
- Type: Line chart
- Metric: RDS > Per-Database Metrics > `jeromelu-db`
- Add: `CPUUtilization`, `DatabaseConnections`, `FreeStorageSpace`

**Widget 4 — ALB Requests & Errors**
- Type: Line chart
- Metric: ApplicationELB > Per AppELB Metrics > `jeromelu-alb`
- Add: `RequestCount`, `HTTPCode_ELB_5XX_Count`, `HTTPCode_Target_5XX_Count`

**Widget 5 — CloudFront**
- Type: Line chart
- Metric: CloudFront > Per-Distribution Metrics > `E2G6FL11A3JP8F`
- Add: `Requests`, `TotalErrorRate`

### Step 11.2 — Create CloudWatch Alarms

Navigate to: **CloudWatch Console > Alarms > Create alarm**

Create these alarms:

| Alarm                     | Metric                          | Threshold           |
| ------------------------- | ------------------------------- | ------------------- |
| `jeromelu-db-cpu-high`    | RDS CPUUtilization              | > 80% for 5 minutes |
| `jeromelu-db-storage-low` | RDS FreeStorageSpace            | < 5 GB              |
| `jeromelu-alb-5xx`        | ALB HTTPCode_ELB_5XX_Count      | > 10 in 5 minutes   |
| `jeromelu-web-unhealthy`  | ALB UnHealthyHostCount (web TG) | > 0 for 3 minutes   |
| `jeromelu-api-unhealthy`  | ALB UnHealthyHostCount (api TG) | > 0 for 3 minutes   |

### Step 11.3 — Enable CloudTrail

Navigate to: **CloudTrail Console > Create trail**

- **Trail name:** `jeromelu-audit`
- **Storage location:** Create new S3 bucket `jeromelu-cloudtrail-logs`
- **Log events:** Management events (read + write)

---

## Phase 12 — SQS Queues (Optional, for later)

Navigate to: **SQS Console > Create queue**

Create when needed:

**1. `jeromelu-ingestion-queue`**

- Type: Standard
- Visibility timeout: 300 seconds
- Message retention: 4 days

**2. `jeromelu-ingestion-dlq`**

- Type: Standard
- Message retention: 14 days
- Set as dead-letter queue for `jeromelu-ingestion-queue` (max receives: 3)

**3. `jeromelu-publish-queue`**

- Type: Standard
- Visibility timeout: 60 seconds

**4. `jeromelu-publish-dlq`**

- Type: Standard
- Set as dead-letter queue for `jeromelu-publish-queue`

---

## Verification Checklist

### Completed

- [x] VPC with 2 public + 2 private subnets exists
- [x] 4 security groups created with correct rules
- [x] Route 53 hosted zone exists with NS records pointing from Namecheap
- [x] ACM certificates issued (us-east-1 for CloudFront, ap-southeast-2 for ALB)
- [x] RDS PostgreSQL instance running in private subnets
- [x] 3 S3 buckets created
- [x] Secrets Manager has 3 secrets
- [x] Parameter Store has all config entries
- [x] 6 ECR repositories created with lifecycle policies
- [x] IAM roles created (execution, task — CI/CD deferred)
- [x] ECS cluster `jeromelu` exists
- [x] 6 CloudWatch log groups created
- [x] ALB with HTTPS listener and 2 target groups
- [x] 6 ECS task definitions registered
- [x] `web` and `api` ECS services created (tasks will fail until images are pushed)
- [x] CloudFront distribution active with ACM certificate
- [x] WAF enabled via CloudFront free plan
- [x] KMS key created
- [x] DNS records: root + www -> CloudFront, api -> ALB

### Deferred — Do After Services Are Running

- [ ] CloudWatch dashboard with ECS/ALB/CloudFront/RDS widgets
- [ ] CloudWatch alarms (DB CPU, DB storage, ALB 5xx, unhealthy targets)
- [ ] CloudTrail audit trail
- [ ] SQS queues (optional, when needed)
- [ ] CI/CD deploy role (when configuring GitHub Actions)
- [ ] `https://jeromelu.ai` resolves (confirms full chain works — verify after pushing Docker images)

---

## Cost Estimate (V1 Idle / Low Traffic)

| Service                              | Estimated Monthly |
| ------------------------------------ | ----------------- |
| ECS Fargate (2 tasks, 0.5 vCPU each) | ~$30              |
| RDS db.t4g.micro                     | ~$15              |
| NAT Gateway                          | ~$35              |
| ALB                                  | ~$18              |
| CloudFront                           | ~$1               |
| S3                                   | ~$1               |
| Route 53                             | ~$0.50            |
| Secrets Manager                      | ~$2               |
| WAF                                  | ~$6               |
| **Total (idle)**                     | **~$110/month**   |

Workers at 0 desired tasks cost nothing. Scale up as needed.

---

## Next Steps After Infrastructure

1. Push Docker images to ECR repositories
2. Scale worker ECS services to desired count
3. Connect to RDS and run database migrations (create tables, enable pgvector extension)
4. Configure Temporal Cloud and connect worker services
5. Verify end-to-end: domain -> CloudFront -> ALB -> ECS -> RDS
