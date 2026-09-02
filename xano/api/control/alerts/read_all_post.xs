query "alerts/read_all" verb=POST {
  api_group = "control"
  description = "Mark every unread in-app alert in the caller's workspace as read"
  auth = "user"
  input {}
  stack {
    db.query "alert_log" {
      where = $db.alert_log.workspace_id == $auth.extras.workspace_id && $db.alert_log.channel == "in_app" && $db.alert_log.read == false
      return = { type: "list" }
    } as $unread

    var $n { value = 0 }
    foreach ($unread) {
      each as $a {
        db.patch "alert_log" {
          field_name = "id"
          field_value = $a.id
          data = { read: true }
        }
        var.update $n { value = $n + 1 }
      }
    }
  }
  response = { marked: $n }
  guid = "3pNiIdQz2D2WY-mDaVg2HYjSyvM"
}
