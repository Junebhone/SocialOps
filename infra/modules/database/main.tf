# RDS PostgreSQL 16 plus the DATABASE_URL secret the api and worker read.
#
# Why a secret holding a whole URL rather than RDS's managed master password:
# config.py reads one DATABASE_URL (CLAUDE.md hard rule #1). ECS can inject a
# single key out of a JSON secret, but it cannot assemble a URL from parts, so
# the managed-password secret would force a code change in both services. This
# keeps the app untouched: the variable that was a compose string becomes a
# Secrets Manager reference, and nothing else changes.
#
# Cost of that choice: the password is in Terraform state. The state bucket is
# encrypted, versioned and private (infra/bootstrap). Write-only arguments
# (password_wo, secret_string_wo) would keep it out of state entirely and are
# the upgrade path; they are not used yet because they make rotation a manual
# version bump, which is more than Module 3 needs.

resource "random_password" "master" {
  length = 32
  # Alphanumeric only: the password goes into a URL, and RDS rejects / @ " and
  # spaces. Thirty-two characters from 62 symbols is ~190 bits.
  special = false
}

# Suffix for the final snapshot, fixed for the life of the instance. A fixed
# name like "<name>-final" makes the second destroy of an environment fail with
# DBSnapshotAlreadyExists. timestamp() would change on every plan.
resource "random_id" "final_snapshot" {
  byte_length = 4

  keepers = {
    identifier = var.name
  }
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids

  tags = { Name = var.name }
}

resource "aws_db_instance" "this" {
  identifier = var.name

  engine                     = "postgres"
  engine_version             = var.engine_version
  auto_minor_version_upgrade = true
  instance_class             = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.username
  password = random_password.master.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = var.security_group_ids
  publicly_accessible    = false
  multi_az               = var.multi_az

  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"
  copy_tags_to_snapshot   = true

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-final-${random_id.final_snapshot.hex}"

  apply_immediately = var.apply_immediately

  tags = { Name = var.name }
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = var.secret_name
  description             = "DATABASE_URL for the ${var.name} api and worker (asyncpg, TLS required)."
  recovery_window_in_days = var.secret_recovery_window_days
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id

  # Same driver and shape as the compose URL, plus ssl=require: RDS for
  # PostgreSQL 15+ already refuses non-TLS connections (rds.force_ssl=1), and
  # saying so in the URL makes a misconfigured client fail on connect with a
  # clear error rather than on the server's rejection.
  secret_string = format(
    "postgresql+asyncpg://%s:%s@%s:%d/%s?ssl=require",
    var.username,
    random_password.master.result,
    aws_db_instance.this.address,
    aws_db_instance.this.port,
    var.db_name,
  )
}
