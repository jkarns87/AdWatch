task "collect_all_watchlists" {
  description = "Every 6 hours: ask the data plane to collect + analyze every watchlist in every workspace"
  stack {
    db.query "workspace" {
      return = { type: "list" }
    } as $workspaces

    var $runs { value = 0 }

    foreach ($workspaces) {
      each as $ws {
        api.request {
          url = $env.DATAPLANE_URL ~ "/api/v1/watchlists"
          method = "GET"
          headers = ["X-Workspace-Id: " ~ ($ws.id|to_text), "X-Dataplane-Secret: " ~ $env.DATAPLANE_SHARED_SECRET]
          timeout = 30
        } as $list

        conditional {
          if ($list.response.status == 200) {
            foreach ($list.response.result) {
              each as $wl {
                api.request {
                  url = $env.DATAPLANE_URL ~ "/api/v1/watchlists/" ~ ($wl.id|to_text) ~ "/collect-and-analyze"
                  method = "POST"
                  params = {}
                  headers = ["X-Workspace-Id: " ~ ($ws.id|to_text), "X-Dataplane-Secret: " ~ $env.DATAPLANE_SHARED_SECRET, "Content-Type: application/json"]
                  timeout = 120
                } as $run
                var.update $runs { value = $runs + 1 }
              }
            }
          }
        }
      }
    }

    debug.log { value = "collect_all_watchlists triggered " ~ ($runs|to_text) ~ " runs" }
  }
  schedule = [{starts_on: 2026-09-02 00:00:00+0000, freq: 21600}]
  guid = "HuSpI31FyjFnyMr4dNYAqnVmT6Y"
}
