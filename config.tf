resource "aws_s3_bucket" "config" {
  bucket = "lambda-config-bucket"
}

resource "aws_s3_object" "config_file" {
  bucket = aws_s3_bucket.config.bucket
  key    = "config.json"
  source = "config.json"
}

resource "aws_lambda_function" "s3_copy" {
  function_name = "s3-subfolder-copy-lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      CONFIG_BUCKET = aws_s3_bucket.config.bucket
      CONFIG_KEY    = aws_s3_object.config_file.key
    }
  }
}
