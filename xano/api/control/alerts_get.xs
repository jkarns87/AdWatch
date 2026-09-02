query "alerts" verb=GET {
  api_group = "control"
  description = "In-app alert inbox for the caller's workspace (newest first). Rows are written by /internal/dispatch for the in_app destination."
  auth = "user"
  input {}
  stack {
    db.query "alert_log" {
      where = $db.alert_log.workspace_id == $auth.extras.workspace_id && $db.alert_log.channel == "in_app"
      sort = { created_at: "desc" }
      return = { type: "list" }
    } as $alerts

    db.query "alert_log" {
      where = $db.alert_log.workspace_id == $auth.extras.workspace_id && $db.alert_log.channel == "in_app" && $db.alert_log.read == false
      return = { type: "count" }
    } as $unread
  }
  response = { unread: $unread, alerts: $alerts }
  guid = "QRBt3FNbUjnjXlukS2VS7vYHLYI"
}
