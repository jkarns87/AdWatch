task "prune_snapshots" {
  description = "Daily: drop snapshot payloads older than the retention window. Rows are kept; only raw goes."
  stack {
    api.request {
      url = $env.DATAPLANE_URL ~ "/api/v1/maintenance/prune-snapshots?keep_runs=20"
      method = "POST"
      params = {}
      headers = ["X-Dataplane-Secret: " ~ $env.DATAPLANE_SHARED_SECRET, "Content-Type: application/json"]
      timeout = 120
    } as $pruned

    conditional {
      if ($pruned.response.status == 200) {
        debug.log { value = "prune_snapshots freed " ~ ($pruned.response.result.bytes_freed|to_text) ~ " bytes across " ~ ($pruned.response.result.snapshots_pruned|to_text) ~ " snapshots" }
      }
      else {
        debug.log { value = "prune_snapshots failed with status " ~ ($pruned.response.status|to_text) }
      }
    }
  }
  schedule = [{starts_on: 2026-09-03 09:00:00+0000, freq: 86400}]
  guid = "N89zMduwaucHcvltNL42IGiWu4k"
}
