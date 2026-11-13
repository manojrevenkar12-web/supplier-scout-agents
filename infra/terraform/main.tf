# GCP for the supplier search: the API and the agent worker on Cloud Run, searches over Pub/Sub with a dead-letter
# topic, state in Firestore, the model key in Secret Manager, and an alert when the search failure rate passes 1%.

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

variable "image" {
  description = "The container image built from this repository"
  type        = string
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

resource "google_cloud_run_v2_service" "service" {
  for_each = { api = "uvicorn scout.service.main:app --host 0.0.0.0 --port 8080", worker = "python -m scout.service.worker" }
  name     = "supplier-scout-${each.key}"
  location = var.region
  template {
    service_account = google_service_account.scout.email
    scaling {
      min_instance_count = each.key == "worker" ? 1 : 0
      max_instance_count = 10
    }
    containers {
      image   = var.image
      command = ["sh", "-c", each.value]
      env {
        name  = "GCP_PROJECT"
        value = var.project
      }
      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic.secret_id
            version = "latest"
          }
        }
      }
      resources {
        limits = { cpu = "2", memory = "2Gi" }
      }
    }
  }
}

# The agent logs one line per finished search with failed=true|false; the alert compares failures to searches.
resource "google_logging_metric" "failed_searches" {
  name   = "supplier_search_failed"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"search_done\" AND jsonPayload.failed=true"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_notification_channel" "email" {
  display_name = "Supplier search on call"
  type         = "email"
  labels       = { email_address = var.alert_email }
}

resource "google_monitoring_alert_policy" "failure_rate" {
  display_name = "Supplier search failures"
  combiner     = "OR"
  conditions {
    display_name = "failed searches in the last hour"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/supplier_search_failed\" AND resource.type=\"cloud_run_revision\""
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
