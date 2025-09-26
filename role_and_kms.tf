# Lambda execution role
resource "aws_iam_role" "lambda_role" {
  name = "s3-subfolder-copy-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

# Attach CloudWatch Logs permissions (best practice)
resource "aws_iam_role_policy_attachment" "logs_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Allow Lambda to decrypt from KMS
resource "aws_iam_policy" "kms_source_access" {
  name   = "lambda-kms-source-access"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ],
        Resource = aws_kms_key.source_key.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "kms_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.kms_source_access.arn
}
