locals {
  common_tags = {
    Project   = var.project
    ManagedBy = "terraform"
    Repo      = "github.com/kristopherlopez/Jeromelu"
  }
}
