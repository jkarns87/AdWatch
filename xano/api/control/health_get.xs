query "health" verb=GET {
  api_group = "control"
  description = "Liveness and config check for the control plane. ?deep=true also proves the scheduler can actually reach the data plane."
  input {
    bool deep?=false
  }
  stack {
    var $has_dataplane { value = $env.DATAPLANE_URL != null && $env.DATAPLANE_URL != "" }
    // Password reset links are built from DASHBOARD_URL. Unset, the email still
    // sends but points nowhere, which is invisible without this.
    var $has_dashboard { value = $env.DASHBOARD_URL != null && $env.DASHBOARD_URL != "" }
    // Reported separately: the scheduled collect task needs BOTH, and a missing
    // secret fails differently (401 from the data plane) than a missing URL
    // (a relative path that never resolves).
    var $has_secret { value = $env.DATAPLANE_SHARED_SECRET != null && $env.DATAPLANE_SHARED_SECRET != "" }

    // Both variables being set proves nothing about whether the secret MATCHES the
    // one the data plane holds — that only shows up as a 401 on the nightly task,
    // hours later and unattended. This calls the same authenticated endpoint the
    // task calls. Behind ?deep because it is an outbound request, not a liveness check.
    var $reachable { value = null }
    conditional {
      if ($input.deep == true && $has_dataplane == true) {
        api.request {
          url = $env.DATAPLANE_URL ~ "/api/v1/watchlists"
          method = "GET"
          headers = ["X-Workspace-Id: 1", "X-Dataplane-Secret: " ~ $env.DATAPLANE_SHARED_SECRET]
          timeout = 10
        } as $probe
        var.update $reachable { value = $probe.response.status }
      }
    }
  }
  response = {
    status: "ok",
    dataplane_configured: $has_dataplane,
    dashboard_url_configured: $has_dashboard,
    dataplane_secret_configured: $has_secret,
    dataplane_probe_status: $reachable
  }
  guid = "MLpxH5ea3wkzZGZ9nVd0LwfbdmI"
}
