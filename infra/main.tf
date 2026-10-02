terraform {
  required_version = ">= 1.5"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.0" }
  }
}

variable "region" { default = "eu-west-1" }
variable "alert_email" {
  description = "Gets a mail at 80% of the monthly budget (confirm the AWS subscription)"
  type        = string
}
variable "monthly_budget_usd" { default = "10" }
variable "bedrock_model" { default = "eu.anthropic.claude-haiku-4-5-20251001-v1:0" }
variable "name" { default = "agentic-rag" }

provider "aws" { region = var.region }

resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "aws_ecr_repository" "repo" {
  name         = var.name
  force_delete = true # demo project: `terraform destroy` must not get stuck on images
}

# LangGraph DynamoDBSaver schema: PK/SK strings, optional `ttl` epoch attribute
resource "aws_dynamodb_table" "checkpoints" {
  name         = "${var.name}-checkpoints"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"
  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

resource "aws_iam_role" "lambda" {
  name = "${var.name}-lambda"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "app" {
  name = "app"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # ponytail: "*" for Bedrock; tighten to the one model + inference profile ARNs if this outlives the demo
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem"]
        Resource = aws_dynamodb_table.checkpoints.arn
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "app" {
  function_name = var.name
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repo.repository_url}:latest"
  architectures = ["x86_64"]
  memory_size   = 2048
  timeout       = 120
  environment {
    variables = {
      LLM_BACKEND      = "bedrock"
      BEDROCK_MODEL    = var.bedrock_model
      CHECKPOINT_TABLE = aws_dynamodb_table.checkpoints.name
      API_KEY          = random_password.api_key.result
      DATA_DIR         = "/var/task/data"
      INDEX_DIR        = "/var/task/index"
    }
  }
  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy_attachment.logs]
}

# Public URL; the handler enforces the x-api-key header itself.
resource "aws_lambda_function_url" "app" {
  function_name      = aws_lambda_function.app.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "url_public" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.app.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}

output "function_url" { value = aws_lambda_function_url.app.function_url }
output "ecr_repository_url" { value = aws_ecr_repository.repo.repository_url }
output "table" { value = aws_dynamodb_table.checkpoints.name }
output "api_key" {
  value     = random_password.api_key.result
  sensitive = true
}
