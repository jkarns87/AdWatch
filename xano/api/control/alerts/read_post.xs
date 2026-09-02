query "alerts/{alert_id}/read" verb=POST {
  api_group = "control"
  description = "Mark one in-app alert as read (must belong to the caller's workspace)"
  auth = "user"
  input {
    int alert_id {
      table = "alert_log"
    }
  }
  stack {
    db.get "alert_log" {
      field_name = "id"
      field_value = $input.alert_id
    } as $alert

    precondition ($alert != null && $alert.workspace_id == $auth.extras.workspace_id) {
      error_type = "notfound"
      error = "alert not found"
    }

    db.patch "alert_log" {
      field_name = "id"
      field_value = $input.alert_id
      data = { read: true }
    } as $updated
  }
  response = $updated
  guid = "lUKahljRjwnalYJqCaBKfD4trLU"
}
