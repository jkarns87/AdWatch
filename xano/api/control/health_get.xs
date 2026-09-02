query "health" verb=GET {
  api_group = "control"
  description = "Liveness + config check for the control plane"
  input {}
  stack {
    var $has_dataplane { value = $env.DATAPLANE_URL != null && $env.DATAPLANE_URL != "" }
  }
  response = { status: "ok", dataplane_configured: $has_dataplane }
}
