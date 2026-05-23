################################################################################
# S3 buckets
#
# - jeromelu-raw-transcripts : raw YouTube transcripts (versioned).
# - jeromelu-raw-audio       : raw audio (yt-dlp pulls), kept for re-transcription
#                              and voice fine-tuning. Versioned.
# - jeromelu-clean-documents : cleaned + processed docs and agent run logs.
# - jeromelu-public-assets   : site assets and nightly Postgres dumps.
#
# All four: ap-southeast-2, public access blocked, SSE-S3 (AES256).
# Only public-assets has a lifecycle rule (14-day expiry on backups/postgres/).
################################################################################

# ---- jeromelu-raw-transcripts ------------------------------------------------

resource "aws_s3_bucket" "raw_transcripts" {
  bucket = "jeromelu-raw-transcripts"
}

resource "aws_s3_bucket_versioning" "raw_transcripts" {
  bucket = aws_s3_bucket.raw_transcripts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_transcripts" {
  bucket = aws_s3_bucket.raw_transcripts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_transcripts" {
  bucket                  = aws_s3_bucket.raw_transcripts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---- jeromelu-raw-audio ------------------------------------------------------

resource "aws_s3_bucket" "raw_audio" {
  bucket = "jeromelu-raw-audio"
}

resource "aws_s3_bucket_versioning" "raw_audio" {
  bucket = aws_s3_bucket.raw_audio.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_audio" {
  bucket = aws_s3_bucket.raw_audio.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_audio" {
  bucket                  = aws_s3_bucket.raw_audio.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---- jeromelu-clean-documents ------------------------------------------------

resource "aws_s3_bucket" "clean_documents" {
  bucket = "jeromelu-clean-documents"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "clean_documents" {
  bucket = aws_s3_bucket.clean_documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "clean_documents" {
  bucket                  = aws_s3_bucket.clean_documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---- jeromelu-public-assets --------------------------------------------------

resource "aws_s3_bucket" "public_assets" {
  bucket = "jeromelu-public-assets"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "public_assets" {
  bucket = aws_s3_bucket.public_assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "public_assets" {
  bucket                  = aws_s3_bucket.public_assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "public_assets" {
  bucket = aws_s3_bucket.public_assets.id

  rule {
    id     = "expire-postgres-backups"
    status = "Enabled"

    filter {
      prefix = "backups/postgres/"
    }

    expiration {
      days = 14
    }
  }
}
