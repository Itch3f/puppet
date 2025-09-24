locals {
  config   = jsondecode(file("config.json"))
  mappings = { for m in local.config.mappings : m.name => m }
}

# IAM Role (shared across all Lambdas)
resource "aws_iam_role" "lambda_role" {
  name = "s3-subfolder-copy-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Policies (shared)
resource "aws_iam_policy" "source_read" {
  name   = "lambda-source-read"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = ["s3:GetObject", "s3:ListBucket"],
      Resource = [
        "arn:aws:s3:::${local.config.source_bucket}",
        "arn:aws:s3:::${local.config.source_bucket}/*"
      ]
    }]
  })
}

resource "aws_iam_policy" "dest_rw" {
  name   = "lambda-dest-rw"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:PutObjectAcl"],
      Resource = [
        "arn:aws:s3:::${local.config.dest_bucket}",
        "arn:aws:s3:::${local.config.dest_bucket}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "source_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.source_read.arn
}

resource "aws_iam_role_policy_attachment" "dest_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.dest_rw.arn
}

# Lambda per mapping
resource "aws_lambda_function" "s3_copy" {
  for_each = local.mappings

  function_name = "s3-${each.key}-lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      SOURCE_BUCKET = local.config.source_bucket
      DEST_BUCKET   = local.config.dest_bucket
      SOURCE_PREFIX = each.value.source_prefix
      DEST_PREFIX   = each.value.dest_prefix
    }
  }
}

# Allow S3 to trigger Lambda
resource "aws_lambda_permission" "allow_s3" {
  for_each = local.mappings

  statement_id  = "AllowExecutionFromS3-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.s3_copy[each.key].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${local.config.source_bucket}"
}

# Event notification for each prefix
resource "aws_s3_bucket_notification" "source_notification" {
  bucket = local.config.source_bucket

  lambda_function {
    lambda_function_arn = aws_lambda_function.s3_copy[each.key].arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = each.value.source_prefix
  }

  depends_on = [aws_lambda_permission.allow_s3]
}
