mock_provider "aws" {}

variables {
  name                  = "test"
  secret_name           = "socialops/test/database-url"
  subnet_ids            = ["subnet-a", "subnet-b"]
  security_group_ids    = ["sg-db"]
  instance_class        = "db.t4g.micro"
  multi_az              = false
  backup_retention_days = 1
}

run "disposable_database" {
  command = plan

  variables {
    deletion_protection = false
    skip_final_snapshot = true
  }

  assert {
    condition     = aws_db_instance.this.publicly_accessible == false && aws_db_instance.this.storage_encrypted == true
    error_message = "RDS must be private and encrypted in every environment."
  }

  assert {
    condition     = aws_db_instance.this.final_snapshot_identifier == null
    error_message = "A disposable database should not name a final snapshot."
  }
}

run "protected_database" {
  command = plan

  variables {
    multi_az            = true
    deletion_protection = true
    skip_final_snapshot = false
  }

  assert {
    condition     = aws_db_instance.this.multi_az == true && aws_db_instance.this.deletion_protection == true
    error_message = "multi_az and deletion_protection should pass straight through."
  }

  assert {
    condition     = startswith(aws_db_instance.this.final_snapshot_identifier, "test-final-")
    error_message = "A protected database must take a final snapshot on destroy, under a name unique to this instance."
  }
}

run "password_is_url_safe" {
  command = plan

  variables {
    deletion_protection = false
    skip_final_snapshot = true
  }

  assert {
    condition     = random_password.master.special == false && random_password.master.length >= 32
    error_message = "The password is embedded in DATABASE_URL, so it must be long and alphanumeric."
  }
}
