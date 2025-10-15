provider "aws" {
  region = var.region
}

##############################################
# Security Groups for EMR Studio & Serverless
##############################################
resource "aws_security_group" "emr_studio_engine" {
  name        = "${var.project}-emr-studio-engine-sg"
  description = "Security group for EMR Studio engine"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "emr_studio_workspace" {
  name        = "${var.project}-emr-studio-workspace-sg"
  description = "Security group for EMR Studio workspace"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "emr_serverless" {
  name        = "${var.project}-emr-serverless-sg"
  description = "Security group for EMR Serverless"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

##############################################
# IAM Roles
##############################################
# EMR Studio Service Role
resource "aws_iam_role" "emr_studio_service_role" {
  name = "${var.project}-emr-studio-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "elasticmapreduce.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "emr_studio_service_policy" {
  role = aws_iam_role.emr_studio_service_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "elasticmapreduce:ListClusters",
          "elasticmapreduce:DescribeCluster",
          "elasticmapreduce:ListSteps",
          "elasticmapreduce:DescribeStep",
          "emr-serverless:*",
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "logs:*"
        ],
        Resource = "*"
      }
    ]
  })
}

##############################################
# EMR Studio
##############################################
resource "aws_emr_studio" "studio" {
  name                        = "${var.project}-emr-studio"
  auth_mode                   = "IAM"
  subnet_ids                  = var.subnet_ids
  engine_security_group_id    = aws_security_group.emr_studio_engine.id
  workspace_security_group_id = aws_security_group.emr_studio_workspace.id
  vpc_id                      = var.vpc_id
  service_role                = aws_iam_role.emr_studio_service_role.arn
  default_s3_location         = var.default_s3_location
  tags                        = var.tags
}

##############################################
# EMR Serverless Application
##############################################
resource "aws_emrserverless_application" "spark_app" {
  name          = "${var.project}-spark-serverless"
  release_label = var.release_label
  type          = "SPARK"

  network_configuration {
    subnet_ids        = var.subnet_ids
    security_group_ids = [aws_security_group.emr_serverless.id]
  }

  initial_capacity {
    initial_capacity_type = "Driver"
    initial_capacity_config {
      worker_count = 1
      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
      }
    }
  }

  initial_capacity {
    initial_capacity_type = "Executor"
    initial_capacity_config {
      worker_count = 2
      worker_configuration {
        cpu    = "4 vCPU"
        memory = "8 GB"
      }
    }
  }

  maximum_capacity {
    cpu    = "20 vCPU"
    memory = "80 GB"
  }

  tags = var.tags
}
