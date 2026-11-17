# GCP for the supplier search: the API, the agent worker and the Argo retraining workflow on GKE Autopilot (manifests
# in deploy/), searches over Pub/Sub with a dead-letter topic, state in Firestore, the model key in Secret Manager,
# images in Artifact Registry, the stance reader in a models bucket, and alerts on short searches and novel wording.

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
  backend "gcs" {}
}

variable "project" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west3" # Frankfurt
}

variable "alert_email" {
  type = string
}

provider "google" {
  project = var.project
  region  = var.region
}

resource "google_service_account" "scout" {
  account_id   = "supplier-scout"
  display_name = "Supplier search API and agent worker"
}

resource "google_pubsub_topic" "searches" {
  name = "supplier-searches"
}

resource "google_pubsub_topic" "dead" {
  name = "supplier-searches-dead"
}

resource "google_pubsub_subscription" "worker" {
  name                       = "supplier-searches"
  topic                      = google_pubsub_topic.searches.id
  ack_deadline_seconds       = 300
  message_retention_duration = "86400s"
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead.id
    max_delivery_attempts = 5
  }
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }
}

resource "google_firestore_database" "searches" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

resource "google_secret_manager_secret" "anthropic" {
  secret_id = "anthropic-api-key"
  replication {
    auto {}
  }
}

resource "google_project_iam_member" "scout" {
  for_each = toset(["roles/pubsub.publisher", "roles/pubsub.subscriber", "roles/datastore.user", "roles/logging.logWriter", "roles/monitoring.metricWriter"])
  project  = var.project
  role     = each.value
  member   = "serviceAccount:${google_service_account.scout.email}"
}

resource "google_secret_manager_secret_iam_member" "scout" {
  secret_id = google_secret_manager_secret.anthropic.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.scout.email}"
}

resource "google_artifact_registry_repository" "scout" {
  repository_id = "scout"
  location      = var.region
  format        = "DOCKER"
}

# the reader in production, its registry, and the supplier pages the API pods pull at start
resource "google_storage_bucket" "models" {
  name                        = "${var.project}-scout-models"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning {
    enabled = true # a promoted reader can be rolled back to the previous object version
  }
}

resource "google_container_cluster" "scout" {
  name                = "scout"
  location            = var.region
  enable_autopilot    = true
  deletion_protection = true
}

resource "google_service_account" "trainer" {
  account_id   = "scout-trainer"
  display_name = "Retraining workflow (Argo): harvest, train, gate, publish"
}

resource "google_storage_bucket_iam_member" "readers" {
  for_each = {
    api     = { member = google_service_account.scout.email, role = "roles/storage.objectViewer" }
    trainer = { member = google_service_account.trainer.email, role = "roles/storage.objectAdmin" }
  }
  bucket = google_storage_bucket.models.name
  role   = each.value.role
  member = "serviceAccount:${each.value.member}"
}

# Kubernetes service accounts act as the Google ones (workload identity): no keys in the cluster
resource "google_service_account_iam_member" "workload_identity" {
  for_each = {
    "scout/scout"        = google_service_account.scout.name
    "argo/scout-trainer" = google_service_account.trainer.name
  }
  service_account_id = each.value
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project}.svc.id.goog[${each.key}]"
}

# One log line per search (scout.ops.telemetry): searches that end short, and sentences in novel wording.
resource "google_logging_metric" "short_searches" {
  name   = "supplier_search_short"
  filter = "resource.type=\"k8s_container\" AND jsonPayload.event=\"scout.search\" AND jsonPayload.short=true"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "novel_sentences" {
  name            = "supplier_search_novel_sentences"
  filter          = "resource.type=\"k8s_container\" AND jsonPayload.event=\"scout.search\""
  value_extractor = "EXTRACT(jsonPayload.novel)"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
  }
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 10
      growth_factor      = 2
      scale              = 1
    }
  }
}

resource "google_monitoring_notification_channel" "email" {
  display_name = "Supplier search on call"
  type         = "email"
  labels       = { email_address = var.alert_email }
}

resource "google_monitoring_alert_policy" "failure_rate" {
  display_name = "Supplier searches that end short"
  combiner     = "OR"
  conditions {
    display_name = "short searches in the last hour"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/supplier_search_short\" AND resource.type=\"k8s_container\""
      comparison      = "COMPARISON_GT"
      threshold_value = 3
      duration        = "0s"
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
}

output "models_bucket" {
  value = google_storage_bucket.models.name
}

output "registry" {
  value = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.scout.repository_id}"
}
