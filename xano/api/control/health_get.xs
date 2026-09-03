query "health" verb=GET {
  api_group = "control"
  description = "Liveness + config check for the control plane"
  input {}
  stack {
    var $has_dataplane { value = $env.DATAPLANE_URL != null && $env.DATAPLANE_URL != "" }
    // Password reset links are built from DASHBOARD_URL. Unset, the email still
    // sends but points nowhere, which is invisible without this.
    var $has_dashboard { value = $env.DASHBOARD_URL != null && $env.DASHBOARD_URL != "" }
    // Reported separately: the scheduled collect task needs BOTH, and a missing
    // secret fails differently (401 from the data plane) than a missing URL
    // (a relative path that never resolves).
    var $has_secret { value = $env.DATAPLANE_SHARED_SECRET != null && $env.DATAPLANE_SHARED_SECRET != "" }
  }
  response = { status: "ok", dataplane_configured: $has_dataplane, dashboard_url_configured: $has_dashboard, dataplane_secret_configured: $has_secret }
  guid = "MLpxH5ea3wkzZGZ9nVd0LwfbdmI"
}
