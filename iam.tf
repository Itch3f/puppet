locals {
  config = jsondecode(file("config.json"))
}

# Source read-only
resource "aws_iam_policy" "source_read" {
  name   = "lambda-source-read"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${local.config.source_bucket}",
          "arn:aws:s3:::${local.config.source_bucket}/*"
        ]
      }
    ]
  })
}

# Destination read/write
resource "aws_iam_policy" "dest_rw" {
  name   = "lambda-dest-rw"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:PutObjectAcl"]
        Resource = [
          "arn:aws:s3:::${local.config.dest_bucket}",
          "arn:aws:s3:::${local.config.dest_bucket}/*"
        ]
      }
    ]
  })
}
