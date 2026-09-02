query "alert_prefs/by_id/{alert_pref_id}" verb=DELETE {
  api_group = "control"
  description = "Remove an alert destination (must belong to the caller's workspace)"
  auth = "user"
  input {
    int alert_pref_id {
      table = "alert_pref"
    }
  }
  stack {
    db.get "alert_pref" {
      field_name = "id"
      field_value = $input.alert_pref_id
    } as $pref

    precondition ($pref != null && $pref.workspace_id == $auth.workspace_id) {
      error_type = "notfound"
      error = "alert preference not found"
    }

    db.del "alert_pref" {
      field_name = "id"
      field_value = $input.alert_pref_id
    }
  }
  response = { success: true }
  guid = "S5eh83O6W0gaOEiY4-APK9zFZyQ"
}
