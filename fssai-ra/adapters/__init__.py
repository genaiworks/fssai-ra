"""Optional production adapters. Each maps a reference seam to a real backend
(Kafka, Iceberg, Spark, a local LLM). Imports are guarded so the core package
runs with no external infrastructure; install the extra to enable an adapter."""
