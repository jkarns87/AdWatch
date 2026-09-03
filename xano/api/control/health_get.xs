query "health" verb=GET {
  api_group = "control"
  description = "Liveness + config check for the control plane"
  input {}
  stack {
    var $has_dataplane { value = $env.DATAPLANE_URL != null && $env.DATAPLANE_URL != "" }
    // Password reset links are built from DASHBOARD_URL. Unset, the email still
    // sends but points nowhere, which is invisible without this.
    var $has_dashboard { value = $env.DASHBOARD_URL != null && $env.DASHBOARD_URL != "" }
  }
  response = { status: "ok", dataplane_configured: $has_dataplane, dashboard_url_configured: $has_dashboard }
  guid = "MLpxH5ea3wkzZGZ9nVd0LwfbdmI"
}
