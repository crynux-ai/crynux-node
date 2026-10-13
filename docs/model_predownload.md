# Node Model Pre-download Flow

This document specifies how `crynux-node` handles background base-model pre-download requests delivered as relay `DownloadModel` events. Task-scoped downloads of non-base models are part of inference task execution and are specified in `docs/task-system-design.md` and `docs/task-lifecycle.md`.

## Overview

`crynux-node` MUST process relay base-model pre-download requests through the node manager task system. This event-driven path MUST download base models only. It is a background locality optimization and MUST remain independent of any inference task.

The flow has four stages:

1. Receive a `DownloadModel` event from relay.
2. Create a local download task keyed by `{node_address}_{model_files_digest}`.
3. Run the base-model download and report each downloaded model file with its exact revision to relay.
4. Persist final task state as `Success` or `Failed`.

The node MUST apply exponential backoff retries for download failures and MUST stop retrying after 3 attempts. Background jobs MUST NOT carry an execution deadline and MAY remain queued or in progress while a foreground task-scoped download uses the same serial download worker.

## Trigger Point

The event watcher in `NodeManager` MUST subscribe to relay `DownloadModel` events. Each event on this path MUST carry `model_files`, a list of model file requirements for base models. When an event for this node is received, `NodeManager` MUST call `TaskSystem.create_download_task(task_id, task_type, model_files)`.

### Model File Requirements

A model file requirement is a `ModelFileEntry` with the fields `source_type`, `repository`, `revision`, `format`, and `format_kwargs`. A requirement with a non-empty `revision` is exact and identifies the files to download. A requirement with an empty `revision` is a source: the node MUST download one revision of that source and MUST report the revision that was downloaded. `format_kwargs` MUST be an object; a JSON `null` MUST be read as an empty object.

The task identifier format MUST be:

`{node_address}_{model_files_digest}`

`model_files_digest` MUST be the SHA-256 digest of the requirements' canonical JSON representations, sorted and joined by newline, so that it does not depend on the order of the list.

## Download Task Lifecycle

`DownloadTaskRunner` MUST persist and transition download task state in `download_task_states`.

### State Machine

`DownloadTaskStatus` MUST follow this lifecycle:

- `Started`: task created, download not yet completed.
- `Executed`: model files downloaded locally and resolved to exact revisions, relay report pending.
- `Success`: relay report succeeded and local model cache updated.
- `Failed`: download retries exhausted; task is abandoned.

### Execution Rules

1. If a task already exists in state `Success` or `Failed`, `DownloadTaskRunner.run()` MUST return immediately.
2. In `Started`, the runner MUST execute `run_download_task(...)` with the model file requirements as a background job without a deadline.
3. After the local download succeeds, the runner MUST resolve every requirement to an exact `ModelFileEntry` and MUST set state to `Executed` with the resolved entries persisted in the task state. An exact requirement resolves to itself. A source requirement resolves to the entry with a revision that the worker returned for the same source. A download result that lacks a revision for a source requirement MUST fail the download.
4. In `Executed`, the runner MUST call `relay.node_report_model_downloaded(model_file)` once for each resolved entry.
5. After reporting succeeds, the runner MUST set state to `Success` and MUST save each resolved entry into `download_model_cache`.

The server MUST NOT inspect the Hugging Face cache before dispatching the job. The download worker MUST provide idempotent download behavior when the requested model is already present or partially downloaded.

The download worker manager MUST NOT restart the worker when a background job fails. Background failure handling consists only of the retry and persisted-state rules in this document. A download worker restart caused by a foreground task-scoped deadline cancels an in-flight background job; that cancellation MUST enter the same bounded retry flow.

## Retry and Backoff Policy

`TaskSystem._run_download_task` MUST use bounded retries with exponential backoff:

- Maximum attempts: `3`
- Backoff type: exponential
- Initial delay: `30s`
- Maximum delay cap: `300s`

If all retry attempts fail, the node MUST mark the task as `Failed` and MUST NOT continue retrying that task instance.

## Re-trigger Behavior

If a new `DownloadModel` event arrives for a task whose persisted state is `Failed`, `TaskSystem.create_download_task` MUST reset the state back to `Started` and enqueue a new execution cycle.

This allows future relay events to re-attempt download after a previous exhausted failure cycle.

## Persistence and Recovery

Download task states MUST be persisted in `download_task_states` through `DownloadTaskStateCache`.

On node restart, `TaskSystem._recover_download_task` MUST only recover tasks in:

- `Started`
- `Executed`

Tasks in `Success` or `Failed` MUST NOT be recovered for automatic execution.

### Local Downloaded Model Inventory

`download_model_cache` MUST store one record per exact `ModelFileEntry` with `source_type`, `repository`, `revision`, `format`, `format_kwargs`, and the task type. A record MUST have a non-empty revision. The inventory reported to relay MUST be exactly the entries of `download_model_cache`.

Startup preload MUST download every base model in the initial-task model and the configured preloaded base models as model file sources, MUST resolve each to the downloaded revision, and MUST save the resolved entries into `download_model_cache`. LoRA and ControlNet preloads populate the Hugging Face cache only and MUST NOT create inventory records.

When the local database holds `download_models` records or `download_task_states` records without the revision-bearing schema, startup MUST delete those tables' records by recreating the tables empty. The Hugging Face cache files MUST remain untouched. Models that were downloaded before the schema change and are not preloaded MUST NOT appear in the inventory until relay requests them again through a `DownloadModel` event.

Only background base-model pre-download tasks use `download_task_states`, `download_model_cache`, relay completion reporting, and restart recovery. Foreground non-base-model downloads are task-scoped execution steps and MUST NOT create these persistent download-task records or report individual model completion to the relay.

## Relevant Source Files

- `src/crynux_server/node_manager/node_manager.py`: subscribes to `DownloadModel` and creates download tasks
- `src/crynux_server/task/task_system.py`: queueing, retries, backoff, and failed-state handling
- `src/crynux_server/task/download_task.py`: download runner state transitions and relay reporting
- `src/crynux_server/models/model_file.py`: `ModelFileEntry`, digest, and requirement resolution
- `src/crynux_server/download_model_cache/`: local downloaded model inventory
- `src/crynux_server/db/connect.py`: upgrade of revision-less download tables
- `src/crynux_server/models/task.py`: `DownloadTaskStatus` definition
- `src/crynux_server/task/state_cache/db_impl.py`: persistent download task state storage
- `src/crynux_server/worker_manager/manager.py`: dispatches deadline-free background jobs and maps worker download errors to `TaskDownloadError`
